"""Mixin: _show_usage, _show_tasks."""

from __future__ import annotations

import time


class _UsageTasksDisplayMixin:
    def _show_usage(self):
        """Show token usage and cost for this session."""
        with self._run_lock:
            sdk_calls = int(self._session_sdk_calls)
            sdk_in = int(self._session_sdk_input_tokens)
            sdk_out = int(self._session_sdk_output_tokens)
            sdk_cache_read = int(self._session_sdk_cache_read_tokens)
            sdk_cache_create = int(self._session_sdk_cache_creation_tokens)
            sdk_models = sorted(self._session_sdk_models)
            sdk_rows = list(self._session_sdk_turn_rows)

        if sdk_calls > 0:
            from rich.table import Table

            table = Table(title="Session SDK Usage", show_lines=False)
            table.add_column("Turn", style="cyan", no_wrap=True)
            table.add_column("Input", justify="right", style="green")
            table.add_column("Output", justify="right", style="green")
            table.add_column("Cache Read", justify="right", style="dim")
            table.add_column("Cache Create", justify="right", style="dim")
            table.add_column("Models", style="dim")

            for row in sdk_rows:
                models = ", ".join(row.get("models", [])) or "-"
                table.add_row(
                    str(row.get("turn", "")),
                    f"{int(row.get('input_tokens', 0)):,}",
                    f"{int(row.get('output_tokens', 0)):,}",
                    f"{int(row.get('cache_read_tokens', 0)):,}",
                    f"{int(row.get('cache_creation_tokens', 0)):,}",
                    models,
                )

            total_models = ", ".join(sdk_models) if sdk_models else "-"
            table.add_row(
                "TOTAL",
                f"{sdk_in:,}",
                f"{sdk_out:,}",
                f"{sdk_cache_read:,}",
                f"{sdk_cache_create:,}",
                total_models,
                style="bold",
            )
            self.console.print(table)
            return

        # Fallback for legacy non-SDK flows.
        llm = self.session.get_llm()
        if hasattr(llm, "usage") and llm.usage.calls:
            self.console.print(f"  {llm.usage.summary()}")
            return
        self.console.print("  [dim]No LLM calls made yet.[/dim]")

    def _show_tasks(self, force_refresh: bool = False):
        """Show current background task watcher state from the SDK runner."""
        runner = None
        if hasattr(self, "agent"):
            runner = getattr(self.agent, "_runner", None)
        if runner is None or not hasattr(runner, "get_background_watch_status"):
            self.console.print("  [dim]No background watcher available in this session.[/dim]")
            return

        # Reconcile pending tasks before rendering so /tasks reflects
        # any just-completed tasks detected by the local output-file probe.
        if hasattr(runner, "refresh_background_watch_status"):
            runner.refresh_background_watch_status(force=force_refresh)

        statuses = runner.get_background_watch_status(include_inactive=True)
        if not statuses:
            self.console.print("  [dim]No background tasks tracked yet.[/dim]")
            return

        from rich.table import Table
        table = Table(title="Background Task Watchers", show_lines=False)
        table.add_column("Session", style="cyan", no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Watcher", style="dim")
        table.add_column("Attempts", style="dim")
        table.add_column("Pending", style="yellow")
        table.add_column("Completed", style="green")
        table.add_column("Updated", style="dim")

        for item in statuses:
            session_id = str(item.get("session_id") or "")
            session_short = session_id[:8] + "…" if len(session_id) > 8 else session_id
            status = str(item.get("status") or "unknown")
            if status == "running":
                status_markup = "[cyan]running[/cyan]"
            elif status == "completed":
                status_markup = "[green]completed[/green]"
            elif status == "timeout":
                status_markup = "[yellow]timeout[/yellow]"
            else:
                status_markup = f"[red]{status}[/red]"

            watcher_alive = bool(item.get("watcher_alive"))
            watcher_text = "alive" if watcher_alive else "stopped"
            attempts_text = str(int(item.get("connection_attempts") or 0))
            disconnect_reason = str(item.get("last_disconnect_reason") or "").strip()
            if disconnect_reason and disconnect_reason != "unknown":
                watcher_text = f"{watcher_text} ({disconnect_reason})"

            pending_ids = [str(x) for x in (item.get("pending_task_ids") or []) if str(x)]
            completed_ids = [str(x) for x in (item.get("completed_task_ids") or []) if str(x)]

            def _compact_ids(ids: list[str]) -> str:
                if not ids:
                    return "—"
                shown = [i[:8] + "…" if len(i) > 8 else i for i in ids[:3]]
                suffix = f" (+{len(ids) - 3})" if len(ids) > 3 else ""
                return ", ".join(shown) + suffix

            updated_at = item.get("last_update_at")
            if isinstance(updated_at, (int, float)) and updated_at > 0:
                age_s = max(0, int(time.time() - updated_at))
                if age_s < 60:
                    updated_text = f"{age_s}s ago"
                elif age_s < 3600:
                    updated_text = f"{age_s // 60}m ago"
                else:
                    updated_text = f"{age_s // 3600}h ago"
            else:
                updated_text = "—"

            table.add_row(
                session_short or "—",
                status_markup,
                watcher_text,
                attempts_text,
                _compact_ids(pending_ids),
                _compact_ids(completed_ids),
                updated_text,
            )

        self.console.print(table)
