"""Scrollable transcript UIControl with click-to-expand and wheel scroll."""

from __future__ import annotations

from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType

from ui.terminal.transcript.render import render_all_lines
from ui.terminal.transcript.store import ToolEntry, TranscriptStore


class TranscriptControl(UIControl):
    """Full-height transcript content; the parent ``Window`` scrolls natively."""

    def __init__(self, store: TranscriptStore, *, config=None) -> None:
        self.store = store
        self.config = config
        self.window = None  # set by app after Window is created
        self._hit_map: list[tuple[object, int]] = []
        self._height = 1
        self._width = 80
        self._line_count = 0

    def is_focusable(self) -> bool:
        # Keep focus on the input buffer; mouse over this window still works.
        return False

    def create_content(self, width: int, height: int) -> UIContent:
        self._width = max(20, width)
        self._height = max(1, height)
        rows, hit_map = render_all_lines(
            self.store, width=self._width, config=self.config
        )
        self._hit_map = hit_map
        self._line_count = len(rows)

        # The Window scrolls to keep ``cursor_position`` visible, so the
        # cursor *is* our scroll anchor: last line while following the tail,
        # else the current scroll position (so manual scrolling isn't undone).
        last = max(0, len(rows) - 1)
        if self.store.follow_tail:
            cursor = Point(x=0, y=last)
            if self.window is not None:
                self.window.vertical_scroll = max(0, self._line_count - self._height)
        else:
            scroll = int(getattr(self.window, "vertical_scroll", 0) or 0)
            cursor = Point(x=0, y=max(0, min(last, scroll)))

        def get_line(i: int):
            if i < 0 or i >= len(rows):
                return []
            return list(rows[i])

        return UIContent(
            get_line=get_line,
            line_count=len(rows),
            cursor_position=cursor,
            show_cursor=False,
        )

    def mouse_handler(self, mouse_event: MouseEvent):
        etype = mouse_event.event_type

        # Let the parent Window perform native vertical scroll; track follow-tail.
        if etype == MouseEventType.SCROLL_UP:
            self.store.follow_tail = False
            return NotImplemented
        if etype == MouseEventType.SCROLL_DOWN:
            win = self.window
            if win is not None:
                max_scroll = max(0, self._line_count - self._height)
                # Window scrolls +1 per wheel event after we return.
                if win.vertical_scroll + 1 >= max_scroll:
                    self.store.follow_tail = True
            return NotImplemented

        if etype == MouseEventType.MOUSE_DOWN:
            y = mouse_event.position.y
            scroll = int(getattr(self.window, "vertical_scroll", 0) or 0)
            idx = scroll + y
            if idx < 0 or idx >= len(self._hit_map):
                return NotImplemented
            entry, line_idx = self._hit_map[idx]
            if isinstance(entry, ToolEntry) and line_idx >= 0:
                self.store.toggle_tool(entry.entry_id)
                return None
        return NotImplemented

    def scroll_by(self, delta: int) -> None:
        """Adjust ``Window.vertical_scroll``. Positive moves toward newer lines."""
        win = self.window
        if win is None:
            return
        max_scroll = max(0, self._line_count - self._height)
        if delta < 0:
            self.store.follow_tail = False
        win.vertical_scroll = max(0, min(max_scroll, win.vertical_scroll + delta))
        if win.vertical_scroll >= max_scroll:
            self.store.follow_tail = True

    def move_cursor_down(self) -> None:
        self.scroll_by(1)

    def move_cursor_up(self) -> None:
        self.scroll_by(-1)

    def get_cursor_position(self) -> Point:
        return Point(x=0, y=0)
