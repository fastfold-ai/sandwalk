"""Unit tests for /themes modal helpers (filter + options)."""

from __future__ import annotations

from ui.terminal.theme_palettes import list_palettes
from ui.terminal.themes_modal import build_theme_options, filter_theme_options


def test_build_theme_options_includes_modes_and_palettes():
    opts = build_theme_options(list_palettes(), mode="dark")
    kinds = {o.kind for o in opts}
    assert kinds == {"mode", "palette"}
    modes = [o.value for o in opts if o.kind == "mode"]
    assert modes == ["light", "dark", "auto"]
    ids = {o.value for o in opts if o.kind == "palette"}
    assert "sandwalk" in ids
    assert "ember" in ids


def test_filter_theme_options_by_name_and_id():
    opts = build_theme_options(list_palettes(), mode="auto")
    neon = filter_theme_options(opts, "neon")
    assert any(o.value == "neonnoir" for o in neon)
    assert all("neon" in o.search.lower() or "neon" in o.title.lower() for o in neon)

    modes = filter_theme_options(opts, "mode dark")
    assert any(o.kind == "mode" and o.value == "dark" for o in modes)


def test_filter_empty_query_returns_all():
    opts = build_theme_options(list_palettes(), mode="auto")
    assert filter_theme_options(opts, "") == opts
    assert filter_theme_options(opts, "   ") == opts


def test_run_themes_modal_skips_under_pytest():
    from ui.terminal.themes_modal import run_themes_modal

    assert run_themes_modal(object()) is False


def test_overlay_black_blends_toward_black():
    from ui.terminal.themes_modal import _overlay_black

    assert _overlay_black("#ffffff", 0.5) == "#7f7f7f"
    assert _overlay_black("#000000", 0.5) == "#000000"


def test_backdrop_dim_keeps_themes_styles_bright():
    from ui.terminal.themes_modal import dim_transcript_styles_for_backdrop

    styles = {
        "transcript-root": "bg:#ffffff #111111",
        "themes-dialog": "bg:#abcdef #000000",
    }
    out = dim_transcript_styles_for_backdrop(styles, alpha=0.5)
    assert out["themes-dialog"] == "bg:#abcdef #000000"
    assert out["transcript-root"] != styles["transcript-root"]
    assert "#7f7f7f" in out["transcript-root"]
