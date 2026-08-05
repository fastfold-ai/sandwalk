"""Unit tests for /sessions modal helpers."""

from __future__ import annotations

from ui.terminal.sessions_modal import (
    SessionEntry,
    build_session_rows,
    first_selectable_index,
    lean_text,
    run_sessions_modal,
)


def test_lean_text_truncates():
    assert lean_text("short") == "short"
    out = lean_text("word " * 40, max_len=20)
    assert len(out) <= 20
    assert out.endswith("…")


def test_build_session_rows_date_and_pinned():
    entries = [
        SessionEntry(
            session_id="a",
            title="Pinned chat",
            snippet="hello",
            updated_at=1_700_000_000.0,
            pinned=True,
        ),
        SessionEntry(
            session_id="b",
            title="Recent chat",
            snippet="world",
            updated_at=1_700_000_000.0,
            pinned=False,
        ),
    ]
    rows = build_session_rows(entries)
    titles = [r.title for r in rows]
    assert titles[0] == "Pinned"
    assert any(r.kind == "session" and r.title == "Pinned chat" for r in rows)
    assert any(r.kind == "header" and r.title != "Pinned" for r in rows)


def test_build_session_rows_search():
    entries = [
        SessionEntry(
            session_id="a",
            title="Capybara",
            snippet="animal",
            updated_at=1.0,
        ),
        SessionEntry(
            session_id="b",
            title="Greeting",
            snippet="hi",
            updated_at=1.0,
        ),
    ]
    rows = build_session_rows(entries, query="capy")
    names = [r.title for r in rows if r.kind == "session"]
    assert names == ["Capybara"]


def test_first_selectable_skips_headers():
    entries = [
        SessionEntry(
            session_id="a", title="One", snippet="x", updated_at=1.0, pinned=True
        )
    ]
    rows = build_session_rows(entries)
    assert rows[0].kind == "header"
    assert first_selectable_index(rows) == 1


def test_run_sessions_modal_skips_under_pytest():
    assert run_sessions_modal(object()) is False


def test_backdrop_dim_keeps_sessions_styles_bright():
    from ui.terminal.themes_modal import dim_transcript_styles_for_backdrop

    styles = {
        "transcript-root": "bg:#ffffff #111111",
        "sessions-dialog": "bg:#abcdef #000000",
    }
    out = dim_transcript_styles_for_backdrop(styles, alpha=0.5)
    assert out["sessions-dialog"] == "bg:#abcdef #000000"
