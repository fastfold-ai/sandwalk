"""Mixin: _resume_session, _reset_usage_counters, _new_session, _delete_session."""

from __future__ import annotations


class _SessionLifecycleMixin:
    def _reset_transcript_canvas(self) -> None:
        """Clear the TUI to a fresh banner — like starting a new session."""
        transcript = getattr(self, "transcript", None)
        if transcript is not None:
            transcript.clear()
            seed = getattr(self, "_seed_transcript_banner", None)
            if callable(seed):
                seed()
            return
        try:
            self.console.clear()
            from cli.banner import print_banner

            print_banner(self.session.config, console=self.console)
            self.console.print()
        except Exception:
            pass

    def _session_display_title(self, *, heal: bool = True) -> str:
        """Readable session title; heal instruction-echo junk from auto-title."""
        from agent_server.title import fallback_title_from_query, is_placeholder_title

        traj = getattr(getattr(self, "agent", None), "trajectory", None)
        if traj is None:
            return "untitled"
        title = str(getattr(traj, "title", None) or "").strip()
        if title and not is_placeholder_title(title):
            return title
        turns = list(getattr(traj, "turns", None) or [])
        query = ""
        if turns:
            query = str(getattr(turns[0], "query", "") or "").strip()
        healed = fallback_title_from_query(query) if query else ""
        if healed and heal:
            traj.title = healed
            try:
                traj.save()
            except Exception:
                pass
            return healed
        return healed or title or "untitled"

    def _print_resumed_session_line(
        self,
        session_id: str,
        title: str,
        n: int,
        *,
        label: str = "Resumed session",
    ) -> None:
        """Resume status with left pad on every wrapped line (+ image chips)."""
        from rich.markup import escape

        from ui.terminal.attachments import chipify_uploads_for_display

        display = chipify_uploads_for_display(str(title or ""))
        sid = str(session_id or "")
        line = f"{label} {sid} — {display} ({n} turns)"
        transcript = getattr(self, "transcript", None)
        if transcript is not None:
            # Own wrap so continuation lines keep LEFT_PAD (Rich drops it).
            transcript.append_text(line, kind="resume")
            return
        self.console.print(
            f"  [green]{escape(label)}[/green] [bold]{escape(sid)}[/bold] — "
            f"{escape(display)} ({n} turns)"
        )

    def _resume_session(self, identifier: str = None):
        """Resume a previous session and replay its history into the TUI."""
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
            self._last_response = None
            n = len(self.agent.trajectory.turns)
            title = self._session_display_title()
            # Clear the prior active session's scrollback, then show resumed turns.
            self._reset_transcript_canvas()
            self._print_resumed_session_line(session_id, title, n, label="Resumed")
            self._render_resumed_history(
                self.console.width, turns=self.agent.trajectory.turns
            )
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

        self._reset_transcript_canvas()
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
