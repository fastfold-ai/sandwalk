"""Unit tests for /tools modal helpers."""

from __future__ import annotations

from types import SimpleNamespace

from ui.terminal.tools_modal import (
    build_tool_rows,
    first_selectable_index,
    run_tools_modal,
    tool_status_label,
)


def _tool(name: str, *, category: str = "target", description: str = ""):
    return SimpleNamespace(
        name=name,
        category=category,
        description=description,
        requires_data=[],
    )


def test_tool_status_labels():
    assert tool_status_label(_tool("target.foo")) == "stable"
    assert tool_status_label(_tool("x", category="compute")) == "experimental"
    assert tool_status_label(_tool("claude.code")) == "guarded"


def test_build_tool_rows_sections():
    tools = [
        _tool("a.stable", category="target"),
        _tool("b.exp", category="cro"),
        _tool("claude.code", category="code"),
    ]
    rows = build_tool_rows(tools)
    titles = [r.title for r in rows]
    assert "Stable" in titles
    assert "Experimental" in titles
    assert "Guarded" in titles


def test_build_tool_rows_search():
    tools = [
        _tool("fold.predict", description="protein folding"),
        _tool("chem.search", description="molecules"),
    ]
    rows = build_tool_rows(tools, query="protein")
    names = [r.title for r in rows if r.kind == "tool"]
    assert names == ["fold.predict"]


def test_first_selectable_skips_headers():
    rows = build_tool_rows([_tool("a.tool")])
    assert rows[0].kind == "header"
    assert first_selectable_index(rows) == 1


def test_run_tools_modal_skips_under_pytest():
    assert run_tools_modal(object()) is False
