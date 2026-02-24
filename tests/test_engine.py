import pytest
import docker
from pipestep.engine import PipelineEngine
from pipestep.models import Step, Job


@pytest.fixture
def sample_job():
    return Job(
        name="test-job",
        runs_on="ubuntu-latest",
        docker_image="ubuntu:22.04",
        steps=[
            Step(name="Echo hello", command='echo "hello world"'),
            Step(name="Create file", command="touch /workspace/testfile.txt"),
            Step(name="Failing step", command="exit 1"),
        ],
    )


@pytest.fixture
def engine(sample_job, tmp_path):
    eng = PipelineEngine(job=sample_job, workdir=str(tmp_path))
    yield eng
    eng.cleanup()


class TestEngineSetup:
    def test_setup_creates_container(self, engine):
        engine.setup()
        assert engine.container is not None
        engine.container.reload()
        assert engine.container.status == "running"

    def test_setup_mounts_workdir(self, engine):
        engine.setup()
        exit_code, output = engine.container.exec_run("ls /workspace")
        assert exit_code == 0


class TestStepExecution:
    def test_run_step_success(self, engine, sample_job):
        engine.setup()
        result = engine.run_step(sample_job.steps[0])
        assert result.exit_code == 0
        assert "hello world" in result.stdout

    def test_run_step_creates_file(self, engine, sample_job):
        engine.setup()
        engine.run_step(sample_job.steps[1])
        exit_code, output = engine.container.exec_run("ls /workspace/testfile.txt")
        assert exit_code == 0

    def test_run_step_failure(self, engine, sample_job):
        engine.setup()
        result = engine.run_step(sample_job.steps[2])
        assert result.exit_code != 0

    def test_run_step_with_env(self, engine):
        engine.setup()
        step = Step(name="Env test", command='echo "$MY_VAR"', env={"MY_VAR": "hello123"})
        result = engine.run_step(step)
        assert "hello123" in result.stdout

    def test_run_step_with_working_directory(self, engine):
        engine.setup()
        engine.container.exec_run("mkdir -p /workspace/subdir")
        step = Step(name="Workdir test", command="pwd", working_directory="/workspace/subdir")
        result = engine.run_step(step)
        assert "/workspace/subdir" in result.stdout


class TestContainerInspection:
    def test_get_env(self, engine):
        engine.setup()
        env = engine.get_env()
        assert isinstance(env, dict)
        assert "PATH" in env

    def test_get_files(self, engine):
        engine.setup()
        files = engine.get_files("/")
        assert len(files) > 0

    def test_container_id_available(self, engine):
        engine.setup()
        assert engine.container_id != ""


class TestCleanup:
    def test_cleanup_removes_container(self, engine):
        engine.setup()
        container_id = engine.container.id
        engine.cleanup()
        client = docker.from_env()
        with pytest.raises(docker.errors.NotFound):
            client.containers.get(container_id)
