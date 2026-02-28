import os
import shlex
import subprocess

import docker
from docker.errors import NotFound, ImageNotFound
from pipestep.models import Step, Job, StepResult


class PipelineEngine:
    def __init__(self, job: Job, workdir: str = "."):
        self.job = job
        self.workdir = workdir
        try:
            self.client = docker.from_env()
            self.client.ping()
        except docker.errors.DockerException:
            print("Error: Can't connect to Docker. Is Docker Desktop running?")
            raise SystemExit(1)
        self.container = None
        self._container_name = f"pipestep-{job.name}-{os.getpid()}"

    @property
    def container_id(self) -> str:
        if self.container is None:
            return ""
        return self.container.id

    def setup(self) -> None:
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

    def run_step(self, step: Step) -> StepResult:
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
        if self.container is None:
            return []
        result = self.container.exec_run(f"ls -1 {shlex.quote(path)}", demux=True)
        stdout = result.output[0].decode() if result.output[0] else ""
        return [f for f in stdout.strip().split("\n") if f]

    def cleanup(self) -> None:
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
