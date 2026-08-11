"""Handlers for on_chat_model_stream / on_chat_model_end events."""

from __future__ import annotations

import time

from agent.deepagents_runtime.event_text import _text_from_content


class EventProcessorModelHandlersMixin:
    """Owns streaming-token and end-of-turn text handling."""

    def _handle_chat_model_stream(self, data: dict) -> None:
        chunk = data.get("chunk")
        if chunk is None:
            return
        # Structured tool-call fragments are not assistant prose — skip any
        # content that arrives on the same chunk (provider wire format).
        if getattr(chunk, "tool_call_chunks", None):
            return
        text = _text_from_content(getattr(chunk, "content", ""))
        if not text:
            return
        if self.group_tools:
            self._close_group()
        self._stop_spinner()
        self.streamed_len += len(text)
        self._emit_progress(
            "stream",
            delta=text,
            streamed_chars=int(self.streamed_len),
        )

    def _handle_chat_model_end(self, data: dict) -> None:
        self.model_call_count += 1
        output = data.get("output")
        self._add_usage(output)
        text = _text_from_content(getattr(output, "content", "")) if output is not None else ""
        if not text.strip():
            return
        if self.group_tools:
            self._close_group()
        self._stop_spinner()
        self.full_text.append(text)
        if self.trace_events is not None:
            self.trace_events.append(
                {"type": "text", "content": text, "timestamp": time.time()}
            )
        if not self.headless and self.trace_renderer:
            self.streamed_len = 0
            self.trace_renderer.render_reasoning(text)
        snippet = text.strip().replace("\n", " ")[:40]
        if snippet:
            self._emit_progress("activity", text=snippet)
