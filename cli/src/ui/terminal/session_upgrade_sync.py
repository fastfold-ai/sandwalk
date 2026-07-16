"""Mixin: _run_upgrade, _list_sessions, _sync_sessions, _resolve_session_identifier."""

from __future__ import annotations

import time


class _SessionUpgradeSyncMixin:
    def _run_upgrade(self) -> None:
        """Upgrade CLI installation using the shared uv install flow."""
        try:
            from cli import execute_upgrade
        except Exception as exc:
            self.console.print(f"  [red]Could not load upgrade command:[/red] {exc}")
            return

        ok = execute_upgrade(console_obj=self.console, cfg=self.session.config)
        if ok:
            self.console.print("  [dim]Tip: restart sandwalk to confirm the new version.[/dim]")

    def _list_sessions(self):
        """Show recent saved sessions."""
        from rich.table import Table

        from agent.trajectory import Trajectory

        sessions = Trajectory.list_sessions()
        if not sessions:
            self.console.print("  [dim]No saved sessions.[/dim]")
            return

        def _relative_time(ts: float | int | None) -> str:
            if not isinstance(ts, (int, float)) or ts <= 0:
                return "—"
            age_s = max(0, int(time.time() - float(ts)))
            if age_s < 5:
                return "just now"
            if age_s < 60:
                return f"{age_s}s ago"
            if age_s < 3600:
                return f"{age_s // 60}m ago"
            if age_s < 86400:
                return f"{age_s // 3600}h ago"
            return f"{age_s // 86400}d ago"

        table = Table(title="/sessions", show_lines=False)
        table.add_column("", style="green", no_wrap=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Preview")
        table.add_column("Messages", justify="right", style="magenta")
        table.add_column("Model", style="yellow")
        table.add_column("Last Used", style="dim", no_wrap=True)

        current_session_id = (
            self.agent.trajectory.session_id
            if hasattr(self, "agent") and getattr(self.agent, "trajectory", None)
            else None
        )

        def _preview_text(value: object, max_len: int = 70) -> str:
            # Keep preview strictly single-line so long multiline prompts
            # don't break row layout in the sessions table.
            normalized = " ".join(str(value or "untitled").split())
            return normalized[:max_len] if normalized else "untitled"

        for s in sessions[:20]:
            sid = str(s.get("session_id", "?"))
            title = _preview_text(s.get("title"))
            model = str(s.get("model") or "—")
            n_turns = int(s.get("n_turns") or 0)
            updated_at = s.get("updated_at", s.get("created_at"))
            marker = "*" if current_session_id == sid else ""
            table.add_row(
                marker,
                sid,
                title,
                str(n_turns),
                model,
                _relative_time(updated_at),
            )

        self.console.print()
        self.console.print(table)
        self.console.print(
            "\n  [dim]/resume <id-or-prefix> to continue · /resume <number> from table · /sessions delete <id|number|last> to remove · /sync to share with UI[/dim]"
        )

    def _sync_sessions(self, *, force: bool = False) -> None:
        """Import legacy JSONL CLI sessions into the shared SQLite store for the UI."""
        from agent_server.session_sync import sync_jsonl_sessions

        self.console.print(
            "  [cyan]Syncing legacy CLI sessions into the shared UI database…[/cyan]"
            + (" [dim](force)[/dim]" if force else "")
        )
        result = sync_jsonl_sessions(force=force)
        self.console.print(
            "  [green]Sync complete.[/green] "
            f"scanned={result.scanned} imported={result.imported} "
            f"updated={result.updated} skipped={result.skipped} failed={result.failed}"
        )
        if result.failed and result.details:
            for line in result.details:
                if "failed" in line:
                    self.console.print(f"  [yellow]{line}[/yellow]")
        self.console.print(
            "  [dim]Start the UI with `sandwalk serve` + local-web to continue these chats there.[/dim]"
        )

    def _resolve_session_identifier(self, identifier: str, sessions: list[dict]) -> str | None:
        """Resolve number/id/prefix/last into a concrete session id."""
        token = str(identifier or "").strip()
        if not token:
            self.console.print("  [dim]No session selected.[/dim]")
            return None

        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(sessions):
                return str(sessions[idx]["session_id"])
            self.console.print("  [dim]Invalid number.[/dim]")
            return None

        if token == "last":
            return str(sessions[0]["session_id"])

        matches = [s for s in sessions if str(s.get("session_id", "")).startswith(token)]
        if not matches:
            self.console.print(f"  [yellow]Session '{token}' not found.[/yellow]")
            return None
        if len(matches) > 1:
            options = ", ".join(str(s.get("session_id", "")) for s in matches[:5])
            self.console.print(
                f"  [yellow]Session prefix '{token}' is ambiguous.[/yellow] Matches: {options}"
            )
            return None
        return str(matches[0]["session_id"])
