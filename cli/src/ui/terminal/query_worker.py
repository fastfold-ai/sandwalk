"""Mixin: _run_query_worker and CLI toolbar label refresh helpers."""

from __future__ import annotations

import time


class _QueryWorkerMixin:
    def _run_query_worker(self, first_payload: tuple[str, dict]) -> None:
        current = first_payload
        try:
            while True:
                query, ctx = current
                with self._run_lock:
                    self._active_query = query
                    self._active_query_started_at = time.time()
                    self._active_activity = "Running..."
                    self._active_activity_updated_at = time.time()
                    self._active_input_tokens = 0
                    self._active_output_tokens = 0
                    self._active_streamed_chars = 0

                def _progress_update(event="activity", **payload) -> None:
                    # New callback shape: (event, **payload); keep legacy text-only support.
                    if isinstance(event, dict):
                        merged = dict(event)
                        merged.update(payload)
                        payload = merged
                        event = str(payload.pop("event", "activity"))
                    elif not isinstance(event, str):
                        event = str(event or "")

                    # Visible turn finished (usage footer printed). Clear scanner
                    # before title LLM / store dual-write — those can take seconds.
                    if event in {"turn_complete", "done"}:
                        self._clear_toolbar_busy()
                        return

                    if payload:
                        if "input_tokens" in payload or "output_tokens" in payload:
                            self._set_active_usage(
                                payload.get("input_tokens"),
                                payload.get("output_tokens"),
                                payload.get("cache_read_input_tokens"),
                            )
                        if "streamed_chars" in payload:
                            self._set_active_streamed_chars(payload.get("streamed_chars"))
                        text = payload.get("text") or payload.get("activity")
                        if text:
                            self._set_active_activity(str(text))
                        return

                    # Legacy: callback invoked with a plain status string.
                    if event and event not in {"activity", "usage"}:
                        self._set_active_activity(event)

                try:
                    result = self._run_with_clarification(
                        query,
                        ctx,
                        progress_callback=_progress_update,
                    )
                except KeyboardInterrupt:
                    self.console.print("\n  [yellow]Interrupted.[/yellow]")
                    result = None
                except Exception as e:
                    self.console.print(f"\n  [red]Execution error:[/red] {e}")
                    result = None
                finally:
                    # Always idle the compose scanner when the agent returns —
                    # even if later usage/title work raises or hangs.
                    self._clear_toolbar_busy()

                with self._run_lock:
                    has_queued = bool(self._queued_queries)
                    if has_queued:
                        current = self._queued_queries.popleft()
                    else:
                        current = None

                # Drop the scanner immediately — don't wait for usage bookkeeping.
                if not has_queued:
                    self._clear_toolbar_busy()
                    with self._run_lock:
                        self._worker_thread = None

                if result is not None:
                    self._record_sdk_usage(result)
                    self._last_response = result.summary
                    self._update_suggestions(query, result.plan, result)

                if has_queued and current is not None:
                    self.console.print()
                    continue
                break
        finally:
            with self._run_lock:
                self._worker_thread = None
            # Idempotent if already cleared above.
            if hasattr(self, "_clear_toolbar_busy"):
                self._clear_toolbar_busy()
            else:
                with self._run_lock:
                    self._active_query = None
                    self._active_query_started_at = 0.0
                    self._active_activity = ""
                    self._active_activity_updated_at = 0.0
                    self._active_input_tokens = 0
                    self._active_output_tokens = 0
                    self._active_streamed_chars = 0

    def _current_placeholder(self):
        """Deprecated: ghost-text placeholders were removed from the prompt."""
        return None

    def _advance_suggestion(self):
        """No-op — ghost suggestions are no longer shown in the prompt."""
        return

    def _update_suggestions(self, query: str, plan=None, result=None):
        """No-op — ghost suggestions are no longer shown in the prompt."""
        return

    def _refresh_cli_specialist_label(self) -> None:
        """Cache active specialist name for the bottom toolbar."""
        try:
            from agent.specialists_manage import get_active_specialist

            # Always read from disk so /specialist use|clear updates immediately
            # even when session.config is an older in-memory snapshot.
            active = get_active_specialist()
            self._cli_specialist_label = active.name if active else None
        except Exception:
            self._cli_specialist_label = None

    def _refresh_cli_sandbox_label(self) -> None:
        """Cache sandbox backend label for the bottom toolbar."""
        try:
            from agent.sandbox_manage import sandbox_toolbar_label

            # Always read from disk so /sandbox updates apply immediately.
            self._cli_sandbox_label = sandbox_toolbar_label()
        except Exception:
            self._cli_sandbox_label = "Local Sandbox"
