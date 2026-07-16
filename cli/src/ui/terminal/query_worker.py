"""Mixin: _run_query_worker, _current_placeholder, _advance_suggestion, _update_suggestions, _refresh_cli_specialist_label, _refresh_cli_sandbox_label."""

from __future__ import annotations

import time
from prompt_toolkit.formatted_text import HTML
from ui.terminal.mentions import _extract_llm_suggestions


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
                    self.console.print()
                    result = self._run_with_clarification(
                        query,
                        ctx,
                        progress_callback=_progress_update,
                    )
                    self.console.print()
                except KeyboardInterrupt:
                    self.console.print("\n  [yellow]Interrupted.[/yellow]")
                    result = None
                except Exception as e:
                    self.console.print(f"\n  [red]Execution error:[/red] {e}")
                    result = None

                if result is not None:
                    self._record_sdk_usage(result)
                    self._last_response = result.summary
                    self._update_suggestions(query, result.plan, result)

                with self._run_lock:
                    if self._queued_queries:
                        current = self._queued_queries.popleft()
                    else:
                        self._worker_thread = None
                        self._active_query = None
                        self._active_query_started_at = 0.0
                        self._active_activity = ""
                        self._active_activity_updated_at = 0.0
                        self._active_input_tokens = 0
                        self._active_output_tokens = 0
                        self._active_streamed_chars = 0
                        break
        finally:
            with self._run_lock:
                self._worker_thread = None
                self._active_query = None
                self._active_query_started_at = 0.0
                self._active_activity = ""
                self._active_activity_updated_at = 0.0
                self._active_input_tokens = 0
                self._active_output_tokens = 0
                self._active_streamed_chars = 0

    def _current_placeholder(self):
        """Return the current ghost suggestion as dim placeholder text."""
        text = self._suggestions[self._suggestion_idx % len(self._suggestions)]
        return HTML(f'<style fg="#555555">{text}</style>')

    def _advance_suggestion(self):
        """Move to next ghost suggestion."""
        self._suggestion_idx = (self._suggestion_idx + 1) % len(self._suggestions)

    def _update_suggestions(self, query: str, plan=None, result=None):
        """Replace suggestions with contextual follow-ups based on last query.

        Uses LLM-suggested follow-ups extracted from the synthesis output.
        """
        suggestions = []

        # Extract LLM-suggested follow-ups from synthesis
        if result and hasattr(result, 'summary') and result.summary:
            llm_suggestions = _extract_llm_suggestions(result.summary)
            suggestions.extend(llm_suggestions)

        if suggestions:
            self._suggestions = suggestions[:5]
            self._suggestion_idx = 0
        else:
            self._advance_suggestion()

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
