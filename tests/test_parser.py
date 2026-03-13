import os
import tempfile
import pytest
from pipestep.parser import parse_workflow

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _write_yaml(content: str) -> str:
    """Write content to a temp YAML file and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
    f.write(content)
    f.close()
    return f.name


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


# --- Edge case tests ---


def test_empty_yaml_raises():
    path = _write_yaml("")
    with pytest.raises(ValueError, match="Invalid workflow file"):
        parse_workflow(path)
    os.unlink(path)


def test_runs_on_as_list():
    path = _write_yaml("""
name: Self-hosted
on: push
jobs:
  build:
    runs-on: [self-hosted, linux]
    steps:
      - run: echo hello
""")
    wf = parse_workflow(path)
    assert wf.jobs[0].runs_on == "self-hosted"
    assert wf.jobs[0].docker_image == "ubuntu:22.04"  # fallback
    os.unlink(path)


def test_job_with_no_steps():
    path = _write_yaml("""
name: Empty
on: push
jobs:
  empty:
    runs-on: ubuntu-latest
""")
    wf = parse_workflow(path)
    assert len(wf.jobs[0].steps) == 0
    os.unlink(path)


def test_workflow_with_no_jobs():
    path = _write_yaml("""
name: No jobs
on: push
""")
    with pytest.raises(ValueError, match="no 'jobs' section"):
        parse_workflow(path)
    os.unlink(path)


def test_trigger_string():
    path = _write_yaml("""
name: Simple
"on": push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""")
    wf = parse_workflow(path)
    assert "push" in wf.trigger
    os.unlink(path)


def test_trigger_list():
    path = _write_yaml("""
name: Multi trigger
"on": [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""")
    wf = parse_workflow(path)
    assert "push" in wf.trigger
    assert "pull_request" in wf.trigger
    os.unlink(path)


def test_boolean_env_lowercase():
    path = _write_yaml("""
name: Bool env
"on": push
env:
  CI: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo $CI
""")
    wf = parse_workflow(path)
    assert wf.jobs[0].steps[0].env["CI"] == "true"
    os.unlink(path)


def test_container_at_job_level():
    path = _write_yaml("""
name: Container job
"on": push
jobs:
  build:
    runs-on: ubuntu-latest
    container: node:18
    steps:
      - run: node --version
""")
    wf = parse_workflow(path)
    assert wf.jobs[0].docker_image == "node:18"
    os.unlink(path)


def test_container_as_dict():
    path = _write_yaml("""
name: Container dict
"on": push
jobs:
  build:
    runs-on: ubuntu-latest
    container:
      image: python:3.12
    steps:
      - run: python --version
""")
    wf = parse_workflow(path)
    assert wf.jobs[0].docker_image == "python:3.12"
    os.unlink(path)


def test_only_action_steps():
    path = _write_yaml("""
name: Actions only
"on": push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
""")
    wf = parse_workflow(path)
    assert len(wf.jobs[0].steps) == 2
    assert all(s.is_action for s in wf.jobs[0].steps)
    os.unlink(path)


def test_action_with_inputs_parsed():
    path = _write_yaml("""
name: With inputs
"on": push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-node@v4
        with:
          node-version: 18
""")
    wf = parse_workflow(path)
    step = wf.jobs[0].steps[0]
    assert step.is_action is True
    assert step.action_with == {"node-version": "18"}
    os.unlink(path)


def test_unrecognized_runs_on():
    path = _write_yaml("""
name: Custom runner
"on": push
jobs:
  build:
    runs-on: macos-latest
    steps:
      - run: echo hi
""")
    wf = parse_workflow(path)
    assert wf.jobs[0].docker_image == "ubuntu:22.04"  # default fallback
    os.unlink(path)


def test_env_as_string_does_not_crash():
    """Bug #3: env: 'something' (string) should not crash the parser."""
    path = _write_yaml("""
name: String env
"on": push
env: "some-string"
jobs:
  build:
    runs-on: ubuntu-latest
    env: "another-string"
    steps:
      - run: echo hi
        env: "step-string"
""")
    wf = parse_workflow(path)
    assert len(wf.jobs[0].steps) == 1
    os.unlink(path)
