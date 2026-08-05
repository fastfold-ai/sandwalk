"""Unit tests for /effort modal helpers."""

from __future__ import annotations

from ui.terminal.effort_modal import (
    build_effort_rows,
    first_selectable_index,
    run_effort_modal,
)


def test_build_effort_rows_options():
    rows = build_effort_rows(current_label="Medium")
    titles = [r.title for r in rows if r.kind == "option"]
    assert titles[0] == "Low"
    assert any("Fast" in t for t in titles)


def test_build_effort_rows_search():
    rows = build_effort_rows(query="fast")
    titles = [r.title for r in rows if r.kind == "option"]
    assert len(titles) == 1
    assert "Fast" in titles[0]


def test_first_selectable_skips_header():
    rows = build_effort_rows()
    assert rows[0].kind == "header"
    assert first_selectable_index(rows) == 1


def test_run_effort_modal_skips_under_pytest():
    assert run_effort_modal(object()) is False
