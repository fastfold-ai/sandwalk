"""Self-updating Rich renderable: spinner + rotating word + elapsed time."""

from __future__ import annotations

import time

from ui.status.gradient import apply_gradient
from ui.status.spinners import SPINNERS


class _ThinkingRenderable:
    """Self-updating renderable: Animated spinner + rotating bio-themed word + elapsed time.

    Computes display state from wall-clock time on each refresh, so no
    separate update thread is needed — Rich's Live refresh handles it.
    """

    def __init__(self, words, spinner_style="benzene_breathing"):
        self.words = words
        self.start_time = time.time()

        # Load spinner configuration
        spinner_conf = SPINNERS.get(spinner_style, SPINNERS["benzene_breathing"])
        self.frames = spinner_conf["frames"]
        self.interval_ms = spinner_conf["interval_ms"]

    def __rich_console__(self, console, options):
        elapsed = time.time() - self.start_time

        # Determine current word (rotates every 3 seconds)
        word_idx = int(elapsed / 3) % len(self.words)
        word = self.words[word_idx]

        # Determine current spinner frame
        frame_idx = int(elapsed * (1000 / self.interval_ms)) % len(self.frames)
        frame_str = self.frames[frame_idx]

        if elapsed < 60:
            time_str = f"{elapsed:.0f}s"
        else:
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            time_str = f"{mins}m {secs}s"

        # Apply gradient to spinner frame
        output = apply_gradient(frame_str, elapsed_s=elapsed)
        output.append("  ")
        output.append(f"{word}…", style="cyan")
        output.append("  ")
        output.append(f"({time_str})", style="dim")

        yield output
