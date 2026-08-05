"""Unit tests for /specialist modal helpers."""

from __future__ import annotations

from types import SimpleNamespace

from ui.terminal.specialist_modal import (
    _SpecialistRow,
    apply_specialist_selection,
    build_specialist_rows,
    first_selectable_index,
    run_specialist_modal,
)


def _spec(name: str, slug: str, *, sid: str = "", description: str = ""):
    return SimpleNamespace(
        id=sid or slug,
        name=name,
        slug=slug,
        description=description,
        skill_names=["fold"],
        mcp_server_ids=[],
        mcp_catalog_ids=[],
        enabled=True,
    )


def test_build_specialist_rows_includes_none():
    rows = build_specialist_rows([], active_id="")
    kinds = [r.kind for r in rows]
    assert "none" in kinds
    none = next(r for r in rows if r.kind == "none")
    assert none.active is True


def test_build_specialist_rows_marks_active():
    items = [_spec("Bio", "bio", sid="1"), _spec("Chem", "chem", sid="2")]
    rows = build_specialist_rows(items, active_id="2")
    active = [r for r in rows if r.kind == "specialist" and r.active]
    assert len(active) == 1
    assert active[0].slug == "chem"
    none = next(r for r in rows if r.kind == "none")
    assert none.active is False


def test_build_specialist_rows_search():
    items = [
        _spec("Biology", "bio", description="cells"),
        _spec("Chemistry", "chem", description="molecules"),
    ]
    rows = build_specialist_rows(items, query="chem")
    specs = [r for r in rows if r.kind == "specialist"]
    assert len(specs) == 1
    assert specs[0].slug == "chem"


def test_first_selectable_prefers_none():
    rows = build_specialist_rows([_spec("Bio", "bio")])
    assert rows[0].kind == "header"
    assert first_selectable_index(rows) == 1
    assert rows[1].kind == "none"


def test_apply_specialist_selection_none(monkeypatch):
    calls: list[str | None] = []

    def _set(ref):
        calls.append(ref)

    monkeypatch.setattr(
        "agent.specialists_manage.set_active_specialist_ref",
        _set,
    )
    terminal = SimpleNamespace(_refresh_cli_specialist_label=lambda: None)
    msg = apply_specialist_selection(
        terminal, _SpecialistRow(kind="none", title="None")
    )
    assert calls == [None]
    assert "Cleared" in msg


def test_run_specialist_modal_skips_under_pytest():
    assert run_specialist_modal(object()) is False
