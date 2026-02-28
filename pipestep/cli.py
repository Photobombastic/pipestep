import sys
import os
from pipestep import __version__
from pipestep.parser import parse_workflow


def main():
    if len(sys.argv) == 2 and sys.argv[1] in ("--version", "-V"):
        print(f"pipestep {__version__}")
        sys.exit(0)

    if len(sys.argv) < 3 or sys.argv[1] != "run":
        print("Usage: python cli.py run <workflow.yml> [--workdir <path>]")
        print("  Example: python cli.py run sample_workflow.yml")
        sys.exit(1)

    workflow_path = sys.argv[2]
    if not os.path.exists(workflow_path):
        print(f"Error: File not found: {workflow_path}")
        sys.exit(1)

    workdir = "."
    if "--workdir" in sys.argv:
        idx = sys.argv.index("--workdir")
        if idx + 1 < len(sys.argv):
            workdir = sys.argv[idx + 1]

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
            except (ValueError, EOFError):
                pass
            print("Invalid choice. Try again.")

    run_steps = [s for s in job.steps if not s.is_action]
    print(f"\nJob: {job.name}")
    print(f"Image: {job.docker_image}")
    print(f"Steps: {len(job.steps)} total, {len(run_steps)} runnable")
    print()

    from pipestep.tui import PipeStepApp
    app = PipeStepApp(workflow=workflow, job=job, workdir=workdir)
    app.run()


if __name__ == "__main__":
    main()
