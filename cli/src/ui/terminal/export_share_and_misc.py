"""Mixin: _export_share, _export_notebook, _compact_context, _run_shell."""

from __future__ import annotations

from pathlib import Path
import re
import shlex
import subprocess
import threading
import time


class _ExportShareAndMiscMixin:
    def _export_share(self, filename: str = None):
        """Export transcript and share to configured Slack report channel."""
        path = self._export_session(filename)
        if path is None:
            return

        try:
            markdown = path.read_text(encoding="utf-8")
        except Exception as exc:
            self.console.print(f"  [red]Could not read export file:[/red] {exc}")
            return

        self.console.print("  [cyan]Sending report to Slack...[/cyan]")
        payload = self._send_export_to_slack(markdown, path.name)
        if bool(payload.get("ok")):
            channel_id = payload.get("channel_id") or "(unknown)"
            library_item_id = payload.get("library_item_id")
            self.console.print(f"  [green]Shared to Slack channel[/green] {channel_id}")
            if library_item_id:
                self.console.print(f"  [green]Saved to library item[/green] {library_item_id}")
            return

        self.console.print(f"  [yellow]{payload.get('message') or 'Failed to share report.'}[/yellow]")
        if bool(payload.get("needs_slack_setup")):
            setup = payload.get("setup_instructions") or (
                "Configure Slack at https://cloud.fastfold.ai/integrations/slack "
                "and set a channel for the agent_cli_report mode."
            )
            self.console.print(f"  [dim]{setup}[/dim]")

    def _export_notebook(self, filename: str = None):
        """Export the current session trace as a Jupyter notebook."""
        if not hasattr(self, 'agent') or not hasattr(self.agent, 'trace_store'):
            self.console.print("  [dim]No trace data available.[/dim]")
            return

        trace_store = self.agent.trace_store
        if not trace_store.path.exists():
            self.console.print("  [dim]No trace data yet. Run a query first.[/dim]")
            return

        try:
            from reports.notebook import save_notebook, trace_to_notebook
        except ImportError:
            self.console.print("  [red]nbformat required.[/red] pip install nbformat")
            return

        nb = trace_to_notebook(trace_store.path)

        output_dir = Path.cwd() / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            path = output_dir / filename
        else:
            import re
            slug = re.sub(r"[^a-zA-Z0-9]+", "_", trace_store.session_id).strip("_")
            path = output_dir / f"session_{slug}.ipynb"

        save_notebook(nb, path)
        abs_path = str(path.resolve())
        self.console.print("  [green]Notebook exported to[/green]")
        self.console.print(f"  {abs_path}")
        self.console.print(f"  [dim]Open with: jupyter lab {path}[/dim]")

    def _compact_context(self, instructions: str = None):
        """Summarize session trajectory; LLM call runs off the UI thread.

        Blocking ``llm.chat`` on the enter handler freezes the fullscreen TUI
        (same class of bug as ``/doctor``). Background the work and animate a
        status line in the transcript until the summary lands.
        """
        if not hasattr(self, "agent") or not self.agent.trajectory.turns:
            self.console.print("  [dim]Nothing to compact yet.[/dim]")
            return

        trajectory = self.agent.trajectory
        n_turns = len(trajectory.turns)
        if n_turns <= 2:
            self.console.print("  [dim]Session too short to compact.[/dim]")
            return
        if bool(getattr(self, "_compact_running", False)):
            self.console.print("  [dim]Compaction already running…[/dim]")
            return

        context = trajectory.context_for_planner()
        focus = f"\nFocus: {instructions}" if instructions else ""
        prompt = (
            f"Summarize this research session into a brief paragraph that preserves "
            f"key findings, entities, and conclusions. Be specific about results and numbers.{focus}\n\n"
            f"{context}"
        )
        entities = list(trajectory.entities())
        last_turn = trajectory.turns[-1]
        session = self.session

        self._compact_running = True
        stop_spin = threading.Event()
        from ui.status.spinners import SPINNERS

        try:
            style = str(session.config.get("ui.spinner") or "benzene_breathing")
        except Exception:  # noqa: BLE001
            style = "benzene_breathing"
        spinner_conf = SPINNERS.get(style) or SPINNERS["benzene_breathing"]
        frames = [str(f) for f in spinner_conf.get("frames", []) if str(f)] or ["·"]
        interval_s = max(0.05, int(spinner_conf.get("interval_ms", 125)) / 1000.0)

        transcript = getattr(self, "transcript", None)
        status_entry = None
        if transcript is not None:
            status_entry = transcript.append_text(
                f"  {frames[0]} Compacting session…", kind="system"
            )
        else:
            self.console.print(f"  [cyan]{frames[0]}[/cyan] Compacting session…")

        def _set_status(text: str) -> None:
            if status_entry is not None and transcript is not None:
                transcript.update_text(status_entry, text)
                return
            if status_entry is None:
                self.console.print(text)

        def _spin() -> None:
            i = 0
            while not stop_spin.wait(interval_s):
                _set_status(f"  {frames[i % len(frames)]} Compacting session…")
                i += 1

        def _worker() -> None:
            err = None
            summary = ""
            try:
                llm = session.get_llm()
                response = llm.chat(
                    system=(
                        "You are a research session summarizer. "
                        "Be concise but preserve specific results."
                    ),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=1200,
                )
                summary = response.content if hasattr(response, "content") else str(response)
                if not str(summary).strip():
                    raise ValueError("Summarizer returned empty output")
            except Exception as exc:  # noqa: BLE001
                err = exc

            stop_spin.set()
            try:
                if err is not None:
                    _set_status(f"  Compact failed: {err}")
                    self.console.print(f"  [red]Compact failed:[/red] {err}")
                    return
                from agent.trajectory import Turn

                summary_turn = Turn(
                    query="[session summary]",
                    answer=summary,
                    entities=entities,
                    tools_used=[],
                    timestamp=time.time(),
                )
                trajectory.turns = [summary_turn, last_turn]
                try:
                    if getattr(trajectory, "session_id", None):
                        trajectory.save()
                except Exception:  # noqa: BLE001
                    pass
                _set_status("  Compaction complete")
                self.console.print(
                    f"  [green]Compacted[/green] {n_turns} turns → 2 (summary + last)"
                )
            finally:
                self._compact_running = False
                try:
                    self._invalidate_prompt_toolbar(retries=2)
                except Exception:  # noqa: BLE001
                    pass
                app = getattr(self, "_transcript_app", None)
                try:
                    if app is not None and getattr(app, "is_running", False):
                        app.invalidate()
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=_spin, daemon=True, name="sandwalk-compact-spin").start()
        threading.Thread(target=_worker, daemon=True, name="sandwalk-compact").start()

    def _run_shell(self, cmd: str):
        """Execute a shell command and display output."""
        if not cmd:
            self.console.print("  [dim]Usage: !<command>  (e.g., !ls .)[/dim]")
            return

        from tools.shell import _is_blocked
        blocked_reason = _is_blocked(cmd)
        if blocked_reason:
            self.console.print(f"  [yellow]Command blocked:[/yellow] {blocked_reason}")
            return

        try:
            args = shlex.split(cmd, posix=True)
        except ValueError as e:
            self.console.print(f"  [red]Invalid command syntax:[/red] {e}")
            return

        # Expand user-home shorthand for convenience when not using a shell.
        args = [str(Path(arg).expanduser()) if arg.startswith("~") else arg for arg in args]

        try:
            result = subprocess.run(
                args,
                shell=False,
                cwd=str(Path.cwd()),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.stdout:
                self.console.print(result.stdout.rstrip())
            if result.stderr:
                self.console.print(f"[red]{result.stderr.rstrip()}[/red]")
            if result.returncode != 0 and not result.stderr:
                self.console.print(f"  [dim]Exit code: {result.returncode}[/dim]")
        except subprocess.TimeoutExpired:
            self.console.print("  [yellow]Command timed out (30s limit).[/yellow]")
        except Exception as e:
            self.console.print(f"  [red]Error: {e}[/red]")
