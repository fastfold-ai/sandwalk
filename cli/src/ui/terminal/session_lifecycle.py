"""Mixin: _resume_session, _reset_usage_counters, _new_session, _delete_session."""

from __future__ import annotations

class _SessionLifecycleMixin:
    def _resume_session(self, identifier: str = None):
        """Resume a previous session."""
        from agent.loop import AgentLoop
        from agent.trajectory import Trajectory

        sessions = Trajectory.list_sessions()
        if not sessions:
            self.console.print("  [dim]No saved sessions.[/dim]")
            return

        if identifier is None:
            # Show picker
            self._list_sessions()
            try:
                choice = self._prompt_session.prompt(
                    [("class:prompt", "  Select session: ")],
                ).strip()
            except (EOFError, KeyboardInterrupt):
                return
            if not choice:
                return
            identifier = choice

        session_id = self._resolve_session_identifier(identifier, sessions)
        if not session_id:
            return

        try:
            self.agent = AgentLoop.resume(self.session, session_id)
            self._restore_usage_from_trajectory()
            n = len(self.agent.trajectory.turns)
            title = self.agent.trajectory.title or "untitled"
            self.console.print(f"  [green]Resumed[/green] [bold]{session_id}[/bold] — {title} ({n} turns)")
            self._render_resumed_history(self.console.width, turns=self.agent.trajectory.turns)
        except FileNotFoundError:
            self.console.print(f"  [yellow]Session '{session_id}' not found.[/yellow]")

    def _reset_usage_counters(self) -> None:
        """Reset per-session usage counters for a fresh session."""
        with self._run_lock:
            self._session_sdk_calls = 0
            self._session_sdk_input_tokens = 0
            self._session_sdk_output_tokens = 0
            self._session_sdk_cache_read_tokens = 0
            self._session_sdk_cache_creation_tokens = 0
            self._session_sdk_cost_usd = 0.0
            self._session_sdk_total_cost_usd = 0.0
            self._session_sdk_extra_server_tool_cost_usd = 0.0
            self._session_sdk_models = set()
            self._session_sdk_turn_rows = []

    def _new_session(self) -> None:
        """Start a brand-new local session."""
        from agent.loop import AgentLoop

        # Clear visible transcript so /new feels like a blank chat start.
        self.console.clear()
        try:
            # Mirror startup UX when beginning a fresh session.
            from cli import print_banner
            # Add slight top margin so content isn't pinned to row 1.
            self.console.print()
            self.console.print()
            self.console.print()
            self.console.print()
            self.console.print()
            self.console.print()
            print_banner(self.session.config)
            self.console.print()
        except Exception:
            pass
        self.agent = AgentLoop(self.session)
        self._reset_usage_counters()
        self._last_response = None
        self.console.print(
            f"  [green]Started new session[/green] [bold]{self.agent.trajectory.session_id}[/bold]."
        )

    def _delete_session(self, identifier: str | None = None) -> None:
        """Delete a saved session (and trace file) by id, prefix, number, or 'last'."""
        from agent.trajectory import Trajectory

        sessions = Trajectory.list_sessions()
        if not sessions:
            self.console.print("  [dim]No saved sessions.[/dim]")
            return

        if identifier is None:
            self._list_sessions()
            try:
                choice = self._prompt_session.prompt(
                    [("class:prompt", "  Delete session: ")],
                ).strip()
            except (EOFError, KeyboardInterrupt):
                return
            if not choice:
                return
            identifier = choice

        session_id = self._resolve_session_identifier(identifier, sessions)
        if not session_id:
            return

        try:
            result = Trajectory.delete_session(session_id)
        except FileNotFoundError:
            self.console.print(f"  [yellow]Session '{session_id}' not found.[/yellow]")
            return

        trace_note = " and trace" if result.get("trace_deleted") else ""
        self.console.print(
            f"  [green]Deleted[/green] [bold]{session_id}[/bold]{trace_note}."
        )

        current_session_id = (
            self.agent.trajectory.session_id
            if hasattr(self, "agent") and getattr(self.agent, "trajectory", None)
            else None
        )
        if current_session_id == session_id:
            self._new_session()
            self.console.print(
                f"  [dim]Current session was deleted; switched to new session {self.agent.trajectory.session_id}.[/dim]"
            )
