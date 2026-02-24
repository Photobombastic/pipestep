from pipestep.models import Step, Job, Workflow, StepResult, StepStatus


def test_step_defaults():
    step = Step(name="Install deps", command="pip install -r requirements.txt")
    assert step.status == StepStatus.PENDING
    assert step.breakpoint is False
    assert step.is_action is False
    assert step.env == {}
    assert step.working_directory == "/workspace"
    assert step.output == ""
    assert step.exit_code is None


def test_step_action():
    step = Step(name="Checkout", command="", is_action=True, action_ref="actions/checkout@v4")
    assert step.is_action is True
    assert step.action_ref == "actions/checkout@v4"


def test_job_defaults():
    job = Job(name="build", runs_on="ubuntu-latest", docker_image="ubuntu:22.04")
    assert job.steps == []
    assert job.env == {}


def test_workflow_defaults():
    wf = Workflow(name="CI", trigger="push")
    assert wf.jobs == []


def test_step_result():
    result = StepResult(exit_code=0, stdout="ok\n", stderr="")
    assert result.exit_code == 0


def test_step_status_values():
    assert StepStatus.PENDING.value == "pending"
    assert StepStatus.RUNNING.value == "running"
    assert StepStatus.COMPLETED.value == "completed"
    assert StepStatus.FAILED.value == "failed"
    assert StepStatus.SKIPPED.value == "skipped"
