"""Named soft-panel palettes — same ids as Sandwalk local-web Theme presets."""

from __future__ import annotations

from typing import TypedDict


class ModeColors(TypedDict):
    canvas_bg: str
    canvas_fg: str
    panel_bg: str
    panel_fg: str
    model_fg: str
    muted_fg: str
    sep_fg: str
    prompt_fg: str
    accent: str
    resume_fg: str
    system_fg: str
    sep_line: str


class ThemePalette(TypedDict):
    id: str
    name: str
    description: str
    swatches: list[str]
    light: ModeColors
    dark: ModeColors


def _mode(
    *,
    canvas_bg: str,
    canvas_fg: str,
    panel_bg: str,
    panel_fg: str,
    model_fg: str,
    muted_fg: str,
    sep_fg: str,
    prompt_fg: str,
    accent: str,
    resume_fg: str,
    system_fg: str,
    sep_line: str,
) -> ModeColors:
    return {
        "canvas_bg": canvas_bg,
        "canvas_fg": canvas_fg,
        "panel_bg": panel_bg,
        "panel_fg": panel_fg,
        "model_fg": model_fg,
        "muted_fg": muted_fg,
        "sep_fg": sep_fg,
        "prompt_fg": prompt_fg,
        "accent": accent,
        "resume_fg": resume_fg,
        "system_fg": system_fg,
        "sep_line": sep_line,
    }


# Order matches apps/local-web THEME_PALETTES (Default first, then product presets).
THEME_PALETTES: list[ThemePalette] = [
    {
        "id": "default",
        "name": "Default",
        "description": "Neutral light and dark — the current sandwalk look.",
        "swatches": ["#A3A3A3", "#4B4B4F", "#111111"],
        "light": _mode(
            canvas_bg="#ffffff",
            canvas_fg="#222222",
            panel_bg="#f5f5f5",
            panel_fg="#222222",
            model_fg="#333333",
            muted_fg="#8a8f98",
            sep_fg="#aaaaaa",
            prompt_fg="#555555",
            accent="#c9a227",
            resume_fg="#0f766e",
            system_fg="#7f8790",
            sep_line="#d0d0d0",
        ),
        "dark": _mode(
            canvas_bg="#121214",
            canvas_fg="#e8e8ea",
            panel_bg="#2a2a2e",
            panel_fg="#e8e8ea",
            model_fg="#e8e8ea",
            muted_fg="#9aa0a8",
            sep_fg="#6a6f78",
            prompt_fg="#c0c4cc",
            accent="#d4af37",
            resume_fg="#2dd4bf",
            system_fg="#9aa0a8",
            sep_line="#3f3f46",
        ),
    },
    {
        "id": "sandwalk",
        "name": "Sandwalk",
        "description": "Golden dune — cream, gold, terracotta (Dorado).",
        "swatches": ["#E1B34C", "#F2D9A0", "#3D2A18"],
        "light": _mode(
            canvas_bg="#faf6ee",
            canvas_fg="#3d2a18",
            panel_bg="#f7ebd4",
            panel_fg="#3d2a18",
            model_fg="#3d2a18",
            muted_fg="#8e5c3c",
            sep_fg="#c4a574",
            prompt_fg="#6b4423",
            accent="#8e5c3c",
            resume_fg="#8e5c3c",
            system_fg="#9a7e60",
            sep_line="#e2c49a",
        ),
        "dark": _mode(
            canvas_bg="#3d2a18",
            canvas_fg="#f2d9a0",
            panel_bg="#2e2418",
            panel_fg="#f2d9a0",
            model_fg="#f2d9a0",
            muted_fg="#c4a574",
            sep_fg="#8e5c3c",
            prompt_fg="#e1b34c",
            accent="#e1b34c",
            resume_fg="#e2b045",
            system_fg="#c4a574",
            sep_line="#4a3824",
        ),
    },
    {
        "id": "ember",
        "name": "Ember",
        "description": "Crimson red with a navy selected accent.",
        "swatches": ["#9C0000", "#070C52", "#12081c"],
        "light": _mode(
            canvas_bg="#faf5f6",
            canvas_fg="#1a1020",
            panel_bg="#f5e8ea",
            panel_fg="#1a1020",
            model_fg="#1a1020",
            muted_fg="#6a4050",
            sep_fg="#b08090",
            prompt_fg="#5a2030",
            accent="#9c0000",
            resume_fg="#070c52",
            system_fg="#7a6070",
            sep_line="#e0c8d0",
        ),
        "dark": _mode(
            # Slightly lifted navy so the full TUI canvas reads as Ember, not
            # near-black host terminal (panels stay #1a1028).
            canvas_bg="#12081c",
            canvas_fg="#f0d8dc",
            panel_bg="#1a1028",
            panel_fg="#f0d8dc",
            model_fg="#f0d8dc",
            muted_fg="#a08098",
            sep_fg="#6a4060",
            prompt_fg="#e8a0a8",
            accent="#e04040",
            resume_fg="#8a9cff",
            system_fg="#a08098",
            sep_line="#2a1840",
        ),
    },
    {
        "id": "verdant",
        "name": "Verdant",
        "description": "Lavender with a green selected accent.",
        "swatches": ["#BEB0FF", "#71D18F", "#1E1630"],
        "light": _mode(
            canvas_bg="#f7f5ff",
            canvas_fg="#1e1630",
            panel_bg="#f0ecff",
            panel_fg="#1e1630",
            model_fg="#1e1630",
            muted_fg="#6a6080",
            sep_fg="#a098c0",
            prompt_fg="#4a4070",
            accent="#71d18f",
            resume_fg="#2d6a4f",
            system_fg="#7a7090",
            sep_line="#d8d0f0",
        ),
        "dark": _mode(
            canvas_bg="#1e1630",
            canvas_fg="#e8e0ff",
            panel_bg="#221a38",
            panel_fg="#e8e0ff",
            model_fg="#e8e0ff",
            muted_fg="#a098c0",
            sep_fg="#6a6080",
            prompt_fg="#beb0ff",
            accent="#71d18f",
            resume_fg="#71d18f",
            system_fg="#a098c0",
            sep_line="#322850",
        ),
    },
    {
        "id": "fabienk",
        "name": "Fabienk",
        "description": "Angine de Poitrine — black void and gold accent.",
        "swatches": ["#F8B144", "#FFFFFF", "#000000"],
        "light": _mode(
            canvas_bg="#ffffff",
            canvas_fg="#0a0a0a",
            panel_bg="#f5f0e6",
            panel_fg="#0a0a0a",
            model_fg="#0a0a0a",
            muted_fg="#6a6a6a",
            sep_fg="#b0a090",
            prompt_fg="#4a4a4a",
            accent="#f8b144",
            resume_fg="#b8891f",
            system_fg="#7a7a7a",
            sep_line="#e0d8c8",
        ),
        "dark": _mode(
            canvas_bg="#000000",
            canvas_fg="#e8e0d0",
            panel_bg="#141414",
            panel_fg="#e8e0d0",
            model_fg="#e8e0d0",
            muted_fg="#8a8a8a",
            sep_fg="#5a5a5a",
            prompt_fg="#f8b144",
            accent="#f8b144",
            resume_fg="#ffc857",
            system_fg="#8a8a8a",
            sep_line="#2a2a2a",
        ),
    },
    {
        "id": "dune",
        "name": "Dune",
        "description": "Arrakis — teal haze, burnt umber, copper sand.",
        "swatches": ["#F0B85A", "#C87828", "#1A0E0A"],
        "light": _mode(
            canvas_bg="#f5f0e8",
            canvas_fg="#1a0e0a",
            panel_bg="#f0e8dc",
            panel_fg="#1a0e0a",
            model_fg="#1a0e0a",
            muted_fg="#7a6a58",
            sep_fg="#c4a070",
            prompt_fg="#5a3a20",
            accent="#e8a040",
            resume_fg="#c87828",
            system_fg="#8a7a68",
            sep_line="#e0d0b8",
        ),
        "dark": _mode(
            canvas_bg="#1a0e0a",
            canvas_fg="#e8dfd0",
            panel_bg="#241610",
            panel_fg="#e8dfd0",
            model_fg="#e8dfd0",
            muted_fg="#c4a070",
            sep_fg="#8a6040",
            prompt_fg="#f0b85a",
            accent="#f0b85a",
            resume_fg="#e09030",
            system_fg="#c4a070",
            sep_line="#3d2118",
        ),
    },
    {
        "id": "neonnoir",
        "name": "Neon Noir",
        "description": "Magenta neon, deep violet, holographic noir.",
        "swatches": ["#E83A8A", "#5C2A8A", "#0A0614"],
        "light": _mode(
            canvas_bg="#faf5fc",
            canvas_fg="#0a0614",
            panel_bg="#f0e8f4",
            panel_fg="#0a0614",
            model_fg="#0a0614",
            muted_fg="#6a5a7a",
            sep_fg="#b090b0",
            prompt_fg="#4a2a6a",
            accent="#e83a8a",
            resume_fg="#5c2a8a",
            system_fg="#7a6a8a",
            sep_line="#e0d0e8",
        ),
        "dark": _mode(
            canvas_bg="#0a0614",
            canvas_fg="#e8d8f0",
            panel_bg="#160a28",
            panel_fg="#e8d8f0",
            model_fg="#e8d8f0",
            muted_fg="#a090b8",
            sep_fg="#6a4a8a",
            prompt_fg="#ff4da6",
            accent="#e83a8a",
            resume_fg="#ff4da6",
            system_fg="#a090b8",
            sep_line="#2a1840",
        ),
    },
    {
        "id": "mirage",
        "name": "Mirage",
        "description": "Coral red primary with sand gold accents.",
        "swatches": ["#E84B3C", "#E2B045", "#2A2118"],
        "light": _mode(
            canvas_bg="#faf6f0",
            canvas_fg="#2a2118",
            panel_bg="#f4efe6",
            panel_fg="#2a2118",
            model_fg="#2a2118",
            muted_fg="#7a6a58",
            sep_fg="#c4a574",
            prompt_fg="#6b4423",
            accent="#e84b3c",
            resume_fg="#b8891f",
            system_fg="#8a7a68",
            sep_line="#e8dcc8",
        ),
        "dark": _mode(
            canvas_bg="#2a2118",
            canvas_fg="#e8dfd0",
            panel_bg="#2a2118",
            panel_fg="#e8dfd0",
            model_fg="#e8dfd0",
            muted_fg="#c4a574",
            sep_fg="#8a6a48",
            prompt_fg="#e2b045",
            accent="#e84b3c",
            resume_fg="#e2b045",
            system_fg="#c4a574",
            sep_line="#3d3229",
        ),
    },
    {
        "id": "mahal",
        "name": "Mahal",
        "description": "Terracotta, gold, and cream — warm architectural tones.",
        "swatches": ["#F2D9A0", "#E1B34C", "#8E5C3C"],
        "light": _mode(
            canvas_bg="#faf3e6",
            canvas_fg="#3a2418",
            panel_bg="#f7ebd4",
            panel_fg="#3a2418",
            model_fg="#3a2418",
            muted_fg="#8a6e55",
            sep_fg="#c4a070",
            prompt_fg="#6b4423",
            accent="#8e5c3c",
            resume_fg="#8e5c3c",
            system_fg="#9a7e60",
            sep_line="#e8d4a8",
        ),
        "dark": _mode(
            canvas_bg="#2a1a10",
            canvas_fg="#f2d9a0",
            panel_bg="#2e2014",
            panel_fg="#f2d9a0",
            model_fg="#f2d9a0",
            muted_fg="#d4a06a",
            sep_fg="#8e5c3c",
            prompt_fg="#e1b34c",
            accent="#e1b34c",
            resume_fg="#e07a5a",
            system_fg="#d4a06a",
            sep_line="#4a3424",
        ),
    },
    {
        "id": "darwin",
        "name": "Darwin",
        "description": "Forest green with sage surfaces — calm and scientific.",
        "swatches": ["#52B788", "#D8F3DC", "#0B1F14"],
        "light": _mode(
            canvas_bg="#f4faf5",
            canvas_fg="#0b1f14",
            panel_bg="#e8f5e9",
            panel_fg="#0b1f14",
            model_fg="#0b1f14",
            muted_fg="#52796f",
            sep_fg="#95b8a8",
            prompt_fg="#2d6a4f",
            accent="#2d6a4f",
            resume_fg="#2d6a4f",
            system_fg="#52796f",
            sep_line="#c8e6d0",
        ),
        "dark": _mode(
            canvas_bg="#0b1f14",
            canvas_fg="#d8f3dc",
            panel_bg="#12241a",
            panel_fg="#d8f3dc",
            model_fg="#d8f3dc",
            muted_fg="#74c69d",
            sep_fg="#3a6b50",
            prompt_fg="#52b788",
            accent="#52b788",
            resume_fg="#74c69d",
            system_fg="#6a9080",
            sep_line="#2d4a3c",
        ),
    },
    {
        "id": "tritanopia",
        "name": "Tritanopia",
        "description": "Indigo and magenta — blue/yellow color-vision safe.",
        "swatches": ["#3949AB", "#D6336C", "#0A0A1A"],
        "light": _mode(
            canvas_bg="#f5f5fb",
            canvas_fg="#0a0a1a",
            panel_bg="#eceef8",
            panel_fg="#0a0a1a",
            model_fg="#0a0a1a",
            muted_fg="#5a5a7a",
            sep_fg="#9a9ab8",
            prompt_fg="#3949ab",
            accent="#3949ab",
            resume_fg="#d6336c",
            system_fg="#6a6a8a",
            sep_line="#d0d0e8",
        ),
        "dark": _mode(
            canvas_bg="#0a0a1a",
            canvas_fg="#e8e0f0",
            panel_bg="#12122a",
            panel_fg="#e8e0f0",
            model_fg="#e8e0f0",
            muted_fg="#9a9ac0",
            sep_fg="#4a4a80",
            prompt_fg="#8a9cff",
            accent="#d6336c",
            resume_fg="#d6336c",
            system_fg="#9a9ac0",
            sep_line="#222248",
        ),
    },
    {
        "id": "protanopia",
        "name": "Protanopia & Deuteranopia",
        "description": "Violet and steel blue — red/green color-vision safe.",
        "swatches": ["#7C3AED", "#2C5AA0", "#12081F"],
        "light": _mode(
            canvas_bg="#f7f3fc",
            canvas_fg="#12081f",
            panel_bg="#efe8fa",
            panel_fg="#12081f",
            model_fg="#12081f",
            muted_fg="#5a4a7a",
            sep_fg="#a090c0",
            prompt_fg="#2c5aa0",
            accent="#7c3aed",
            resume_fg="#2c5aa0",
            system_fg="#6a5a8a",
            sep_line="#d8d0f0",
        ),
        "dark": _mode(
            canvas_bg="#12081f",
            canvas_fg="#e8e0f8",
            panel_bg="#1a1030",
            panel_fg="#e8e0f8",
            model_fg="#e8e0f8",
            muted_fg="#a090c8",
            sep_fg="#5a4090",
            prompt_fg="#a78bfa",
            accent="#7c3aed",
            resume_fg="#5b9cf0",
            system_fg="#a090c8",
            sep_line="#2a1848",
        ),
    },
]

_PALETTE_BY_ID = {p["id"]: p for p in THEME_PALETTES}


def palette_swatch_markup(pal: ThemePalette | dict) -> str:
    """One Rich cell blending two signature swatches (bright on deep)."""
    swatches = list(pal.get("swatches") or [])
    top = str(swatches[0] if swatches else "#888888")
    bottom = str(swatches[-1] if len(swatches) > 1 else top)
    # ▄ = lower half fg + upper half bg → one square, two theme colors.
    return f"[{top} on {bottom}]▄[/]"


# Aliases users might type in /theme …
_PALETTE_ALIASES = {
    "neon-noir": "neonnoir",
    "neon_noir": "neonnoir",
    "noir": "neonnoir",
    "bladerunner": "neonnoir",
    "protan": "protanopia",
    "deuteranopia": "protanopia",
    "deut": "protanopia",
    "tritan": "tritanopia",
    "dorado": "sandwalk",
}


def normalize_palette_id(raw: str | None) -> str | None:
    token = (
        str(raw or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("&", "")
    )
    if not token:
        return None
    # Aliases may still use hyphens; normalize those keys the same way.
    alias_key = str(raw or "").strip().lower().replace(" ", "")
    token = _PALETTE_ALIASES.get(alias_key, token)
    token = token.replace("-", "").replace("_", "")
    if token in _PALETTE_BY_ID:
        return token
    # Match by display name slug (e.g. "Neon Noir" → neonnoir).
    for pal in THEME_PALETTES:
        slug = (
            pal["name"]
            .lower()
            .replace(" ", "")
            .replace("&", "")
            .replace("-", "")
            .replace("_", "")
        )
        if token == slug or token == pal["id"]:
            return pal["id"]
    return None


def get_palette(palette_id: str | None) -> ThemePalette:
    pid = normalize_palette_id(palette_id) or "default"
    return _PALETTE_BY_ID.get(pid) or _PALETTE_BY_ID["default"]


def list_palettes() -> list[ThemePalette]:
    return list(THEME_PALETTES)
