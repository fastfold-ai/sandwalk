"""Unit tests for /settings modal helpers."""

from __future__ import annotations

from ui.terminal.settings_modal import (
    build_settings_rows,
    cycle_profile,
    cycle_spinner,
    first_selectable_index,
    run_settings_modal,
)


def test_build_settings_rows_includes_core_keys():
    rows = build_settings_rows()
    keys = [r.key for r in rows if r.kind == "setting"]
    assert keys == ["spinner", "profile", "auto_publish", "openai_profiles"]


def test_build_settings_rows_search_filters():
    rows = build_settings_rows(query="spinner")
    keys = [r.key for r in rows if r.kind == "setting"]
    assert keys == ["spinner"]


def test_first_selectable_skips_headers():
    rows = build_settings_rows()
    assert rows[0].kind == "header"
    assert first_selectable_index(rows) == 1


def test_cycle_spinner_and_profile():
    assert cycle_spinner("dna_helix") in {"benzene_breathing", "dna_helix"}
    assert cycle_profile("research") in {"research", "enterprise", "pharma"}


def test_run_settings_modal_skips_under_pytest():
    assert run_settings_modal(object()) is False


def test_backdrop_dim_keeps_settings_styles_bright():
    from ui.terminal.themes_modal import dim_transcript_styles_for_backdrop

    styles = {
        "transcript-root": "bg:#ffffff #111111",
        "settings-dialog": "bg:#abcdef #000000",
    }
    out = dim_transcript_styles_for_backdrop(styles, alpha=0.5)
    assert out["settings-dialog"] == "bg:#abcdef #000000"
    assert out["transcript-root"] != styles["transcript-root"]
