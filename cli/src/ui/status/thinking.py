"""ThinkingStatus context manager: Claude Code-style thinking indicator."""

from __future__ import annotations

import random

from rich.live import Live

from ui.status.renderable import _ThinkingRenderable
from ui.status.words import THINKING_WORDS


class ThinkingStatus:
    """Context manager showing a Claude Code-style thinking status.

    Displays a spinner with rotating drug-discovery themed words and an
    elapsed time counter. The status disappears when the context exits.

    The Rich Live daemon thread may stall when the GIL is held by
    CPU-bound tool code running via ``asyncio.to_thread()``.  To keep
    the timer ticking, call :meth:`kick` from the async message loop
    or start :meth:`async_refresh_task` as a background asyncio task.

    Args:
        console: Rich Console instance.
        phase: One of the keys in THINKING_WORDS (planning, synthesizing, etc.).
    """

    def __init__(self, console, phase="planning"):
        from agent.config import Config
        self.console = console
        words = list(THINKING_WORDS.get(phase, THINKING_WORDS["planning"]))
        random.shuffle(words)

        # Determine spinner style from config
        try:
            cfg = Config.load()
            spinner_style = cfg.get("ui.spinner", "benzene_breathing")
        except Exception:
            spinner_style = "benzene_breathing"

        self._renderable = _ThinkingRenderable(words, spinner_style=spinner_style)
        self._live = None
        self._async_task = None

    def __enter__(self):
        self._live = Live(
            self._renderable,
            console=self.console,
            refresh_per_second=8,
            transient=True,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        self._cancel_async_task()
        if self._live is not None:
            return self._live.__exit__(*args)

    def kick(self):
        """Force a single refresh of the Live display.

        Call from the async message loop to keep the timer updating
        even when the daemon thread is GIL-starved.
        """
        if self._live is not None:
            try:
                self._live.refresh()
            except Exception:
                pass

    def start_async_refresh(self):
        """Start a background asyncio task that refreshes the display.

        This supplements the Rich Live daemon thread: while a tool runs
        in ``asyncio.to_thread()``, the event loop still gets cycles
        during I/O waits and can drive this coroutine to keep the timer
        updating.  Call :meth:`stop` or :meth:`_cancel_async_task` to
        stop.
        """
        import asyncio

        async def _refresh_loop():
            try:
                while True:
                    await asyncio.sleep(0.125)
                    self.kick()
            except asyncio.CancelledError:
                pass

        try:
            loop = asyncio.get_running_loop()
            self._async_task = loop.create_task(_refresh_loop())
        except RuntimeError:
            pass  # No running event loop — daemon thread is the fallback

    def _cancel_async_task(self):
        if self._async_task is not None:
            self._async_task.cancel()
            self._async_task = None

    def stop(self):
        """Programmatically stop the animation (idempotent)."""
        self._cancel_async_task()
        if self._live is not None:
            try:
                self._live.__exit__(None, None, None)
            except Exception:
                pass
            self._live = None
