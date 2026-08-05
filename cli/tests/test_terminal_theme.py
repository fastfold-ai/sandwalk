"""Light/dark soft-panel theme detection, palettes, and /themes wiring."""

from __future__ import annotations

from ui.terminal.theme import (
    clear_theme_cache,
    panel_palette,
    resolve_ui_palette,
    resolve_ui_theme,
    terminal_prefers_dark,
    transcript_style_dict,
)
from ui.terminal.theme_palettes import list_palettes, normalize_palette_id


def test_palette_swatch_is_single_two_tone_square():
    from ui.terminal.theme_palettes import get_palette, palette_swatch_markup

    markup = palette_swatch_markup(get_palette("sandwalk"))
    assert markup.count("▄") == 1
    assert "██" not in markup
    assert "#E1B34C" in markup
    assert "#3D2A18" in markup
    assert " on " in markup


def test_ui_palettes_match_sandwalk_web_preset_ids():
    ids = {p["id"] for p in list_palettes()}
    assert ids == {
        "default",
        "sandwalk",
        "ember",
        "verdant",
        "fabienk",
        "dune",
        "neonnoir",
        "mirage",
        "mahal",
        "darwin",
        "tritanopia",
        "protanopia",
    }


def test_palette_aliases():
    assert normalize_palette_id("neon-noir") == "neonnoir"
    assert normalize_palette_id("bladerunner") == "neonnoir"
    assert normalize_palette_id("Dorado") == "sandwalk"
    assert normalize_palette_id("protanopia") == "protanopia"


def test_panel_palette_dark_is_raised_charcoal_not_white():
    light = panel_palette("light", palette="default")
    dark = panel_palette("dark", palette="default")
    assert light["panel_bg"] == "#f5f5f5"
    assert dark["panel_bg"] == "#2a2a2e"
    assert dark["panel_bg"] != light["panel_bg"]


def test_named_palette_changes_accent():
    sand = panel_palette("dark", palette="sandwalk")
    neon = panel_palette("dark", palette="neonnoir")
    assert sand["accent"] == "#e1b34c"
    assert neon["accent"] == "#e83a8a"
    assert sand["panel_bg"] != neon["panel_bg"]


def test_transcript_style_embeds_panel_bg():
    dark = transcript_style_dict("dark", palette="default")
    assert "bg:#2a2a2e" in dark["transcript-compose"]
    assert "bg:#2a2a2e" in dark["transcript-user"]
    light = transcript_style_dict("light", palette="default")
    assert "bg:#f5f5f5" in light["transcript-compose"]


def test_transcript_tool_color_stronger_on_light():
    light = transcript_style_dict("light", palette="default")
    dark = transcript_style_dict("dark", palette="default")
    assert "#0284c7" in light["transcript-tool"]
    assert "bold" in light["transcript-tool"]
    assert "#7dd3fc" in dark["transcript-tool"]
    assert light["transcript-tool"] != dark["transcript-tool"]


def test_transcript_style_paints_full_tui_canvas():
    """Named palettes set the whole TUI background (sidebar → canvas)."""
    noir = transcript_style_dict("dark", palette="neonnoir")
    assert "bg:#0a0614" in noir[""]
    assert "bg:#0a0614" in noir["transcript-root"]
    assert "bg:#0a0614" in noir["transcript-status"]
    sand = transcript_style_dict("dark", palette="sandwalk")
    assert "bg:#3d2a18" in sand["transcript-root"]
    assert sand["transcript-root"] != noir["transcript-root"]


def test_completion_menu_follows_theme_accent_and_panel():
    """Slash menu matches compose panel; selection uses palette accent."""
    from ui.terminal.theme import _contrast_on

    sand = transcript_style_dict("dark", palette="sandwalk")
    assert "bg:#2e2418" in sand["completion-menu"]  # sandwalk dark panel
    assert "bg:#e1b34c" in sand["completion-menu.completion.current"]
    assert _contrast_on("#e1b34c") == "#111111"
    assert "#111111" in sand["completion-menu.completion.current"]
    assert "bg:#2e2418" in sand["completion-menu-accent"]
    assert "#e1b34c" in sand["completion-menu-accent"]

    noir = transcript_style_dict("dark", palette="neonnoir")
    assert "bg:#e83a8a" in noir["completion-menu.completion.current"]
    assert sand["completion-menu.completion.current"] != noir[
        "completion-menu.completion.current"
    ]


class _Cfg:
    def __init__(self, *, theme: str = "auto", palette: str = "default"):
        self.theme = theme
        self.palette = palette

    def get(self, key, default=None):
        if key == "ui.theme":
            return self.theme
        if key == "ui.palette":
            return self.palette
        return default


def test_config_ui_theme_override(monkeypatch):
    clear_theme_cache()
    monkeypatch.setenv("COLORFGBG", "15;0")  # would prefer dark
    assert resolve_ui_theme(_Cfg(theme="light")) == "light"
    assert resolve_ui_theme(_Cfg(theme="dark")) == "dark"


def test_resolve_ui_palette():
    assert resolve_ui_palette(_Cfg(palette="sandwalk")) == "sandwalk"
    assert resolve_ui_palette(_Cfg(palette="Neon Noir")) == "neonnoir"
    assert resolve_ui_palette(_Cfg(palette="nope")) == "default"


def test_colorfgbg_dark_detection(monkeypatch):
    clear_theme_cache()
    monkeypatch.delenv("LC_DARK_BG", raising=False)
    monkeypatch.delenv("DARK_BG", raising=False)
    monkeypatch.delenv("CLI_THEME", raising=False)
    monkeypatch.setenv("COLORFGBG", "15;0")
    monkeypatch.setattr("ui.terminal.theme._macos_interface_is_dark", lambda: None)
    monkeypatch.setattr("ui.terminal.theme._osc11_bg_is_dark", lambda: None)
    assert terminal_prefers_dark() is True
    monkeypatch.setenv("COLORFGBG", "0;15")
    assert terminal_prefers_dark() is False


def test_osc11_preferred_over_macos(monkeypatch):
    clear_theme_cache()
    monkeypatch.delenv("LC_DARK_BG", raising=False)
    monkeypatch.delenv("DARK_BG", raising=False)
    monkeypatch.delenv("CLI_THEME", raising=False)
    monkeypatch.delenv("COLORFGBG", raising=False)
    monkeypatch.setattr("ui.terminal.theme._osc11_bg_is_dark", lambda: True)
    monkeypatch.setattr("ui.terminal.theme._macos_interface_is_dark", lambda: False)
    assert terminal_prefers_dark() is True


def test_resolve_auto_uses_detection(monkeypatch):
    clear_theme_cache()
    monkeypatch.setattr("ui.terminal.theme.terminal_prefers_dark", lambda: True)
    assert resolve_ui_theme(_Cfg(theme="auto")) == "dark"
    monkeypatch.setattr("ui.terminal.theme.terminal_prefers_dark", lambda: False)
    assert resolve_ui_theme(_Cfg(theme="auto")) == "light"


def test_theme_command_sets_palette(monkeypatch):
    from unittest.mock import MagicMock

    from ui.terminal.theme_command import _ThemeCommandMixin

    class T(_ThemeCommandMixin):
        pass

    t = T()
    t.console = MagicMock()
    t.session = MagicMock()
    t._refresh_ui_theme = MagicMock()

    saved = {}

    class FakeCfg:
        def get(self, key, default=None):
            return saved.get(key, default)

        def set(self, key, value):
            saved[key] = value

        def save(self):
            pass

    monkeypatch.setattr("agent.config.Config.load", lambda: FakeCfg())
    t._handle_theme_command("/themes sandwalk")
    assert saved.get("ui.palette") == "sandwalk"
    t._handle_theme_command("/themes dark")
    assert saved.get("ui.theme") == "dark"
    t._refresh_ui_theme.assert_called()


def test_theme_interactive_list_has_no_descriptions(monkeypatch):
    from unittest.mock import MagicMock

    from ui.terminal.theme_command import _ThemeCommandMixin

    class T(_ThemeCommandMixin):
        pass

    t = T()
    t.console = MagicMock()
    t.session = MagicMock()
    t._refresh_ui_theme = MagicMock()
    t._prompt_session = MagicMock()
    t._prompt_session.prompt.return_value = ""

    saved = {"ui.theme": "light", "ui.palette": "fabienk"}

    class FakeCfg:
        def get(self, key, default=None):
            return saved.get(key, default)

        def set(self, key, value):
            saved[key] = value

        def save(self):
            pass

    monkeypatch.setattr("agent.config.Config.load", lambda: FakeCfg())
    t._handle_theme_command("/themes")
    printed = " ".join(str(c) for c in t.console.print.call_args_list)
    assert "Palettes" in printed or "Themes" in printed
    assert "Fabienk" in printed or "fabienk" in printed
    assert "Angine de Poitrine" not in printed
    assert "Arrakis" not in printed
    assert "Neutral light and dark" not in printed


def test_theme_choice_ignores_exit_sentinel():
    from unittest.mock import MagicMock

    from ui.terminal.theme_command import _ThemeCommandMixin

    class T(_ThemeCommandMixin):
        pass

    t = T()
    t.console = MagicMock()
    t._apply_theme_mode = MagicMock()
    t._apply_theme_palette = MagicMock()
    t._resolve_theme_choice(MagicMock(), "__EXIT__", list_palettes())
    t._apply_theme_mode.assert_not_called()
    t._apply_theme_palette.assert_not_called()
    printed = " ".join(str(c) for c in t.console.print.call_args_list)
    assert "Cancelled" in printed
