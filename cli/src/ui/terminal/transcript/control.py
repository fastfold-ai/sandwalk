"""Scrollable transcript UIControl with click-to-expand, selection, and wheel scroll."""

from __future__ import annotations

import subprocess
import sys

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType

from ui.terminal.transcript.render import render_all_lines
from ui.terminal.transcript.store import ToolEntry, TranscriptStore


def _merge_frags(frags: StyleAndTextTuples) -> StyleAndTextTuples:
    if not frags:
        return []
    out: StyleAndTextTuples = [frags[0]]
    for style, text in frags[1:]:
        prev_style, prev_text = out[-1]
        if style == prev_style:
            out[-1] = (prev_style, prev_text + text)
        else:
            out.append((style, text))
    return out


def _overlay_selection(
    frags: StyleAndTextTuples, start_x: int, end_x: int
) -> StyleAndTextTuples:
    """Highlight ``[start_x, end_x)`` with reverse video."""
    if end_x <= start_x:
        return frags
    out: StyleAndTextTuples = []
    col = 0
    for style, text in frags:
        for ch in text:
            if start_x <= col < end_x:
                out.append(("class:transcript-selected", ch))
            else:
                out.append((style, ch))
            col += 1
    return _merge_frags(out)


def _copy_to_clipboard(text: str) -> None:
    if not text:
        return
    try:
        from prompt_toolkit.application.current import get_app
        from prompt_toolkit.clipboard import ClipboardData

        get_app().clipboard.set_data(ClipboardData(text))
    except Exception:  # noqa: BLE001
        pass
    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode(),
                check=False,
            )
    except Exception:  # noqa: BLE001
        pass


class TranscriptControl(UIControl):
    """Full-height transcript content; the parent ``Window`` scrolls natively."""

    def __init__(self, store: TranscriptStore, *, config=None) -> None:
        self.store = store
        self.config = config
        self.window = None  # set by app after Window is created
        self._hit_map: list[tuple[object, int]] = []
        self._plain_lines: list[str] = []
        self._rows: list = []
        self._height = 1
        self._width = 80
        self._line_count = 0
        self._cache_key: tuple[int, int] | None = None
        # Drag selection (in-app; mouse tracking blocks host selection).
        self._sel_anchor: Point | None = None
        self._sel_end: Point | None = None
        self._dragging = False
        self._mouse_down_pos: Point | None = None

    def is_focusable(self) -> bool:
        # Keep focus on the input buffer; mouse over this window still works.
        return False

    def has_selection(self) -> bool:
        bounds = self.selection_bounds()
        if bounds is None:
            return False
        start, end = bounds
        return (start.y, start.x) != (end.y, end.x)

    def clear_selection(self) -> None:
        self._sel_anchor = None
        self._sel_end = None
        self._dragging = False
        self._mouse_down_pos = None

    def selection_bounds(self) -> tuple[Point, Point] | None:
        if self._sel_anchor is None or self._sel_end is None:
            return None
        a, b = self._sel_anchor, self._sel_end
        if (a.y, a.x) <= (b.y, b.x):
            return a, b
        return b, a

    def selected_text(self) -> str:
        bounds = self.selection_bounds()
        if bounds is None:
            return ""
        start, end = bounds
        if (start.y, start.x) == (end.y, end.x):
            return ""
        lines = self._plain_lines
        if not lines:
            return ""
        y0 = max(0, min(start.y, len(lines) - 1))
        y1 = max(0, min(end.y, len(lines) - 1))
        x0, x1 = start.x, end.x
        # Inclusive end column (character under the cursor is selected).
        if y0 == y1:
            line = lines[y0]
            lo, hi = sorted((x0, x1))
            return line[lo : hi + 1]
        parts: list[str] = [lines[y0][x0:]]
        for y in range(y0 + 1, y1):
            parts.append(lines[y])
        parts.append(lines[y1][: x1 + 1])
        return "\n".join(parts)

    def copy_selection_to_clipboard(self) -> str:
        text = self.selected_text()
        _copy_to_clipboard(text)
        return text

    def create_content(self, width: int, height: int) -> UIContent:
        self._width = max(20, width)
        self._height = max(1, height)
        # Always wrap to the live window width so resize never leaves clipped
        # or narrow-column text. Toolbar animation must not re-run Rich/markdown
        # unless the store revision or width actually changed.
        key = (int(self.store.revision), self._width)
        if key != self._cache_key:
            rows, hit_map = render_all_lines(
                self.store, width=self._width, config=self.config
            )
            self._rows = rows
            self._hit_map = hit_map
            self._plain_lines = [
                "".join(piece for _style, piece in row) for row in rows
            ]
            self._cache_key = key
        rows = self._rows
        self._line_count = len(rows)
        pad_width = self._width

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

        bounds = self.selection_bounds()

        def get_line(i: int):
            if i < 0 or i >= len(rows):
                # Clear stale cells on unused rows after a shrink-resize.
                return [("", " " * pad_width)] if pad_width > 0 else []
            frags = list(rows[i])
            if bounds is not None and self.has_selection():
                start, end = bounds
                if start.y <= i <= end.y:
                    line_len = (
                        len(self._plain_lines[i]) if i < len(self._plain_lines) else 0
                    )
                    if start.y == end.y:
                        lo, hi = sorted((start.x, end.x))
                        frags = _overlay_selection(frags, lo, hi + 1)
                    elif i == start.y:
                        frags = _overlay_selection(
                            frags, start.x, max(start.x, line_len) + 1
                        )
                    elif i == end.y:
                        frags = _overlay_selection(frags, 0, end.x + 1)
                    else:
                        frags = _overlay_selection(frags, 0, line_len + 1)
            # Pad to full width so shrink-resizes erase previous glyphs.
            plain_len = sum(len(t) for _s, t in frags)
            if plain_len < pad_width:
                frags = [*frags, ("", " " * (pad_width - plain_len))]
            return frags

        return UIContent(
            get_line=get_line,
            line_count=max(len(rows), self._height),
            cursor_position=cursor,
            show_cursor=False,
        )

    def mouse_handler(self, mouse_event: MouseEvent):
        etype = mouse_event.event_type
        pos = Point(x=int(mouse_event.position.x), y=int(mouse_event.position.y))

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
            self._mouse_down_pos = pos
            self._sel_anchor = pos
            self._sel_end = pos
            self._dragging = False
            return None

        if etype == MouseEventType.MOUSE_MOVE and mouse_event.button != MouseButton.NONE:
            if self._sel_anchor is None:
                return NotImplemented
            self._sel_end = pos
            if self._mouse_down_pos is not None and (
                pos.x != self._mouse_down_pos.x or pos.y != self._mouse_down_pos.y
            ):
                self._dragging = True
            return None

        if etype == MouseEventType.MOUSE_UP:
            self._sel_end = pos
            if self._dragging:
                # Keep highlight; copy so paste works immediately.
                self._dragging = False
                self._mouse_down_pos = None
                self.copy_selection_to_clipboard()
                return None

            # Plain click — clear selection and toggle tool if hit.
            self.clear_selection()
            idx = pos.y
            if 0 <= idx < len(self._hit_map):
                entry, line_idx = self._hit_map[idx]
                if isinstance(entry, ToolEntry) and line_idx >= 0:
                    self.store.toggle_tool(entry.entry_id)
                    return None
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
