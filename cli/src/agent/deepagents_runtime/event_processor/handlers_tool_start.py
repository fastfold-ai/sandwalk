"""Handler for on_tool_start events."""

from __future__ import annotations

import time


class EventProcessorToolStartMixin:
    """Owns tool-start bookkeeping, trace emission, and grouped/live rendering."""

    def _handle_tool_start(self, event: dict, data: dict) -> None:
        raw_name = event.get("name", "") or ""
        display = self.display_name_map.get(raw_name, raw_name)
        run_id = event.get("run_id", "") or ""
        tool_input = data.get("input", {}) or {}
        now = time.time()
        self._stop_spinner()
        self.inflight[run_id] = {"name": display, "input": tool_input, "start_time": now}
        self.tool_calls.append({"name": display, "input": tool_input})
        self._emit_progress(
            "tool_start",
            name=display,
            arguments=tool_input,
            tool_call_id=run_id,
        )
        if self.trace_events is not None:
            self.trace_events.append(
                {
                    "type": "tool_start",
                    "tool": display,
                    "input": tool_input,
                    "tool_use_id": run_id,
                    "timestamp": now,
                }
            )
        is_todos = display == "write_todos"
        if self.group_tools and not is_todos:
            # Detail is deferred to tool-end (trailing window), so the
            # current call surfaces live via the spinner/toolbar instead of a
            # start line that we'd be unable to collapse later.
            if not self.group["active"]:
                self.group.update({"active": True, "count": 0, "errors": 0, "start": now})
            self.group["count"] = int(self.group["count"]) + 1
            self._emit_progress("activity", text=f"\u25b8 {display}")
            self._start_evaluating_spinner()
            return

        if not self.headless and self.trace_renderer:
            if is_todos:
                # Todos stay visible; close any open group first so the
                # checklist isn't swallowed by the collapsed summary.
                if self.group_tools:
                    self._close_group()
                self.trace_renderer.render_todos(tool_input.get("todos"))
            else:
                self.trace_renderer.render_tool_start(display, tool_input)
        self._emit_progress("activity", text=f"\u25b8 {display}")
        self._start_evaluating_spinner()
