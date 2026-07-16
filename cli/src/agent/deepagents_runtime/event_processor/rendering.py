"""Trailing-detail-window rendering of completed tool calls."""

from __future__ import annotations


class EventProcessorRenderingMixin:
    """Owns the full/compact flush of buffered tool results."""

    def _flush_one(self, item: dict, *, full: bool) -> None:
        """Render one buffered tool result, full or compact (errors always full)."""
        if self.headless or self.trace_renderer is None:
            return
        name = item.get("name") or "unknown"
        if full or item.get("is_error"):
            if item.get("is_error"):
                self.trace_renderer.render_tool_error(name, item.get("result_text", ""))
            else:
                self.trace_renderer.render_tool_complete(
                    name,
                    item.get("input") or {},
                    item.get("result_text", ""),
                    float(item.get("duration", 0.0)),
                )
        else:
            from ui.traces import format_duration

            dur = format_duration(float(item.get("duration", 0.0)))
            self.trace_renderer.console.print(
                f"  [green]\u2713[/] [dim]{name} ({dur})[/]"
            )

    def _close_group(self) -> None:
        """Flush any buffered tools in full detail and reset the batch state."""
        while self.pending:
            self._flush_one(self.pending.pop(0), full=True)
        if not self.group["active"]:
            return
        self.group.update({"active": False, "count": 0, "errors": 0, "start": 0.0})
