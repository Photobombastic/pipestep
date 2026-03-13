"""Data models for workflows, jobs, steps, and execution results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StepStatus(Enum):
    """Execution state of a pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Step:
    """A single step within a CI job (either a shell command or an action reference)."""

    name: str
    command: str
    env: dict = field(default_factory=dict)
    working_directory: str = "/workspace"
    status: StepStatus = StepStatus.PENDING
    breakpoint: bool = False
    is_action: bool = False
    action_ref: str = ""
    action_with: dict = field(default_factory=dict)
    output: str = ""
    exit_code: Optional[int] = None


@dataclass
class Job:
    """A CI job containing a sequence of steps and a target runner image."""

    name: str
    runs_on: str
    docker_image: str
    steps: list[Step] = field(default_factory=list)
    env: dict = field(default_factory=dict)


@dataclass
class Workflow:
    """A parsed GitHub Actions workflow with one or more jobs."""

    name: str
    trigger: str
    jobs: list[Job] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class StepResult:
    """Output captured from executing a single step in the container."""

    exit_code: int
    stdout: str
    stderr: str
