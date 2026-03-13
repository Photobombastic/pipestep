"""Terminal UI for interactive pipeline debugging using Textual."""

from __future__ import annotations

import atexit
import subprocess
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, RichLog, ListView, ListItem, Label
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual import work
from rich.text import Text

from pipestep.models import Step, Job, Workflow, StepStatus, StepResult
from pipestep.engine import PipelineEngine
from pipestep.actions import get_action_equivalent


class StepListItem(ListItem):
    """A single step in the step list sidebar."""

    def __init__(self, step: Step, index: int) -> None:
        super().__init__()
        self.step = step
        self.step_index = index

    def compose(self) -> ComposeResult:
        yield Label(self._render_label())

    def _render_label(self) -> str:
        icon = self._status_icon()
        bp = " [magenta][B][/magenta]" if self.step.breakpoint else ""
        if self.step.is_action and self.step.status == StepStatus.SKIPPED:
            tag = " [dim](action — skipped)[/dim]"
        elif self.step.is_action:
            tag = " [yellow](action)[/yellow]"
        else:
            tag = ""
        return f"{icon} {self.step_index + 1}. {self.step.name}{tag}{bp}"

    def _status_icon(self) -> str:
        icons = {
            StepStatus.PENDING: "  ",
            StepStatus.RUNNING: "[yellow]~[/yellow]",
            StepStatus.PAUSED: "[cyan]●[/cyan]",
            StepStatus.COMPLETED: "[green]✓[/green]",
            StepStatus.FAILED: "[red]✗[/red]",
            StepStatus.SKIPPED: "[dim]⊘[/dim]",
        }
        return icons.get(self.step.status, " ")

    def refresh_label(self) -> None:
        try:
            self.query_one(Label).update(self._render_label())
        except NoMatches:
            pass


class StepDetailPanel(Static):
    """Shows details about the currently selected step."""

    def update_step(self, step: Step, job: Job) -> None:
        env_str = ", ".join(f"{k}={v}" for k, v in list(step.env.items())[:5])
        if len(step.env) > 5:
            env_str += f", ... (+{len(step.env) - 5} more)"

        if step.is_action:
            equiv = get_action_equivalent(step.action_ref, step.action_with)
            if equiv:
                cmd_display = f"Action: {step.action_ref}\n[green]Equivalent: {equiv[0]}[/green]\n  Press [bold]R[/bold] to run equivalent, [bold]S[/bold] to skip, [bold]I[/bold] to shell in"
            else:
                cmd_display = f"Action: {step.action_ref}\n[yellow]No local equivalent known[/yellow]\n  Press [bold]S[/bold] to skip, [bold]I[/bold] to shell in and set up manually"
        else:
            cmd_lines = step.command.split("\n")
            if len(cmd_lines) > 5:
                cmd_display = "\n".join(cmd_lines[:5]) + f"\n... (+{len(cmd_lines) - 5} more lines)"
            else:
                cmd_display = step.command

        text = (
            f"[bold]{step.name}[/bold]\n"
            f"Image: {job.docker_image}\n"
            f"Command:\n{cmd_display}\n"
            f"Env: {env_str}\n"
            f"Working dir: {step.working_directory}\n"
            f"Status: {step.status.value}"
        )
        self.update(text)


class PipeStepApp(App):
    """PipeStep — Interactive CI Pipeline Debugger."""

    CSS = """
    #step-list {
        width: 50;
        border: solid $primary;
        padding: 0 1;
    }
    #right-pane {
        width: 1fr;
    }
    #step-detail {
        height: 11;
        border: solid $accent;
        padding: 1;
    }
    #output-log {
        height: 1fr;
        border: solid $success;
    }
    #help-bar {
        height: 3;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("r", "run_step", "Run"),
        ("s", "skip_step", "Skip"),
        ("i", "shell_in", "Shell In"),
        ("b", "toggle_breakpoint", "Breakpoint"),
        ("n", "run_to_breakpoint", "Run to BP"),
        ("q", "quit_app", "Quit"),
    ]


    current_step_index = reactive(0)
    running = reactive(False)

    def __init__(self, workflow: Workflow, job: Job, workdir: str = "."):
        super().__init__()
        self.workflow = workflow
        self.job = job
        self.workdir = workdir
        self.engine = PipelineEngine(job=job, workdir=workdir)
        atexit.register(self.engine.cleanup)
        self.title = f"PipeStep — {workflow.name} → {job.name}"
        self._auto_running = False
        self._quit_pending = False
        self.session_log: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(
                *[StepListItem(step, i) for i, step in enumerate(self.job.steps)],
                id="step-list",
            )
            with Vertical(id="right-pane"):
                yield StepDetailPanel(id="step-detail")
                yield RichLog(highlight=True, markup=True, auto_scroll=True, id="output-log")
                yield Static(
                    "[R]un / Run Equivalent  [S]kip  [I]nspect Shell  [B]reakpoint  [N] Run to BP  [Q]uit",
                    id="help-bar",
                )
        yield Footer()

    def on_mount(self) -> None:
        self._log("[bold]PipeStep[/bold] — Interactive CI Pipeline Debugger")
        self._log(f"Workflow: {self.workflow.name}")
        self._log(f"Job: {self.job.name} ({self.job.docker_image})")

        # Show parser warnings in the TUI (e.g., unmapped runs-on)
        if hasattr(self.workflow, '_parser_warnings'):
            for warn in self.workflow._parser_warnings:
                self._log(f"[yellow]  ⚠ {warn}[/yellow]")

        self._log("")
        self._log("Setting up Docker container...")
        self._setup_engine()

    @work(thread=True)
    def _setup_engine(self) -> None:
        try:
            self.engine.setup()
            self.call_from_thread(self._log, "[green]Container ready.[/green]\n")
            self.call_from_thread(self._advance_to_first_runnable)
        except Exception as e:
            self.call_from_thread(self._log, f"[red]Setup failed: {e}[/red]")

    def _advance_to_first_runnable(self) -> None:
        if len(self.job.steps) == 0:
            self._log("[yellow]No steps found in this job.[/yellow]")
            return
        step = self.job.steps[0]
        self.current_step_index = 0
        step.status = StepStatus.PAUSED
        self._refresh_step(0)
        self._select_step(0)
        if step.is_action:
            equiv = get_action_equivalent(step.action_ref, step.action_with)
            self._log(f"[cyan]● Paused at action: {step.name}[/cyan]")
            if equiv:
                self._log(f"  [green]Local equivalent available:[/green] {equiv[0]}")
                self._log("  Press [bold]R[/bold] to run equivalent, [bold]S[/bold] to skip, [bold]I[/bold] to shell in")
            else:
                self._log("  [yellow]No local equivalent known.[/yellow]")
                self._log("  Press [bold]S[/bold] to skip, [bold]I[/bold] to shell in and set up manually")
        else:
            self._log(f"[cyan]● Paused at: {step.name}[/cyan]")
            self._log("  Press [bold]R[/bold] to run, [bold]S[/bold] to skip, [bold]I[/bold] to inspect")

    def _current_step(self) -> Step | None:
        if 0 <= self.current_step_index < len(self.job.steps):
            return self.job.steps[self.current_step_index]
        return None

    def watch_current_step_index(self, index: int) -> None:
        self._update_detail_panel()

    def _update_detail_panel(self) -> None:
        step = self._current_step()
        if step:
            try:
                self.query_one(StepDetailPanel).update_step(step, self.job)
            except NoMatches:
                pass

    def _log(self, message: str) -> None:
        try:
            self.query_one("#output-log", RichLog).write(message)
        except NoMatches:
            pass

    def _refresh_step(self, index: int) -> None:
        try:
            items = self.query_one("#step-list", ListView).children
            if 0 <= index < len(items):
                items[index].refresh_label()
        except NoMatches:
            pass

    def _select_step(self, index: int) -> None:
        try:
            list_view = self.query_one("#step-list", ListView)
            list_view.index = index
        except NoMatches:
            pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and isinstance(event.item, StepListItem):
            self.query_one(StepDetailPanel).update_step(event.item.step, self.job)

    # --- Actions ---

    def action_run_step(self) -> None:
        if self.running:
            self.notify("Step is still running...", severity="information")
            return
        step = self._current_step()
        if step is None:
            return
        if step.status not in (StepStatus.PAUSED, StepStatus.PENDING, StepStatus.FAILED):
            return
        self._quit_pending = False

        # Handle action steps: run equivalent command if available
        if step.is_action:
            equiv = get_action_equivalent(step.action_ref, step.action_with)
            if equiv is None:
                self._log(f"[yellow]No local equivalent for {step.action_ref}[/yellow]")
                self._log("  Press [bold]I[/bold] to shell in and set up manually, or [bold]S[/bold] to skip")
                return
            self.running = True
            step.status = StepStatus.RUNNING
            self._refresh_step(self.current_step_index)
            self._update_detail_panel()
            self._log(f"\n[bold]> Running equivalent for: {step.name}[/bold]")
            self._log(f"  [dim]{equiv[0]}[/dim]")
            # Create a temporary step-like object with the equivalent command
            equiv_step = Step(
                name=step.name,
                command=equiv[1],
                env=step.env,
                working_directory="/workspace",
            )
            self._record_action("run_equivalent", step.name, equiv[1])
            self._execute_step(equiv_step, self.current_step_index)
            return

        self.running = True
        step.status = StepStatus.RUNNING
        self._refresh_step(self.current_step_index)
        self._update_detail_panel()
        self._log(f"\n[bold]> Running: {step.name}[/bold]")
        self._record_action("run", step.name, step.command)
        self._execute_step(step, self.current_step_index)

    @work(thread=True)
    def _execute_step(self, step: Step, index: int) -> None:
        try:
            result = self.engine.run_step(step)
            self.call_from_thread(self._on_step_complete, step, index, result)
        except Exception as e:
            self.call_from_thread(
                self._on_step_complete,
                step,
                index,
                StepResult(exit_code=1, stdout="", stderr=str(e)),
            )

    def _on_step_complete(self, step: Step, index: int, result: StepResult) -> None:
        # Always update the real job step (step might be a temp equiv_step)
        real_step = self.job.steps[index]
        real_step.exit_code = result.exit_code
        real_step.output = result.stdout + result.stderr
        step = real_step

        if result.stdout:
            for line in result.stdout.rstrip().split("\n"):
                self._log(Text(f"  {line}"))
        if result.stderr:
            for line in result.stderr.rstrip().split("\n"):
                self._log(Text(f"  {line}", style="red"))

        if result.exit_code == 0:
            step.status = StepStatus.COMPLETED
            self._log(f"[green]  ✓ Step passed (exit code 0)[/green]")
        else:
            step.status = StepStatus.FAILED
            self._log(f"[red]  ✗ Step failed (exit code {result.exit_code})[/red]")
            self._log("[yellow]  [R]etry  [I]nspect Shell  [S]kip  [Q]uit[/yellow]")

        self._refresh_step(index)
        self._update_detail_panel()
        self.running = False

        if step.status == StepStatus.COMPLETED:
            # Always advance to the next step after completion
            self._advance_to_next()
            next_step = self._current_step()
            if next_step is None:
                self._auto_running = False
                return
            if self._auto_running:
                if next_step.breakpoint:
                    self._auto_running = False
                    self._log(f"\n[cyan]● Breakpoint hit: {next_step.name}[/cyan]")
                    self._log("  Press [bold]R[/bold] to run, [bold]I[/bold] to inspect")
                else:
                    # Continue auto-running
                    self.action_run_step()
            # If not auto-running, we just pause at the next step (advance already happened)
        elif self._auto_running:
            self._auto_running = False

    def _advance_to_next(self) -> None:
        idx = self.current_step_index + 1
        while idx < len(self.job.steps):
            step = self.job.steps[idx]
            step.status = StepStatus.PAUSED
            self.current_step_index = idx
            self._refresh_step(idx)
            self._select_step(idx)
            self._update_detail_panel()

            if step.is_action and self._auto_running:
                # In auto-run mode, try to run action equivalents automatically
                equiv = get_action_equivalent(step.action_ref, step.action_with)
                if equiv:
                    self._log(f"\n[dim]Auto-running equivalent for: {step.name}[/dim]")
                    self.action_run_step()
                    return
                else:
                    # Can't auto-run unknown actions, pause
                    self._auto_running = False
                    self._log(f"\n[cyan]● Paused at action: {step.name}[/cyan]")
                    self._log("  [yellow]No local equivalent — cannot auto-run[/yellow]")
                    self._log("  Press [bold]S[/bold] to skip, [bold]I[/bold] to shell in")
                    return

            if not self._auto_running:
                if step.is_action:
                    equiv = get_action_equivalent(step.action_ref, step.action_with)
                    self._log(f"\n[cyan]● Paused at action: {step.name}[/cyan]")
                    if equiv:
                        self._log(f"  [green]Local equivalent:[/green] {equiv[0]}")
                        self._log("  Press [bold]R[/bold] to run equivalent, [bold]S[/bold] to skip, [bold]I[/bold] to shell in")
                    else:
                        self._log("  [yellow]No local equivalent known.[/yellow]")
                        self._log("  Press [bold]S[/bold] to skip, [bold]I[/bold] to shell in")
                else:
                    self._log(f"\n[cyan]● Paused at: {step.name}[/cyan]")
            return
        # All steps done
        self.current_step_index = len(self.job.steps)
        self._log("\n[bold green]━━━ All steps complete! ━━━[/bold green]")
        self._log("Press [bold]Q[/bold] to quit.")
        self._auto_running = False

    def action_skip_step(self) -> None:
        if self.running:
            self.notify("Step is still running...", severity="information")
            return
        step = self._current_step()
        if step is None:
            return
        self._quit_pending = False
        step.status = StepStatus.SKIPPED
        self._refresh_step(self.current_step_index)
        self._log(f"[dim]  ⊘ Skipped: {step.name}[/dim]")
        self._record_action("skip", step.name)
        self._advance_to_next()

    def action_shell_in(self) -> None:
        if self.engine.container is None:
            self.notify("No container running", severity="error")
            return
        container_id = self.engine.container_id
        step = self._current_step()

        # Build docker exec command with step's env vars and working directory
        cmd = ["docker", "exec", "-it"]
        if step:
            for k, v in step.env.items():
                cmd.extend(["-e", f"{k}={v}"])
            workdir = step.working_directory or "/workspace"
            cmd.extend(["-w", workdir])
        else:
            cmd.extend(["-w", "/workspace"])

        self._log("\n[cyan]Launching interactive shell... (type 'exit' to return)[/cyan]")
        with self.suspend():
            ret = subprocess.call(cmd + [container_id, "/bin/bash"])
            if ret != 0:
                subprocess.call(cmd + [container_id, "/bin/sh"])
        self._record_action("shell_in", step.name if step else "unknown")
        self._log("[cyan]Returned from shell.[/cyan]\n")

    def action_toggle_breakpoint(self) -> None:
        try:
            list_view = self.query_one("#step-list", ListView)
        except NoMatches:
            return
        highlighted = list_view.index
        if highlighted is not None and 0 <= highlighted < len(self.job.steps):
            step = self.job.steps[highlighted]
            step.breakpoint = not step.breakpoint
            tag = "set" if step.breakpoint else "removed"
            self._log(f"[magenta]  Breakpoint {tag}: {step.name}[/magenta]")
            if step.breakpoint:
                self._log("[dim]  Press N to auto-run all steps until this breakpoint.[/dim]")
            self._refresh_step(highlighted)

    def action_run_to_breakpoint(self) -> None:
        if self.running:
            self.notify("Step is still running...", severity="information")
            return
        step = self._current_step()
        if step is None:
            return
        self._quit_pending = False
        self._auto_running = True
        self._log("\n[dim]Auto-running to next breakpoint...[/dim]")
        self.action_run_step()

    def _record_action(self, action: str, step_name: str, command: str = "") -> None:
        import time
        self.session_log.append({
            "time": time.strftime("%H:%M:%S"),
            "action": action,
            "step": step_name,
            "command": command,
        })

    def _save_session(self, path: str) -> None:
        lines = [
            "#!/usr/bin/env bash",
            f"# PipeStep session recording — {self.workflow.name} / {self.job.name}",
            f"# Image: {self.job.docker_image}",
            f"# Recorded: {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        for entry in self.session_log:
            lines.append(f"# [{entry['time']}] {entry['action']}: {entry['step']}")
            if entry["command"]:
                lines.append(entry["command"])
            lines.append("")
        import os
        with open(path, "w") as f:
            f.write("\n".join(lines))
        os.chmod(path, 0o755)

    def action_quit_app(self) -> None:
        if self.running:
            self.notify("Step is running. Press Q again to force quit.", severity="warning")
            if self._quit_pending:
                self._do_quit()
            else:
                self._quit_pending = True
            return
        if not self._quit_pending:
            self._quit_pending = True
            self.notify("Press Q again to quit and destroy the container.", severity="warning")
            return
        self._do_quit()

    def _do_quit(self) -> None:
        if self.session_log:
            session_path = f"pipestep-session-{__import__('time').strftime('%Y%m%d-%H%M%S')}.sh"
            self._save_session(session_path)
            self._log(f"\n[green]Session saved to {session_path}[/green]")
        self._log("\nCleaning up container...")
        self.engine.cleanup()
        self.exit()
