"""Tests for Warp-friendly click-to-place cursor."""

from __future__ import annotations

from types import SimpleNamespace

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.mouse_events import MouseButton, MouseEventType

from ui.terminal.mouse_place import parse_sgr_mouse, place_cursor_in_buffer


def test_parse_sgr_left_down():
    parsed = parse_sgr_mouse("\x1b[<0;10;3M")
    assert parsed is not None
    x, y, button, etype = parsed
    assert (x, y) == (9, 2)
    assert button == MouseButton.LEFT
    assert etype == MouseEventType.MOUSE_DOWN


def test_parse_sgr_ignores_scroll():
    assert parse_sgr_mouse("\x1b[<64;10;3M") is None


def test_place_cursor_by_column():
    buf = Buffer(document=Document("hello world", 0))
    place_cursor_in_buffer(buf, x=2 + 6, local_y=0, prompt_width=2)
    assert buf.document.text_before_cursor == "hello "


def test_place_cursor_multiline_last_line():
    buf = Buffer(document=Document("aaa\nbbb\nccc", 0))
    place_cursor_in_buffer(buf, x=2 + 1, local_y=2, prompt_width=2)
    assert buf.document.cursor_position_row == 2
    assert buf.document.cursor_position_col == 1
