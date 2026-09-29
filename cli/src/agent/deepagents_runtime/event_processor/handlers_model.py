"""Handlers for on_chat_model_stream / on_chat_model_end events."""

from __future__ import annotations

import logging
import time

from agent.deepagents_runtime.event_text import _text_from_content

logger = logging.getLogger(__name__)


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
            # A model turn with no prose is normal when it only called tools;
            # with no tool calls either it is the whole answer going missing
            # (refusal, max_tokens, provider hiccup). Keep the provider's
            # stop reason so the summary and logs can say why.
            if output is not None and not getattr(output, "tool_calls", None):
                self._note_empty_model_turn(output)
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

    def _note_empty_model_turn(self, output: object) -> None:
        meta = getattr(output, "response_metadata", None)
        meta = meta if isinstance(meta, dict) else {}
        stop_reason = (
            meta.get("stop_reason")
            or meta.get("finish_reason")
            or meta.get("stopReason")
            or meta.get("done_reason")
        )
        content = getattr(output, "content", None)
        block_types: list[str] = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    block_types.append(str(block.get("type") or "?"))
                else:
                    block_types.append(type(block).__name__)
        note = {
            "call": self.model_call_count,
            "stop_reason": str(stop_reason) if stop_reason is not None else None,
            "content_blocks": block_types,
            "model": meta.get("model") or meta.get("model_name"),
        }
        self.empty_model_turns.append(note)
        logger.info(
            "[llm] empty model turn #%s: stop_reason=%s content_blocks=%s model=%s",
            note["call"],
            note["stop_reason"],
            ",".join(block_types) or "-",
            note["model"],
        )
