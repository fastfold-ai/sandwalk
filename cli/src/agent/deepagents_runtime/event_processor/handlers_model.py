"""Handlers for on_chat_model_stream / on_chat_model_end events."""

from __future__ import annotations

import re
import time

from agent.deepagents_runtime.event_text import _text_from_content

# Bare identifier text (e.g. "run_python", "shell_run") — some OpenAI-compatible
# providers (Inkling/GLM via Together) mirror the tool name into streamed
# ``content`` while emitting a tool call. Real prose diverges within a few
# characters (whitespace, punctuation, uppercase).
_IDENTIFIER_RE = re.compile(r"[a-z0-9_.]+\Z")
_STREAM_GATE_MAX_HOLD = 96


def _tool_call_names(message) -> set[str]:
    names: set[str] = set()
    for call in getattr(message, "tool_calls", None) or []:
        if isinstance(call, dict):
            name = str(call.get("name") or "")
        else:
            name = str(getattr(call, "name", "") or "")
        if name:
            names.add(name)
    return names


def _is_tool_name_noise(text: str, names: set[str]) -> bool:
    """True when ``text`` is only tool names (some OpenAI-compatible providers,
    e.g. Inkling/GLM via Together, mirror the function name into ``content``
    while emitting a tool call)."""
    if not names or not text.strip():
        return False
    residue = text
    for name in names:
        residue = residue.replace(name, "")
    return not residue.strip()


class EventProcessorModelHandlersMixin:
    """Owns streaming-token and end-of-turn text handling."""

    def _handle_chat_model_stream(self, data: dict) -> None:
        chunk = data.get("chunk")
        if chunk is None:
            return
        # Chunks carrying tool-call fragments: any content text is the
        # function name leaking through — never stream it as answer text.
        if getattr(chunk, "tool_call_chunks", None):
            return
        text = _text_from_content(getattr(chunk, "content", ""))
        if not text:
            return
        # Gate the head of each model call: hold back text while it still
        # looks like a bare tool identifier; drop it at model end if it never
        # diverged into prose (tool-name leak), flush it as soon as it does.
        if not getattr(self, "_stream_gate_open", False):
            buffered = getattr(self, "_stream_gate_buf", "") + text
            if (
                _IDENTIFIER_RE.fullmatch(buffered)
                and len(buffered) <= _STREAM_GATE_MAX_HOLD
            ):
                self._stream_gate_buf = buffered
                return
            self._stream_gate_open = True
            self._stream_gate_buf = ""
            text = buffered
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
        # Reset the stream gate per model call; anything still held was a
        # tool-name leak (never diverged into prose) and is dropped.
        self._stream_gate_buf = ""
        self._stream_gate_open = False
        output = data.get("output")
        self._add_usage(output)
        text = _text_from_content(getattr(output, "content", "")) if output is not None else ""
        if not text.strip():
            return
        if _is_tool_name_noise(text, _tool_call_names(output)):
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
