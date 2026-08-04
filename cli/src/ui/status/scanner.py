"""Knight-rider / comet scanner for the busy toolbar."""

from __future__ import annotations

# Bright head → fading trail (green) — classic toolbar.
_TRAIL = (
    "#c8ffd8",  # head
    "#7dffa0",
    "#50fa7b",
    "#2ecc71",
    "#1a8f4a",
    "#0f4a28",
)
_INACTIVE = "#1a2a1e"

# Compose accent (matches transcript gold bar / _COMPOSE_ACCENT).
_TRAIL_GOLD = (
    "#f0e0a0",  # head
    "#e0c86a",
    "#c9a227",
    "#9a7429",
    "#6e5320",
    "#3d2e12",
)
_INACTIVE_GOLD = "#ebe4d4"

_ACTIVE_CHAR = "■"
_INACTIVE_CHAR = "⬝"
_PALETTES = {
    "green": (_TRAIL, _INACTIVE),
    "gold": (_TRAIL_GOLD, _INACTIVE_GOLD),
    # Alias kept for older call sites.
    "purple": (_TRAIL_GOLD, _INACTIVE_GOLD),
}


def _color_index(
    frame: int,
    char: int,
    width: int,
    *,
    trail: int,
    hold_end: int,
    hold_start: int,
) -> int:
    """Return trail index (0=brightest) or -1 for inactive.

    Cycle: forward → hold end → backward → hold start.
    """
    forward = width
    backward = width - 1
    cycle = forward + hold_end + backward + hold_start
    t = frame % cycle

    if t < forward:
        active = t
        moving_forward = True
        hold_progress = 0
        holding = False
    elif t < forward + hold_end:
        active = width - 1
        moving_forward = True
        hold_progress = t - forward
        holding = True
    elif t < forward + hold_end + backward:
        active = width - 2 - (t - forward - hold_end)
        moving_forward = False
        hold_progress = 0
        holding = False
    else:
        active = 0
        moving_forward = False
        hold_progress = t - forward - hold_end - backward
        holding = True

    distance = (active - char) if moving_forward else (char - active)
    if holding:
        return distance + hold_progress if 0 <= distance < trail else -1
    if distance == 0:
        return 0
    if 0 < distance < trail:
        return distance
    return -1


def scanner_cells(
    frame: int,
    *,
    width: int = 10,
    trail: int | None = None,
    hold_end: int = 4,
    hold_start: int = 6,
    palette: str = "green",
) -> list[tuple[str, str]]:
    """Return ``[(hex_color, char), ...]`` for one scanner frame."""
    colors, inactive = _PALETTES.get(palette, _PALETTES["green"])
    length = trail if trail is not None else len(colors)
    cells: list[tuple[str, str]] = []
    for i in range(width):
        idx = _color_index(
            frame,
            i,
            width,
            trail=length,
            hold_end=hold_end,
            hold_start=hold_start,
        )
        if idx < 0 or idx >= len(colors):
            cells.append((inactive, _INACTIVE_CHAR))
        else:
            cells.append((colors[idx], _ACTIVE_CHAR))
    return cells


def scanner_html(
    frame: int,
    *,
    width: int = 10,
    palette: str = "green",
) -> str:
    """prompt_toolkit HTML snippet for one scanner frame."""
    parts = []
    for color, char in scanner_cells(frame, width=width, palette=palette):
        parts.append(f'<style fg="{color}" bg="default">{char}</style>')
    return "".join(parts)


def scanner_frame_count(*, width: int = 10, hold_end: int = 4, hold_start: int = 6) -> int:
    return width + hold_end + (width - 1) + hold_start
