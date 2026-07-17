"""EventProcessor construction, progress emission, and spinner/usage bookkeeping."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from agent.deepagents_runtime.event_text import _usage_from_message


class EventProcessorCoreMixin:
    """Owns state setup, progress forwarding, spinner control, and usage totals."""

    def __init__(
        self,
        *,
        trace_renderer=None,
        headless: bool = False,
        trace_events: list[dict] | None = None,
        thinking_status=None,
        allow_live_spinner: bool = True,
        runner=None,
        on_activity=None,
        code_trace_buffer: list[dict] | None = None,
        display_name_map: dict[str, str] | None = None,
        group_tools: bool = True,
        tool_detail_limit: int = 8,
    ) -> None:
        self.trace_renderer = trace_renderer
        self.headless = headless
        self.trace_events = trace_events
        self.allow_live_spinner = allow_live_spinner
        self.runner = runner
        self.on_activity = on_activity
        self.code_trace_buffer = code_trace_buffer
        self.display_name_map = display_name_map or {}
        self.group_tools = group_tools

        self.full_text: list[str] = []
        self.tool_calls: list[dict] = []
        self.inflight: dict[str, dict] = {}
        self.streamed_len = 0
        self.model_call_count = 0
        self.code_cursor = 0
        self.spinner = {"obj": thinking_status}
        self.group = {"active": False, "count": 0, "errors": 0, "start": 0.0}
        # Trailing-detail buffer: the most recent `detail_window` completed tools
        # are held back and shown in full; as newer tools complete, older ones
        # spill out of the window and are flushed as compact, still-named lines.
        self.pending: list[dict] = []
        self.detail_window = max(1, int(tool_detail_limit))
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }

    def _emit_progress(self, event: str, **payload) -> None:
        if not self.on_activity:
            return
        try:
            self.on_activity(event, **payload)
            return
        except TypeError:
            pass
        except Exception:
            return
        if event == "activity":
            text = str(payload.get("text") or "").strip()
            if text:
                with suppress(Exception):
                    self.on_activity(text)

    def _stop_spinner(self) -> None:
        if self.spinner["obj"] is not None:
            with suppress(Exception):
                self.spinner["obj"].stop()
            self.spinner["obj"] = None
            if self.runner is not None:
                self.runner._active_spinner = None

    def _start_evaluating_spinner(self) -> None:
        if not self.allow_live_spinner or self.headless or self.trace_renderer is None:
            return
        if self.spinner["obj"] is not None:
            return
        try:
            from ui.status import ThinkingStatus

            status = ThinkingStatus(self.trace_renderer.console, phase="evaluating")
            status.__enter__()
            status.start_async_refresh()
            self.spinner["obj"] = status
            if self.runner is not None:
                self.runner._active_spinner = status
        except Exception:  # noqa: BLE001
            pass

    def _add_usage(self, message: Any) -> None:
        totals = _usage_from_message(message)
        if not totals:
            return
        count_keys = (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )
        changed = False
        for key in count_keys:
            value = int(totals.get(key, 0) or 0)
            if value > 0:
                self.token_usage[key] = int(self.token_usage.get(key, 0)) + value
                changed = True
        if not changed and not totals.get("estimated"):
            return
        payload: dict[str, Any] = {
            "input_tokens": int(self.token_usage["input_tokens"]),
            "output_tokens": int(self.token_usage["output_tokens"]),
            "cache_creation_input_tokens": int(
                self.token_usage["cache_creation_input_tokens"]
            ),
            "cache_read_input_tokens": int(self.token_usage["cache_read_input_tokens"]),
        }
        for key in (
            "tokens_per_second",
            "prompt_tokens_per_second",
            "prompt_eval_seconds",
            "generation_seconds",
            "time_to_first_token",
        ):
            value = totals.get(key)
            if value is not None:
                payload[key] = float(value)
        if totals.get("estimated"):
            payload["estimated"] = True
        self._emit_progress("usage", **payload)
