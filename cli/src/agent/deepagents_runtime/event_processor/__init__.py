"""Consume ``astream_events`` (v2) into the ct result/trace contract.

Split into mixins (state/progress, rendering, per-event-type handlers) so the
former single ~330-line closure-heavy function stays under the file-length cap
while keeping one cohesive ``_EventProcessor`` per run.
"""

from __future__ import annotations

from agent.deepagents_runtime.event_processor.core import EventProcessorCoreMixin
from agent.deepagents_runtime.event_processor.handlers_model import (
    EventProcessorModelHandlersMixin,
)
from agent.deepagents_runtime.event_processor.handlers_tool_end import (
    EventProcessorToolEndMixin,
)
from agent.deepagents_runtime.event_processor.handlers_tool_start import (
    EventProcessorToolStartMixin,
)
from agent.deepagents_runtime.event_processor.rendering import EventProcessorRenderingMixin

__all__ = ["process_events"]


class _EventProcessor(
    EventProcessorModelHandlersMixin,
    EventProcessorToolStartMixin,
    EventProcessorToolEndMixin,
    EventProcessorRenderingMixin,
    EventProcessorCoreMixin,
):
    """Stateful consumer for one ``astream_events`` run."""

    async def run(self, events_iter) -> dict:
        async for event in events_iter:
            etype = event.get("event", "")
            data = event.get("data", {}) or {}

            if etype == "on_chat_model_stream":
                self._handle_chat_model_stream(data)
                continue
            if etype == "on_chat_model_end":
                self._handle_chat_model_end(data)
                continue
            if etype == "on_tool_start":
                self._handle_tool_start(event, data)
                continue
            if etype == "on_tool_end":
                self._handle_tool_end(event, data)
                continue

        if self.group_tools:
            self._close_group()
        self._stop_spinner()

        return {
            "full_text": self.full_text,
            "tool_calls": self.tool_calls,
            "token_usage": self.token_usage,
            "model_call_count": self.model_call_count,
            "pending_background_tasks": [],
            "completed_background_tasks": [],
        }


async def process_events(
    events_iter,
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
    tool_detail_limit: int = 0,
) -> dict:
    """Consume ``astream_events`` (v2) into the ct result/trace contract.

    Produces the ExecutionResult, trace export, and usage-accounting shapes the
    UI and export layers expect.

    Tool-call rendering: when ``group_tools`` is True and
    ``tool_detail_limit`` is 0 (default), every tool prints as a collapsed
    one-liner (``✓ Ran name ▸``). Set ``tool_detail_limit`` to N > 0 to keep
    the last N tools in a batch for full detail when the batch closes; older
    ones stay compact. Errors always show their message. Set ``group_tools``
    False to show every tool in full.
    """
    processor = _EventProcessor(
        trace_renderer=trace_renderer,
        headless=headless,
        trace_events=trace_events,
        thinking_status=thinking_status,
        allow_live_spinner=allow_live_spinner,
        runner=runner,
        on_activity=on_activity,
        code_trace_buffer=code_trace_buffer,
        display_name_map=display_name_map,
        group_tools=group_tools,
        tool_detail_limit=tool_detail_limit,
    )
    return await processor.run(events_iter)
