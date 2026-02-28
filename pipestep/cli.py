import sys
import os
import yaml
from pipestep import __version__
from pipestep.parser import parse_workflow


def main():
    try:
        _run()
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML syntax")
        print(f"  {e}")
        sys.exit(1)


def _run():
    if len(sys.argv) == 2 and sys.argv[1] in ("--version", "-V"):
        print(f"pipestep {__version__}")
        sys.exit(0)

    if len(sys.argv) >= 2 and sys.argv[1] in ("--help", "-h"):
        _print_help()
        sys.exit(0)

    if len(sys.argv) < 3 or sys.argv[1] != "run":
        _print_help()
        sys.exit(1)

    if sys.argv[2] in ("--help", "-h"):
        _print_help()
        sys.exit(0)

    workflow_path = sys.argv[2]
    if not os.path.exists(workflow_path):
        print(f"Error: File not found: {workflow_path}")
        sys.exit(1)
    if not os.path.isfile(workflow_path):
        print(f"Error: Not a file: {workflow_path}")
        sys.exit(1)

    workdir = "."
    if "--workdir" in sys.argv:
        idx = sys.argv.index("--workdir")
        if idx + 1 < len(sys.argv):
            workdir = sys.argv[idx + 1]
        else:
            print("Error: --workdir requires a path argument")
            sys.exit(1)

    workdir = os.path.abspath(workdir)

    workflow = parse_workflow(workflow_path)
    print(f"Workflow: {workflow.name}")
    print(f"Trigger:  {workflow.trigger}")
    print(f"Jobs:     {len(workflow.jobs)}")

    if len(workflow.jobs) == 0:
        print("Error: No jobs found in workflow.")
        sys.exit(1)

    if len(workflow.jobs) == 1:
        job = workflow.jobs[0]
    else:
        print("\nMultiple jobs found. Select one:")
        for i, j in enumerate(workflow.jobs):
            print(f"  {i + 1}. {j.name} ({len(j.steps)} steps)")
        while True:
            try:
                choice = int(input("Enter job number: ")) - 1
                if 0 <= choice < len(workflow.jobs):
                    job = workflow.jobs[choice]
                    break
            except ValueError:
                pass
            except EOFError:
                print("\nError: Non-interactive terminal. Use a single-job workflow.")
                sys.exit(1)
            print("Invalid choice. Try again.")

    run_steps = [s for s in job.steps if not s.is_action]
    print(f"\nJob: {job.name}")
    print(f"Image: {job.docker_image}")
    print(f"Steps: {len(job.steps)} total, {len(run_steps)} runnable")

    if len(run_steps) == 0:
        print("\nError: This workflow has no runnable steps — only GitHub Actions (uses:).")
        print("PipeStep can only debug shell commands (run: steps).")
        print("See: https://github.com/photobombastic/pipestep#limitations")
        sys.exit(1)

    print()

    from pipestep.tui import PipeStepApp
    app = PipeStepApp(workflow=workflow, job=job, workdir=workdir)
    app.run()


def _print_help():
    print(f"pipestep {__version__} — Interactive CI pipeline debugger")
    print()
    print("Usage: pipestep run <workflow.yml> [options]")
    print()
    print("Options:")
    print("  --workdir <path>  Directory to mount as /workspace (default: .)")
    print("  --version, -V     Show version")
    print("  --help, -h        Show this help")
    print()
    print("Example:")
    print("  pipestep run .github/workflows/ci.yml")
    print("  pipestep run ci.yml --workdir /path/to/project")


if __name__ == "__main__":
    main()
