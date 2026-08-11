"""BackgroundWatchMixin: background task notifications and local output-file polling.

Split out of ``agent/runner.py`` (package conversion) to keep files under the
project line-count limit. Helper lookups route through ``agent.runner`` (via
``_runner_mod``, mirroring the pattern documented in ``agent/runner_helpers.py``)
instead of direct imports, so existing ``agent.runner.<name>`` monkeypatches in
the test suite keep resolving to the live implementation.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from agent import runner as _runner_mod


class BackgroundWatchMixin:
    """Background task watcher status, local output-file probing, and notifications."""

    def _notify_terminal_task_completion(
        self,
        task_id: str,
        status: str,
        summary: str = "",
        output_file: str = "",
    ) -> None:
        """Emit a desktop notification in Warp on task completion."""
        if self._headless:
            return
        status_norm = str(status or "").strip().lower()
        if status_norm not in {"completed", "failed", "stopped"}:
            return
        if not _runner_mod._is_warp_terminal_env():
            return

        title = _runner_mod._sanitize_notification_text(f"Fastfold task {status_norm}")
        body_parts = []
        if task_id:
            body_parts.append(task_id)
        if summary:
            body_parts.append(summary)
        if output_file:
            body_parts.append(output_file)
        body = _runner_mod._sanitize_notification_text(
            " - ".join(body_parts) if body_parts else status_norm
        )
        if not body:
            return

        # Warp desktop notification via OSC 777.
        sys.stdout.write(f"\033]777;notify;{title};{body}\007")
        sys.stdout.flush()

    def refresh_background_watch_status(self, force: bool = False) -> None:
        """Reconcile pending tasks for the /tasks view via local output-file probe."""
        candidates: list[tuple[str, set[str]]] = []
        with self._bg_watch_lock:
            for session_id, state in self._bg_watch_state.items():
                pending = {
                    str(t).strip() for t in (state.get("pending_task_ids") or [])
                    if str(t).strip()
                }
                if not pending:
                    continue
                candidates.append((session_id, pending))

        if not candidates:
            return

        from ui.traces import TraceRenderer
        for session_id, pending in candidates:
            if not pending:
                continue
            transcript = getattr(self.session, "transcript", None)
            sink = None
            if transcript is not None:
                from ui.terminal.transcript.sink import TranscriptSink

                sink = TranscriptSink(transcript)
            trace_renderer = TraceRenderer(
                self.session.console,
                config=getattr(self.session, "config", None),
                expand_store=getattr(self.session, "tool_expand_store", None),
                sink=sink,
            )
            self._probe_local_task_outputs(session_id, pending, trace_renderer)

    def _probe_local_task_outputs(self, session_id: str, remaining: set[str], trace_renderer) -> None:
        """Fallback completion detector by reading known local task output files."""
        with self._bg_watch_lock:
            state = self._bg_watch_state.get(session_id, {})
            output_files = dict(state.get("output_files", {}))

        if not output_files:
            return

        completed_now: list[tuple[str, str, str]] = []
        for task_id in list(remaining):
            output_file = str(output_files.get(task_id) or "").strip()
            if not output_file:
                output_file = _runner_mod._discover_local_task_output_file(task_id)
                if output_file:
                    with self._bg_watch_lock:
                        state = self._bg_watch_state.get(session_id, {})
                        state_output_files = dict(state.get("output_files", {}))
                        state_output_files[task_id] = output_file
                        state["output_files"] = state_output_files
                        state["last_update_at"] = time.time()
                        self._bg_watch_state[session_id] = state
            if not output_file:
                continue
            path = Path(output_file)
            if not path.exists():
                discovered = _runner_mod._discover_local_task_output_file(task_id)
                if discovered and discovered != output_file:
                    path = Path(discovered)
                    output_file = discovered
                    with self._bg_watch_lock:
                        state = self._bg_watch_state.get(session_id, {})
                        state_output_files = dict(state.get("output_files", {}))
                        state_output_files[task_id] = output_file
                        state["output_files"] = state_output_files
                        state["last_update_at"] = time.time()
                        self._bg_watch_state[session_id] = state
            if not path.exists():
                continue
            try:
                text = path.read_text(errors="replace")
            except Exception:
                continue

            # SDK output files include terminal metadata/footer when completed.
            exit_code_match = re.search(r"exit_code:\s*(-?\d+)", text)
            if not exit_code_match:
                continue
            exit_code = exit_code_match.group(1)
            status = "completed" if exit_code == "0" else "failed"
            summary = (
                f"Detected via local output probe (exit_code={exit_code})."
            )
            completed_now.append((task_id, status, summary))

        if not completed_now:
            return

        with self._bg_watch_lock:
            state = self._bg_watch_state.get(session_id, {})
            pending = set(state.get("pending_task_ids", []))
            completed = list(state.get("completed_task_ids", []))
            for task_id, status, summary in completed_now:
                if task_id in remaining:
                    remaining.remove(task_id)
                pending.discard(task_id)
                if task_id not in completed:
                    completed.append(task_id)
                if not self._headless:
                    trace_renderer.render_task_notification(
                        task_id,
                        status,
                        summary,
                        str(output_files.get(task_id) or ""),
                    )
                self._notify_terminal_task_completion(
                    task_id,
                    status,
                    summary,
                    str(output_files.get(task_id) or ""),
                )
            state["pending_task_ids"] = sorted(pending)
            state["completed_task_ids"] = completed
            state["last_update_at"] = time.time()
            self._bg_watch_state[session_id] = state

    def get_background_watch_status(self, include_inactive: bool = True) -> list[dict]:
        """Return snapshot status for background task watchers."""
        with self._bg_watch_lock:
            rows: list[dict] = []
            for session_id, state in self._bg_watch_state.items():
                thread = self._bg_watchers.get(session_id)
                watcher_alive = bool(thread and thread.is_alive())
                if not include_inactive and not watcher_alive:
                    continue
                row = dict(state)
                row["session_id"] = session_id
                row["watcher_alive"] = watcher_alive
                rows.append(row)
        rows.sort(key=lambda r: float(r.get("last_update_at") or 0.0), reverse=True)
        return rows
