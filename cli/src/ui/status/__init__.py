"""
Thinking status display for ct.

Shows a DNA double-helix animation with rotating drug discovery themed words
and an elapsed time counter. The helix scrolls at 8fps while words rotate
every ~3 seconds.

Usage:
    with ThinkingStatus(console, "planning"):
        result = llm.chat(...)
"""

from __future__ import annotations

import time  # noqa: F401  (exposed as ui.status.time for test patching)

from ui.status.gradient import apply_gradient
from ui.status.renderable import _ThinkingRenderable
from ui.status.scanner import scanner_html, scanner_cells
from ui.status.spinners import DNA_HELIX_FRAMES, SPINNERS
from ui.status.thinking import ThinkingStatus
from ui.status.words import FOOTER_PAST_TENSE_WORDS, THINKING_WORDS

__all__ = [
    "DNA_HELIX_FRAMES",
    "SPINNERS",
    "apply_gradient",
    "scanner_cells",
    "scanner_html",
    "THINKING_WORDS",
    "FOOTER_PAST_TENSE_WORDS",
    "_ThinkingRenderable",
    "ThinkingStatus",
]
