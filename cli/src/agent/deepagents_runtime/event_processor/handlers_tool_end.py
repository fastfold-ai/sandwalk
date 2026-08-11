"""Handler for on_tool_end events."""

from __future__ import annotations

import time

from agent.deepagents_runtime.event_text import _tool_output_text


class EventProcessorToolEndMixin:
    """Owns tool-end result normalization, trace emission, and rendering."""

    def _handle_tool_end(self, event: dict, data: dict) -> None:
        raw_name = event.get("name", "") or ""
        display = self.display_name_map.get(raw_name, raw_name)
        run_id = event.get("run_id", "") or ""
        output = data.get("output")
        result_text = _tool_output_text(output)
        is_error = str(getattr(output, "status", "") or "").lower() == "error"

        tracked = self.inflight.pop(run_id, None)
        duration = 0.0
        tool_input: dict = {}
        if tracked:
            duration = max(0.0, time.time() - tracked["start_time"])
            display = tracked["name"]
            tool_input = tracked["input"]
        self._stop_spinner()
        self._emit_progress(
            "tool_end",
            name=display,
            output=result_text,
            is_error=is_error,
            duration_s=duration,
            tool_call_id=run_id,
        )

        for entry in reversed(self.tool_calls):
            if entry.get("name") == display and "result_text" not in entry:
                entry["result_text"] = result_text
                entry["duration_s"] = duration
                break

        if self.trace_events is not None:
            self.trace_events.append(self._build_tool_result_event(
                display, run_id, result_text, is_error, duration,
            ))

        if self.group_tools and display != "write_todos":
            if is_error:
                self.group["errors"] = int(self.group["errors"]) + 1
            item = {
                "name": display or "unknown",
                "input": tool_input,
                "result_text": result_text,
                "duration": duration,
                "is_error": is_error,
            }
            # detail_window == 0 → collapsed one-liner immediately (default).
            # detail_window > 0 → keep last N buffered; spill older as compact.
            # Errors always flush now so failures aren't hidden in the buffer.
            if is_error or self.detail_window <= 0:
                self._flush_one(item, full=False)
            else:
                self.pending.append(item)
                while len(self.pending) > self.detail_window:
                    self._flush_one(self.pending.pop(0), full=False)
            self._emit_progress("activity", text=f"\u25b8 {display}")
            return

        if not self.headless and self.trace_renderer:
            if display == "write_todos":
                # The checklist was already rendered at tool-start; the raw
                # Command(update=...) echo would just add noise.
                pass
            elif is_error:
                self.trace_renderer.render_tool_error(display or "unknown", result_text)
            else:
                self.trace_renderer.render_tool_complete(
                    display or "unknown", tool_input, result_text, duration
                )

    def _build_tool_result_event(
        self, display: str, run_id: str, result_text: str, is_error: bool, duration: float,
    ) -> dict:
        evt = {
            "type": "tool_result",
            "tool": display,
            "tool_use_id": run_id,
            "result_text": result_text,
            "is_error": is_error,
            "duration_s": duration,
            "timestamp": time.time(),
        }
        if display in ("run_python", "run_r") and self.code_trace_buffer is not None:
            if self.code_cursor < len(self.code_trace_buffer):
                meta = self.code_trace_buffer[self.code_cursor]
                self.code_cursor += 1
                evt.update(
                    {
                        "result_text": meta.get("stdout", result_text),
                        "is_error": bool(meta.get("error")),
                        "code": meta.get("code", ""),
                        "stdout": meta.get("stdout", ""),
                        "plots": meta.get("plots", []),
                        "exports": meta.get("exports", []),
                        "error": meta.get("error"),
                    }
                )
        return evt
