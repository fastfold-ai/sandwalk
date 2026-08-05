"""Light/dark soft-panel theme + named Sandwalk UI palettes for the transcript TUI."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from functools import lru_cache
from typing import Any, Literal

from ui.terminal.theme_palettes import (
    get_palette,
    list_palettes,
    normalize_palette_id,
)

ThemeName = Literal["light", "dark"]


def panel_palette(
    theme: ThemeName | str | None = None,
    *,
    palette: str | None = None,
    config: Any = None,
) -> dict[str, str]:
    """Colors for compose / user soft panels and related chrome."""
    mode: ThemeName = "dark" if str(theme or "").strip().lower() == "dark" else "light"
    pid = palette if palette is not None else resolve_ui_palette(config)
    meta = get_palette(pid)
    return dict(meta[mode])


def _config_get(config: Any, key: str, default: Any = None) -> Any:
    if config is None:
        return default
    try:
        return config.get(key, default)
    except Exception:  # noqa: BLE001
        return default


def _config_theme_override(config: Any = None) -> ThemeName | None:
    raw = str(_config_get(config, "ui.theme") or "").strip().lower()
    if raw in {"light", "dark"}:
        return raw  # type: ignore[return-value]
    return None


def resolve_ui_palette(config: Any = None) -> str:
    """``ui.palette`` — named preset id (default)."""
    raw = str(_config_get(config, "ui.palette") or "default").strip()
    return normalize_palette_id(raw) or "default"


def _colorfgbg_is_dark() -> bool | None:
    """COLORFGBG is ``fg;bg`` (0–15). Low bg indices are usually dark."""
    raw = str(os.environ.get("COLORFGBG") or "").strip()
    if not raw or ";" not in raw:
        return None
    try:
        bg = int(raw.split(";")[-1])
    except ValueError:
        return None
    if bg in {7, 15}:
        return False
    if 0 <= bg <= 8:
        return True
    return None


def _env_flag_is_dark() -> bool | None:
    for key in ("LC_DARK_BG", "DARK_BG"):
        raw = str(os.environ.get(key) or "").strip().lower()
        if raw in {"1", "true", "yes", "dark"}:
            return True
        if raw in {"0", "false", "no", "light"}:
            return False
    cli = str(os.environ.get("CLI_THEME") or "").strip().lower()
    if cli in {"dark", "light"}:
        return cli == "dark"
    return None


@lru_cache(maxsize=1)
def _macos_interface_is_dark() -> bool | None:
    if os.uname().sysname != "Darwin":
        return None
    try:
        proc = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            check=False,
            capture_output=True,
            text=True,
            timeout=0.4,
        )
    except Exception:  # noqa: BLE001
        return None
    if proc.returncode != 0:
        return False
    return "dark" in (proc.stdout or "").strip().lower()


def _luminance_is_dark(r: float, g: float, b: float) -> bool:
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 0.45


@lru_cache(maxsize=1)
def _osc11_bg_is_dark() -> bool | None:
    """Ask the terminal for its background via OSC 11 (Warp/iTerm/xterm)."""
    if not sys.stdin.isatty() and not sys.stdout.isatty():
        return None
    try:
        import select
        import termios
        import tty
    except Exception:  # noqa: BLE001
        return None

    try:
        fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
    except OSError:
        return None

    old = None
    try:
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            os.read(fd, 4096)
        os.write(fd, b"\033]11;?\033\\")
        buf = b""
        while len(buf) < 128:
            ready, _, _ = select.select([fd], [], [], 0.15)
            if not ready:
                break
            chunk = os.read(fd, 64)
            if not chunk:
                break
            buf += chunk
            if b"rgb:" in buf and buf.count(b"/") >= 2:
                break
        text = buf.decode("utf-8", errors="ignore")
        match = re.search(
            r"rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)", text
        )
        if not match:
            return None

        def _chan(raw: str) -> float:
            value = int(raw, 16)
            width = max(1, len(raw))
            return value / ((16**width) - 1)

        return _luminance_is_dark(
            _chan(match.group(1)), _chan(match.group(2)), _chan(match.group(3))
        )
    except Exception:  # noqa: BLE001
        return None
    finally:
        if old is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:  # noqa: BLE001
                pass
        try:
            os.close(fd)
        except Exception:  # noqa: BLE001
            pass


def terminal_prefers_dark() -> bool:
    """Best-effort: env, COLORFGBG, terminal OSC 11, then macOS. Default light."""
    env = _env_flag_is_dark()
    if env is not None:
        return env
    fgbg = _colorfgbg_is_dark()
    if fgbg is not None:
        return fgbg
    osc = _osc11_bg_is_dark()
    if osc is not None:
        return osc
    mac = _macos_interface_is_dark()
    if mac is not None:
        return mac
    return False


def resolve_ui_theme(config: Any = None) -> ThemeName:
    """``ui.theme``: light | dark | auto (default)."""
    override = _config_theme_override(config)
    if override is not None:
        return override
    return "dark" if terminal_prefers_dark() else "light"


def _contrast_on(bg_hex: str) -> str:
    """Readable ink for text on ``bg_hex`` (selected completion row, etc.)."""
    token = str(bg_hex or "").strip().lstrip("#")
    if len(token) != 6:
        return "#ffffff"
    try:
        r = int(token[0:2], 16)
        g = int(token[2:4], 16)
        b = int(token[4:6], 16)
    except ValueError:
        return "#ffffff"
    # Relative luminance — light accents (gold) need dark ink.
    if (0.299 * r + 0.587 * g + 0.114 * b) > 160:
        return "#111111"
    return "#ffffff"


def transcript_style_dict(
    theme: ThemeName | str | None = None,
    *,
    palette: str | None = None,
    config: Any = None,
) -> dict[str, str]:
    """prompt_toolkit style entries for the owned transcript + compose panel."""
    mode: ThemeName = (
        resolve_ui_theme(config)
        if theme is None
        else ("dark" if str(theme).strip().lower() == "dark" else "light")
    )
    p = panel_palette(mode, palette=palette, config=config)
    canvas = f"bg:{p['canvas_bg']} {p['canvas_fg']}"
    panel = f"bg:{p['panel_bg']} {p['panel_fg']}"
    accent = p["accent"]
    on_accent = _contrast_on(accent)
    muted = p["muted_fg"]
    from ui.terminal.mcp_modal import mcp_modal_style_extras
    from ui.terminal.models_modal import models_modal_style_extras
    from ui.terminal.skills_modal import skills_modal_style_extras
    from ui.terminal.themes_modal import themes_modal_style_extras

    # Tool-call name: pale Dracula cyan washes out on light canvases.
    tool_fg = "bold #0284c7" if mode == "light" else "#7dd3fc"
    out = {
        # Full-TUI canvas (sidebar equivalent from Sandwalk UI presets).
        "": canvas,
        "transcript-root": canvas,
        "transcript-sep": p["sep_line"],
        "transcript-text": p["canvas_fg"],
        "transcript-user": panel,
        "transcript-user-accent": accent,
        "transcript-system": p["system_fg"],
        "transcript-resume": p["resume_fg"],
        "transcript-tool": tool_fg,
        "transcript-tool-ok": "#16a34a" if mode == "light" else "#98c379",
        "transcript-tool-error": "#dc2626" if mode == "light" else "#ff5555",
        "transcript-tool-detail": p["system_fg"],
        # Underlined absolute paths / URLs — click-to-open in the TUI.
        "transcript-link": (
            "underline bold #0284c7" if mode == "light" else "underline bold #7dd3fc"
        ),
        "transcript-selected": "reverse",
        "image-chip": "bold #111111 bg:#f0a030",
        # Skills picker inserts — pink chip (brand-adjacent magenta).
        "skill-chip": "bold #111111 bg:#f472b6",
        # MCP picker inserts — cyan chip (distinct from skill pink).
        "mcp-chip": "bold #111111 bg:#22d3ee",
        "transcript-compose": panel,
        "transcript-compose.prompt": f"bold {p['prompt_fg']}",
        "transcript-compose-accent": f"bg:{p['canvas_bg']} {accent}",
        "transcript-status": f"bg:{p['canvas_bg']} {muted}",
        # Slash / @ menu — same panel as compose, accent selection (opencode-like).
        "completion-menu": panel,
        "completion-menu.completion": panel,
        "completion-menu.completion.current": f"bg:{accent} {on_accent} bold",
        "completion-menu.meta.completion": f"bg:{p['panel_bg']} {muted}",
        "completion-menu.meta.completion.current": f"bg:{accent} {on_accent}",
        "completion-menu-accent": f"bg:{p['panel_bg']} {accent}",
        # Thin muted scrollbar (not accent — accent is the left ┃ only).
        "scrollbar.background": f"bg:{p['panel_bg']}",
        "scrollbar.button": f"bg:{p['sep_fg']}",
        "scrollbar.arrow": f"bg:{p['panel_bg']} {muted}",
    }
    out.update(themes_modal_style_extras(p))
    out.update(models_modal_style_extras(p))
    out.update(skills_modal_style_extras(p))
    out.update(mcp_modal_style_extras(p))
    return out


def clear_theme_cache() -> None:
    """Drop cached OS/OSC probes (tests or forced refresh)."""
    _macos_interface_is_dark.cache_clear()
    _osc11_bg_is_dark.cache_clear()


def clear_appearance_cache() -> None:
    """Re-check macOS appearance without re-querying OSC 11 mid-session."""
    _macos_interface_is_dark.cache_clear()


__all__ = [
    "ThemeName",
    "clear_appearance_cache",
    "clear_theme_cache",
    "get_palette",
    "list_palettes",
    "normalize_palette_id",
    "panel_palette",
    "resolve_ui_palette",
    "resolve_ui_theme",
    "terminal_prefers_dark",
    "transcript_style_dict",
    "_contrast_on",
]
