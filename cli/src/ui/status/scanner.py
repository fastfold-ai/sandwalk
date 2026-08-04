"""OpenCode-like knight-rider / comet scanner for the busy toolbar."""

from __future__ import annotations

# Bright head → fading trail (green).
_TRAIL = (
    "#c8ffd8",  # head
    "#7dffa0",
    "#50fa7b",
    "#2ecc71",
    "#1a8f4a",
    "#0f4a28",
)
_INACTIVE = "#1a2a1e"
_ACTIVE_CHAR = "■"
_INACTIVE_CHAR = "⬝"


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

    Cycle: forward → hold end → backward → hold start (OpenCode-style).
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
) -> list[tuple[str, str]]:
    """Return ``[(hex_color, char), ...]`` for one scanner frame."""
    length = trail if trail is not None else len(_TRAIL)
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
        if idx < 0 or idx >= len(_TRAIL):
            cells.append((_INACTIVE, _INACTIVE_CHAR))
        else:
            cells.append((_TRAIL[idx], _ACTIVE_CHAR))
    return cells


def scanner_html(
    frame: int,
    *,
    width: int = 10,
) -> str:
    """prompt_toolkit HTML snippet for one scanner frame."""
    parts = []
    for color, char in scanner_cells(frame, width=width):
        parts.append(f'<style fg="{color}" bg="default">{char}</style>')
    return "".join(parts)


def scanner_frame_count(*, width: int = 10, hold_end: int = 4, hold_start: int = 6) -> int:
    return width + hold_end + (width - 1) + hold_start
