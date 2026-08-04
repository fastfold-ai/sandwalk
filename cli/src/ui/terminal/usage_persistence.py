"""Mixin: _persist_usage_to_trajectory, _restore_usage_from_trajectory, _toolbar_spinner_markup, _submit_query."""

from __future__ import annotations

import threading
import time


class _UsagePersistenceMixin:
    def _persist_usage_to_trajectory(self) -> None:
        """Persist usage snapshot alongside trajectory metadata for resume."""
        trajectory = getattr(getattr(self, "agent", None), "trajectory", None)
        if trajectory is None:
            return
        snapshot = self._usage_snapshot()
        if hasattr(trajectory, "set_usage_data"):
            trajectory.set_usage_data(snapshot)
            trajectory.save()

    def _restore_usage_from_trajectory(self) -> None:
        """Restore usage counters from persisted session metadata."""
        trajectory = getattr(getattr(self, "agent", None), "trajectory", None)
        if trajectory is None or not hasattr(trajectory, "get_usage_data"):
            return
        raw = trajectory.get_usage_data()
        if not isinstance(raw, dict) or not raw:
            return

        rows_raw = raw.get("sdk_turn_rows")
        rows: list[dict] = rows_raw if isinstance(rows_raw, list) else []
        models_raw = raw.get("sdk_models")
        if isinstance(models_raw, str):
            models = {models_raw} if models_raw else set()
        elif isinstance(models_raw, (list, tuple, set)):
            models = {str(m).strip() for m in models_raw if str(m).strip()}
        else:
            models = set()

        with self._run_lock:
            self._session_sdk_calls = self._coerce_token_count(raw.get("sdk_calls"))
            self._session_sdk_input_tokens = self._coerce_token_count(raw.get("sdk_input_tokens"))
            self._session_sdk_output_tokens = self._coerce_token_count(raw.get("sdk_output_tokens"))
            self._session_sdk_cache_read_tokens = self._coerce_token_count(raw.get("sdk_cache_read_tokens"))
            self._session_sdk_cache_creation_tokens = self._coerce_token_count(raw.get("sdk_cache_creation_tokens"))
            self._session_sdk_cost_usd = self._coerce_cost(raw.get("sdk_cost_usd"))
            self._session_sdk_total_cost_usd = self._coerce_cost(raw.get("sdk_total_cost_usd"))
            self._session_sdk_extra_server_tool_cost_usd = self._coerce_cost(
                raw.get("sdk_extra_server_tool_cost_usd")
            )
            self._session_sdk_models = models
            self._session_sdk_turn_rows = [r for r in rows if isinstance(r, dict)]

    def _toolbar_spinner_markup(self) -> str:
        """OpenCode-like comet / knight-rider scanner for the busy toolbar."""
        from ui.status.scanner import scanner_frame_count, scanner_html

        interval = float(getattr(self, "_toolbar_frame_interval_s", 0.04) or 0.04)
        width = int(getattr(self, "_toolbar_scanner_width", 10) or 10)
        n = scanner_frame_count(width=width)
        frame_idx = int(time.time() / max(0.02, interval)) % n
        return scanner_html(frame_idx, width=width)

    def _submit_query(self, query: str, context: dict) -> None:
        payload = (query, dict(context))
        start_refresh = False
        with self._run_lock:
            worker = self._worker_thread
            if worker and worker.is_alive():
                self._queued_queries.append(payload)
                # Do not print queue notices immediately; users found it
                # confusing when this appears before the prior response.
                # The worker prints a "running queued message" notice right
                # before execution, which naturally appears below the
                # previous response.
                return

            worker = threading.Thread(
                target=self._run_query_worker,
                args=(payload,),
                daemon=True,
                name="ct-query-worker",
            )
            self._worker_thread = worker
            self._active_query = query
            self._active_query_started_at = time.time()
            self._active_activity = "Running..."
            self._active_activity_updated_at = time.time()
            self._active_input_tokens = 0
            self._active_output_tokens = 0
            self._active_streamed_chars = 0
            start_refresh = True
            worker.start()
        if start_refresh:
            self._ensure_live_refresh_thread()
