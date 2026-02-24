# PipeStep

Interactive CI pipeline debugger. Step through your GitHub Actions workflows locally with Docker.

**"Set breakpoints on your CI stages, inspect the environment, fix issues live, then push with confidence."**

## Setup

```bash
# Prerequisites: Docker Desktop running, Python 3.11+
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Pre-pull the base image
docker pull ubuntu:22.04
```

## Usage

```bash
python cli.py run sample_workflow.yml
```

## Controls

| Key | Action |
|-----|--------|
| R | Run current step |
| S | Skip current step |
| I | Shell into container (interactive bash) |
| B | Toggle breakpoint on highlighted step |
| N | Auto-run to next breakpoint |
| Q | Quit and cleanup |
| Arrow keys | Navigate step list |

## When a Step Fails

PipeStep pauses and offers: **Retry**, **Inspect Shell**, **Skip**, or **Quit**. Shell in to debug the failure live inside the same container where it happened.
