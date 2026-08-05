"""Smooth resize: debounce SIGWINCH and never erase_down mid-drag."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from ui.terminal.transcript.resize import (
    SyncUpdateGate,
    _RESIZE_DEBOUNCE_S,
    install_smooth_resize,
)


def test_sync_update_gate_nests_without_duplicate_brackets():
    out = MagicMock()
    gate = SyncUpdateGate()
    gate.begin(out)
    gate.begin(out)
    assert out.write_raw.call_count == 1
    assert out.write_raw.call_args.args[0].endswith("2026h")
    gate.end(out)
    assert out.write_raw.call_count == 1  # still nested
    gate.end(out)
    assert out.write_raw.call_count == 2
    assert out.write_raw.call_args.args[0].endswith("2026l")
    out.flush.assert_called()


def test_install_smooth_resize_skips_erase_and_debounces():
    redraws: list[str] = []
    erase = MagicMock()

    class FakeRenderer:
        def __init__(self):
            self._last_screen = object()
            self._last_size = object()

        def erase(self, *args, **kwargs):
            erase(*args, **kwargs)

    renderer = FakeRenderer()
    output = MagicMock()
    loop = MagicMock()
    scheduled: list = []

    def call_soon_threadsafe(fn):
        scheduled.append(fn)

    loop.call_soon_threadsafe.side_effect = call_soon_threadsafe
    loop.is_closed.return_value = False

    app = SimpleNamespace(
        is_running=True,
        renderer=renderer,
        output=output,
        loop=loop,
        _redraw=lambda: redraws.append("draw"),
        _request_absolute_cursor_position=MagicMock(),
        _on_resize=lambda: None,
    )

    install_smooth_resize(app)

    # Burst of SIGWINCH — should schedule one settled paint only.
    app._on_resize()
    app._on_resize()
    app._on_resize()
    assert erase.call_count == 0
    assert redraws == []

    deadline = time.time() + _RESIZE_DEBOUNCE_S + 0.4
    while time.time() < deadline and not scheduled:
        time.sleep(0.02)
    assert len(scheduled) == 1

    scheduled[0]()
    assert erase.call_count == 0
    assert redraws == ["draw"]
    assert renderer._last_screen is None
    assert renderer._last_size is None
    # Sync brackets wrapped the paint.
    writes = [c.args[0] for c in output.write_raw.call_args_list]
    assert any(w.endswith("2026h") for w in writes)
    assert any(w.endswith("2026l") for w in writes)
