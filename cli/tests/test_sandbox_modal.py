"""Unit tests for /sandbox modal helpers."""

from __future__ import annotations

from types import SimpleNamespace

from ui.terminal.sandbox_modal import (
    build_sandbox_rows,
    first_selectable_index,
    run_sandbox_modal,
)


def test_build_sandbox_rows_includes_local():
    cfg = SimpleNamespace()
    # Config API used by presets — stub via real Config when possible.
    from agent.config import Config

    rows = build_sandbox_rows(Config.load())
    titles = [r.title for r in rows if r.kind == "option"]
    assert any("Local" in t for t in titles)
    assert first_selectable_index(rows) >= 1


def test_build_sandbox_rows_search():
    from agent.config import Config

    rows = build_sandbox_rows(Config.load(), query="local")
    titles = [r.title for r in rows if r.kind == "option"]
    assert titles
    assert all("local" in t.lower() or "builtin" in t.lower() for t in titles) or any(
        "Local" in t for t in titles
    )


def test_run_sandbox_modal_skips_under_pytest():
    assert run_sandbox_modal(object()) is False
