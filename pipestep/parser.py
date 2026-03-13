"""Parser for GitHub Actions workflow YAML files."""

from __future__ import annotations

import re
import sys
import yaml
from pipestep.models import Workflow, Job, Step

IMAGE_MAP = {
    "ubuntu-latest": "ubuntu:22.04",
    "ubuntu-24.04": "ubuntu:24.04",
    "ubuntu-22.04": "ubuntu:22.04",
    "ubuntu-20.04": "ubuntu:20.04",
}


def parse_workflow(path: str) -> Workflow:
    """Parse a GitHub Actions YAML file into a Workflow model."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Invalid workflow file: expected YAML mapping, got {type(raw).__name__}")

    # PyYAML parses bare `on:` as boolean True — normalize it
    if True in raw:
        raw["on"] = raw.pop(True)

    if not isinstance(raw.get("jobs"), dict):
        raise ValueError("Invalid workflow file: no 'jobs' section found")

    name = raw.get("name", "Unnamed Workflow")

    trigger_raw = raw.get("on", {})
    if isinstance(trigger_raw, str):
        trigger = f"on: {trigger_raw}"
    elif isinstance(trigger_raw, list):
        trigger = f"on: {', '.join(str(t) for t in trigger_raw)}"
    elif isinstance(trigger_raw, dict):
        trigger = f"on: {', '.join(str(k) for k in trigger_raw.keys())}"
    else:
        trigger = "on: unknown"

    workflow_env = _str_dict(raw.get("env", {}))

    warnings = []
    jobs = []
    for job_id, job_raw in raw.get("jobs", {}).items():
        runs_on = job_raw.get("runs-on", "ubuntu-latest")

        # Handle runs-on as a list (e.g. [self-hosted, linux])
        if isinstance(runs_on, list):
            runs_on_key = runs_on[0] if runs_on else "ubuntu-latest"
        else:
            runs_on_key = str(runs_on)

        # Detect matrix/expression placeholders that can't be resolved locally
        if re.search(r'\$\{\{', runs_on_key):
            msg = f"Job '{job_id}': runs-on uses expression '{runs_on_key}' which can't be resolved locally. Using ubuntu:22.04."
            warnings.append(msg)
            print(f"\u26a0 Warning: {msg}", file=sys.stderr)
            runs_on_key = "ubuntu-latest"

        # Check for container: at job level first
        container_raw = job_raw.get("container", None)
        if isinstance(container_raw, str):
            docker_image = container_raw
        elif isinstance(container_raw, dict):
            docker_image = container_raw.get("image", IMAGE_MAP.get(runs_on_key, "ubuntu:22.04"))
        else:
            docker_image = IMAGE_MAP.get(runs_on_key, "ubuntu:22.04")

        if runs_on_key not in IMAGE_MAP and container_raw is None:
            msg = f"'{runs_on_key}' has no local Docker mapping. Using ubuntu:22.04 as fallback."
            warnings.append(msg)
            print(f"\u26a0 Warning: {msg}", file=sys.stderr)

        job_env = _str_dict(job_raw.get("env", {}))

        steps = []
        for step_raw in job_raw.get("steps", []):
            step_env = {**workflow_env, **job_env, **_str_dict(step_raw.get("env", {}))}

            if "uses" in step_raw:
                action_ref = step_raw["uses"]
                step_name = step_raw.get("name", f"Action: {action_ref}")
                action_with = _str_dict(step_raw.get("with", {}))
                steps.append(Step(
                    name=step_name,
                    command="",
                    env=step_env,
                    is_action=True,
                    action_ref=action_ref,
                    action_with=action_with,
                ))
            elif "run" in step_raw:
                command = step_raw["run"].strip()
                step_name = step_raw.get("name", command.split("\n")[0])
                working_dir = step_raw.get("working-directory")
                if working_dir and not working_dir.startswith("/"):
                    working_dir = f"/workspace/{working_dir}"
                elif working_dir is None:
                    working_dir = "/workspace"

                # Warn about unresolvable expressions in commands
                expressions = re.findall(r'\$\{\{[^}]*\}\}', command)
                matrix_exprs = [e for e in expressions if 'matrix.' in e or 'secrets.' in e or 'github.' in e]
                if matrix_exprs:
                    msg = f"Step '{step_name}': contains expressions {', '.join(matrix_exprs[:3])} that won't resolve locally."
                    warnings.append(msg)
                    print(f"\u26a0 Warning: {msg}", file=sys.stderr)

                steps.append(Step(
                    name=step_name,
                    command=command,
                    env=step_env,
                    working_directory=working_dir,
                ))

        jobs.append(Job(
            name=job_id,
            runs_on=runs_on_key,
            docker_image=docker_image,
            steps=steps,
            env={**workflow_env, **job_env},
        ))

    return Workflow(name=name, trigger=trigger, jobs=jobs, warnings=warnings)


def _str_dict(d: dict) -> dict:
    """Coerce all keys and values to strings, normalizing None and booleans."""
    if not isinstance(d, dict):
        return {}
    result = {}
    for k, v in d.items():
        if v is None:
            result[str(k)] = ""
        elif isinstance(v, bool):
            result[str(k)] = str(v).lower()
        else:
            result[str(k)] = str(v)
    return result
