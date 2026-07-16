"""Temporal color gradient applied to the spinner frame."""

from __future__ import annotations

import math

from rich.text import Text


def apply_gradient(text: str, elapsed_s: float = 0.0) -> Text:
    """Apply a #50fa7b (neon green) to #00e5ff (cyan) temporal gradient."""
    if not text:
        return Text("")

    # #50fa7b (80, 250, 123) to #00e5ff (0, 229, 255)
    r1, g1, b1 = 80, 250, 123
    r2, g2, b2 = 0, 229, 255

    # Cycle over 3 spinner loops (6 frames × 125ms × 3 = 2.25s)
    cycle_duration_s = 2.25
    t = (math.sin((elapsed_s % cycle_duration_s) * (2 * math.pi / cycle_duration_s)) + 1) / 2
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    hex_color = f"#{r:02x}{g:02x}{b:02x}"

    result = Text()
    result.append(text, style=hex_color)
    return result
