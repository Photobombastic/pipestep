# PipeStep

**A debugger for your CI pipeline.**

Step through GitHub Actions workflows locally with Docker. Pause before each step, inspect the environment, drop into a shell, modify variables, re-run failed steps — without pushing and waiting.

<p align="center">
  <img src="demo.gif" alt="PipeStep demo" width="700">
</p>

## The Problem

The CI debugging loop:

1. Commit a fix
2. Push to GitHub
3. Wait 2-5 minutes for the runner
4. Watch it fail
5. Read the logs, guess what went wrong
6. Repeat

A single debugging session eats 30-60 minutes. PipeStep lets you step through the pipeline locally, inspect the container at each stage, and fix issues before you push.

## Install

```bash
pip install git+https://github.com/photobombastic/pipestep.git
```

Requires Python 3.11+ and Docker Desktop running.

## Quick Start

```bash
# Point it at any GitHub Actions workflow
pipestep run .github/workflows/ci.yml

# Or try the included sample
pipestep run sample_workflow.yml
```

## Controls

| Key | Action |
|-----|--------|
| **R** | Run the current step |
| **S** | Skip the current step |
| **I** | Shell into the container (interactive bash) |
| **B** | Toggle breakpoint on a step |
| **N** | Auto-run to the next breakpoint |
| **Q** | Quit and cleanup containers |

## When a Step Fails

PipeStep pauses and lets you:

- **Shell in** to the exact container where it failed — same filesystem, same env vars
- **Retry** the step after making changes inside the container
- **Skip** past it and continue the pipeline
- **Quit** and clean up

No more guessing from log output. You're inside the environment where it broke.

## How It Works

1. Parses your GitHub Actions YAML
2. Maps `runs-on` to a local Docker image (e.g. `ubuntu-latest` → `ubuntu:22.04`)
3. Creates a container and executes each step sequentially
4. Pauses between steps so you can inspect, modify, or debug

## PipeStep vs `act`

| | PipeStep | act |
|---|---|---|
| **Execution model** | Step-through with pause/inspect | Batch run |
| **Shell into container** | Yes, mid-pipeline | No |
| **Breakpoints** | Yes | No |
| **Re-run failed steps** | Yes | Restart entire pipeline |
| **Primary use case** | Debugging | Running locally |

[`act`](https://github.com/nektos/act) is great for running pipelines locally. PipeStep is for when things go wrong and you need to figure out why.

## Contributing

```bash
git clone https://github.com/photobombastic/pipestep.git
cd pipestep
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest
```

## License

[MIT](LICENSE)
