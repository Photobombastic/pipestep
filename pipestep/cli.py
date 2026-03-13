"""Command-line interface for PipeStep."""

from __future__ import annotations

import sys
import os
import yaml
from pipestep import __version__
from pipestep.parser import parse_workflow


def main() -> None:
    """Entry point for the pipestep CLI."""
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


def _run() -> None:
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

    try:
        workflow = parse_workflow(workflow_path)
    except Exception as e:
        print(f"Error parsing workflow: {e}")
        sys.exit(1)

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
            except KeyboardInterrupt:
                print("\nAborted.")
                sys.exit(0)
            print("Invalid choice. Try again.")

    run_steps = [s for s in job.steps if not s.is_action]
    action_steps = len(job.steps) - len(run_steps)
    print(f"\nJob: {job.name}")
    print(f"Image: {job.docker_image}")
    print(f"Steps: {len(job.steps)} total, {len(run_steps)} runnable, {action_steps} actions")

    if len(job.steps) == 0:
        print("\nError: This job has no steps defined.")
        sys.exit(1)

    if action_steps > 0 and len(run_steps) == 0:
        print("\nNote: This workflow only has action steps (uses:).")
        print("PipeStep will offer local equivalents where available.")

    print()
    print(f"⚠  {workdir} will be mounted read-write into the container.")
    print(f"   Steps can modify your files. Use --workdir to mount a copy if concerned.")
    print()

    from pipestep.tui import PipeStepApp
    app = PipeStepApp(workflow=workflow, job=job, workdir=workdir)
    app.run()


def _print_help() -> None:
    """Print CLI usage information."""
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
