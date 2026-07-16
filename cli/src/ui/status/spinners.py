"""Spinner frame/animation definitions."""

from __future__ import annotations

_BASE = "\u2881\u2822\u2814\u2848\u2814\u2822"  # ⢁⠢⠔⡈⠔⠢
DNA_HELIX_FRAMES: list[str] = [_BASE[i:] + _BASE[:i] for i in range(len(_BASE))]

SPINNERS = {
    "benzene_breathing": {
        "frames": ['⬡', '⎔', '⌬', '⬢', '⌬', '⎔'],
        "interval_ms": 125,
    },
    "dna_helix": {
        "frames": DNA_HELIX_FRAMES,
        "interval_ms": 125,
    },
}
