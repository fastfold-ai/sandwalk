"""Trailing-detail-window rendering of completed tool calls."""

from __future__ import annotations


class EventProcessorRenderingMixin:
    """Owns the full/compact flush of buffered tool results."""

    def _flush_one(self, item: dict, *, full: bool) -> None:
        """Render one buffered tool result, full or compact (errors always detailed)."""
        if self.headless or self.trace_renderer is None:
            return
        name = item.get("name") or "unknown"
        duration = float(item.get("duration", 0.0))
        if item.get("is_error"):
            self.trace_renderer.render_tool_error(name, item.get("result_text", ""))
            return
        if full:
            self.trace_renderer.render_tool_complete(
                name,
                item.get("input") or {},
                item.get("result_text", ""),
                duration,
            )
            return
        render_compact = getattr(self.trace_renderer, "render_tool_compact", None)
        if callable(render_compact):
            render_compact(
                name,
                duration,
                args=item.get("input") or {},
                result=item.get("result_text", ""),
                is_error=False,
            )
            return
        self.trace_renderer.console.print(
            f"  [green]\u2713[/] [dim]Ran {name}[/] [dim]\u25b8[/]"
        )

    def _close_group(self) -> None:
        """Flush buffered trailing-window tools; reset the batch state.

        When ``detail_window > 0``, buffered items render in full on close.
        When ``detail_window == 0``, pending is empty (tools already printed
        compact as they finished).
        """
        show_full = self.detail_window > 0
        while self.pending:
            self._flush_one(self.pending.pop(0), full=show_full)
        if not self.group["active"]:
            return
        self.group.update({"active": False, "count": 0, "errors": 0, "start": 0.0})
