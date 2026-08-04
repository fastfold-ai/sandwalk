"""Tests for collapsed tool expand store + click row mapping."""

from __future__ import annotations

from ui.traces.tool_expand import ToolExpandStore


def test_add_and_expand_last():
    store = ToolExpandStore()
    store.add(name="shell.run", args={"command": "ls"}, result="ok", duration=0.4)
    store.add(name="run_python", args={"code": "1"}, result="1", duration=0.1)
    card = store.expand()
    assert card is not None
    assert card.name == "run_python"
    assert card.expanded is True
    card2 = store.expand()
    assert card2 is not None
    assert card2.name == "shell.run"


def test_card_for_screen_row():
    store = ToolExpandStore()
    store.note_lines(5)  # non-tool output
    store.add(name="a", result="1")  # line 6
    store.add(name="b", result="2")  # line 7
    # 2 rows above prompt showing lines 6-7; click y=0 → line 6 → a
    hit = store.card_for_screen_row(rows_above_layout=2, y=0)
    assert hit is not None
    assert hit.name == "a"
    hit2 = store.card_for_screen_row(rows_above_layout=2, y=1)
    assert hit2 is not None
    assert hit2.name == "b"
