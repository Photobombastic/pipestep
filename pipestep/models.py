from dataclasses import dataclass, field
from enum import Enum


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Step:
    name: str
    command: str
    env: dict = field(default_factory=dict)
    working_directory: str = "/workspace"
    status: StepStatus = StepStatus.PENDING
    breakpoint: bool = False
    is_action: bool = False
    action_ref: str = ""
    output: str = ""
    exit_code: int | None = None


@dataclass
class Job:
    name: str
    runs_on: str
    docker_image: str
    steps: list[Step] = field(default_factory=list)
    env: dict = field(default_factory=dict)


@dataclass
class Workflow:
    name: str
    trigger: str
    jobs: list[Job] = field(default_factory=list)


@dataclass
class StepResult:
    exit_code: int
    stdout: str
    stderr: str
