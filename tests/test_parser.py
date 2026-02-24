import os
from pipestep.parser import parse_workflow

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_parse_workflow_name():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    assert wf.name == "Test CI"


def test_parse_trigger():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    assert "push" in wf.trigger


def test_parse_jobs():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    assert len(wf.jobs) == 1
    assert wf.jobs[0].name == "build"


def test_runs_on_to_docker_image():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    assert wf.jobs[0].docker_image == "ubuntu:22.04"


def test_action_step_marked():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    checkout = wf.jobs[0].steps[0]
    assert checkout.is_action is True
    assert checkout.action_ref == "actions/checkout@v4"
    assert checkout.command == ""


def test_run_step_parsed():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    show_env = wf.jobs[0].steps[1]
    assert show_env.name == "Show env"
    assert show_env.command == 'echo "hello"'
    assert show_env.is_action is False


def test_env_flattening():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    show_env = wf.jobs[0].steps[1]
    assert show_env.env["CI"] == "true"
    assert show_env.env["GLOBAL_VAR"] == "from_workflow"
    assert show_env.env["JOB_VAR"] == "from_job"
    assert show_env.env["STEP_VAR"] == "from_step"


def test_multiline_command():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    multi = wf.jobs[0].steps[2]
    assert "line 1" in multi.command
    assert "line 2" in multi.command


def test_unnamed_step_gets_command_as_name():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    unnamed = wf.jobs[0].steps[3]
    assert unnamed.name == 'echo "unnamed step"'


def test_working_directory():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    custom = wf.jobs[0].steps[4]
    assert custom.working_directory == "/workspace/src"


def test_step_count():
    wf = parse_workflow(os.path.join(FIXTURES, "simple_workflow.yml"))
    assert len(wf.jobs[0].steps) == 5
