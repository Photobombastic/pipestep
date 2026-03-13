"""Docker-based execution engine for running pipeline steps in containers."""

from __future__ import annotations

import os
import re
import atexit
import shlex
import signal
import subprocess

import docker
from docker.errors import NotFound, ImageNotFound
from pipestep.models import Step, Job, StepResult

# Module-level registry so atexit/signal handlers can find all engines
_active_engines: list["PipelineEngine"] = []


def _cleanup_all_engines() -> None:
    for engine in list(_active_engines):
        engine.cleanup()


atexit.register(_cleanup_all_engines)


def _signal_handler(signum, frame) -> None:
    _cleanup_all_engines()
    raise SystemExit(1)


# Install signal handlers only if we're not going to clobber existing ones
for _sig in (signal.SIGTERM, signal.SIGINT):
    if signal.getsignal(_sig) in (signal.SIG_DFL, None):
        signal.signal(_sig, _signal_handler)


class PipelineEngine:
    """Manages a Docker container that executes pipeline steps sequentially."""

    def __init__(self, job: Job, workdir: str = ".") -> None:
        self.job = job
        self.workdir = os.path.abspath(workdir)
        self._client = None
        self.container = None
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '-', job.name)
        self._container_name = f"pipestep-{safe_name}-{os.getpid()}"

    @property
    def client(self):
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client.ping()
            except docker.errors.DockerException as e:
                raise RuntimeError(
                    "Cannot connect to Docker. Is Docker Desktop running?\n"
                    f"  Error: {e}"
                ) from e
        return self._client

    @property
    def container_id(self) -> str:
        """Return the running container's ID, or empty string if none."""
        if self.container is None:
            return ""
        return self.container.id

    def setup(self) -> None:
        """Pull the Docker image and start a long-running container."""
        image = self.job.docker_image

        try:
            self.client.images.get(image)
        except ImageNotFound:
            self.client.images.pull(image)

        # Remove stale container with same name
        try:
            old = self.client.containers.get(self._container_name)
            old.remove(force=True)
        except NotFound:
            pass

        # Default env vars to match GitHub Actions runner
        git_sha = ""
        git_ref = ""
        try:
            git_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=self.workdir, stderr=subprocess.DEVNULL
            ).decode().strip()
            git_ref = subprocess.check_output(
                ["git", "symbolic-ref", "HEAD"], cwd=self.workdir, stderr=subprocess.DEVNULL
            ).decode().strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        default_env = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_WORKSPACE": "/workspace",
            "GITHUB_SHA": git_sha,
            "GITHUB_REF": git_ref,
            "RUNNER_OS": "Linux",
            "RUNNER_TEMP": "/tmp",
            "DEBIAN_FRONTEND": "noninteractive",
        }

        self.container = self.client.containers.run(
            image=image,
            command="sleep infinity",
            volumes={
                self.workdir: {"bind": "/workspace", "mode": "rw"},
            },
            working_dir="/workspace",
            environment={
                **default_env,
                **self.job.env,
            },
            name=self._container_name,
            detach=True,
        )
        if self not in _active_engines:
            _active_engines.append(self)

    def run_step(self, step: Step) -> StepResult:
        """Execute a step's shell command inside the container."""
        if self.container is None:
            raise RuntimeError("Engine not set up. Call setup() first.")

        env = {**self.job.env, **step.env}
        cmd = f"bash --noprofile --norc -e -o pipefail -c {shlex.quote(step.command)}"

        result = self.container.exec_run(
            cmd,
            environment=env,
            workdir=step.working_directory,
            demux=True,
        )

        stdout = result.output[0].decode("utf-8", errors="replace") if result.output[0] else ""
        stderr = result.output[1].decode("utf-8", errors="replace") if result.output[1] else ""

        return StepResult(
            exit_code=result.exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    def get_env(self) -> dict:
        """Return the container's current environment variables."""
        if self.container is None:
            return {}
        result = self.container.exec_run("env", demux=True)
        stdout = result.output[0].decode() if result.output[0] else ""
        env = {}
        for line in stdout.strip().split("\n"):
            if "=" in line:
                key, _, value = line.partition("=")
                env[key] = value
        return env

    def get_files(self, path: str = "/workspace") -> list[str]:
        """List files at the given path inside the container."""
        if self.container is None:
            return []
        result = self.container.exec_run(f"ls -1 {shlex.quote(path)}", demux=True)
        stdout = result.output[0].decode() if result.output[0] else ""
        return [f for f in stdout.strip().split("\n") if f]

    def cleanup(self) -> None:
        """Stop and remove the container, ignoring errors during teardown."""
        if self.container is not None:
            try:
                self.container.stop(timeout=3)
            except Exception:
                pass
            try:
                self.container.remove(force=True)
            except Exception:
                pass
            self.container = None
        if self in _active_engines:
            _active_engines.remove(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()
