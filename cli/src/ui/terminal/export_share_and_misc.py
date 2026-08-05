"""Mixin: _export_share, _export_notebook, _compact_context, _run_shell."""

from __future__ import annotations

from pathlib import Path
import re
import shlex
import subprocess
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
        """Summarize session trajectory to free context window space."""
        if not hasattr(self, 'agent') or not self.agent.trajectory.turns:
            self.console.print("  [dim]Nothing to compact yet.[/dim]")
            return

        n_turns = len(self.agent.trajectory.turns)
        if n_turns <= 2:
            self.console.print("  [dim]Session too short to compact.[/dim]")
            return

        # Build a summary of the session using the LLM
        context = self.agent.trajectory.context_for_planner()
        focus = f"\nFocus: {instructions}" if instructions else ""
        prompt = (
            f"Summarize this research session into a brief paragraph that preserves "
            f"key findings, entities, and conclusions. Be specific about results and numbers.{focus}\n\n"
            f"{context}"
        )

        try:
            llm = self.session.get_llm()
            response = llm.chat(
                system="You are a research session summarizer. Be concise but preserve specific results.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1200,
            )
            summary = response.content if hasattr(response, "content") else str(response)
            if not summary.strip():
                raise ValueError("Summarizer returned empty output")

            # Replace all turns except the last one with a single summary turn
            from agent.trajectory import Turn
            last_turn = self.agent.trajectory.turns[-1]
            summary_turn = Turn(
                query="[session summary]",
                answer=summary,
                entities=list(self.agent.trajectory.entities()),
                tools_used=[],
                timestamp=time.time(),
            )
            self.agent.trajectory.turns = [summary_turn, last_turn]
            self.console.print(f"  [green]Compacted[/green] {n_turns} turns → 2 (summary + last)")
        except Exception as e:
            self.console.print(f"  [red]Compact failed:[/red] {e}")

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
