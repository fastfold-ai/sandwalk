"""Debounced, erase-free resize for the fullscreen transcript TUI.

prompt_toolkit's default ``Application._on_resize`` does:

1. ``renderer.erase()`` → ``erase_down`` + flush  (blank flash)
2. CPR request
3. ``_redraw()``

That clear-then-paint split is the flicker. OpenCode / OpenTUI avoid it by
debouncing SIGWINCH (~100ms) and never blanking mid-drag; Codex tracked the
same bug when a clear escapes a DEC 2026 synchronized-update bracket.

We:
- coalesce SIGWINCH for ``_RESIZE_DEBOUNCE_S``
- skip ``erase()`` entirely (keep the previous frame until the new one lands)
- wrap the settled redraw in nest-safe CSI ``?2026`` sync brackets
"""

from __future__ import annotations

import threading
import time
from typing import Any

# Match OpenTUI CliRenderer.resizeDebounceDelay default.
_RESIZE_DEBOUNCE_S = 0.10

_SYNC_BEGIN = "\x1b[?2026h"
_SYNC_END = "\x1b[?2026l"


class SyncUpdateGate:
    """Nest-safe DEC 2026 synchronized-update brackets."""

    def __init__(self) -> None:
        self._depth = 0
        self._lock = threading.Lock()

    def begin(self, output: Any) -> None:
        with self._lock:
            if self._depth == 0:
                try:
                    output.write_raw(_SYNC_BEGIN)
                except Exception:  # noqa: BLE001
                    pass
            self._depth += 1

    def end(self, output: Any) -> None:
        with self._lock:
            if self._depth <= 0:
                return
            self._depth -= 1
            if self._depth == 0:
                try:
                    output.write_raw(_SYNC_END)
                    output.flush()
                except Exception:  # noqa: BLE001
                    pass


def install_smooth_resize(app: Any, *, sync: SyncUpdateGate | None = None) -> SyncUpdateGate:
    """Replace ``app._on_resize`` with a debounced, erase-free handler."""
    gate = sync or SyncUpdateGate()
    state = {"token": 0}
    lock = threading.Lock()

    def _paint_settled() -> None:
        if not getattr(app, "is_running", False):
            return
        renderer = getattr(app, "renderer", None)
        output = getattr(app, "output", None)
        if renderer is None or output is None:
            return
        try:
            # Force a full paint without blanking the live viewport first.
            renderer._last_screen = None
            renderer._last_size = None
        except Exception:  # noqa: BLE001
            pass
        try:
            output.hide_cursor()
        except Exception:  # noqa: BLE001
            pass
        gate.begin(output)
        try:
            # No erase_down — that flush is the blank flash between clear and paint.
            if hasattr(app, "_request_absolute_cursor_position"):
                try:
                    app._request_absolute_cursor_position()
                except Exception:  # noqa: BLE001
                    pass
            app._redraw()
        finally:
            gate.end(output)
            try:
                output.show_cursor()
            except Exception:  # noqa: BLE001
                pass

    def _on_resize_debounced() -> None:
        with lock:
            state["token"] += 1
            token = state["token"]

        def _flush() -> None:
            time.sleep(_RESIZE_DEBOUNCE_S)
            with lock:
                if token != state["token"]:
                    return
            loop = getattr(app, "loop", None)
            if loop is None or loop.is_closed():
                return
            try:
                loop.call_soon_threadsafe(_paint_settled)
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(
            target=_flush, daemon=True, name="sandwalk-smooth-resize"
        ).start()

    app._on_resize = _on_resize_debounced
    return gate
