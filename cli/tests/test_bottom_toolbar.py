"""Coverage for idle / busy / hint paths in the CLI bottom toolbar."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from ui.terminal import InteractiveTerminal  # type: ignore[import-untyped]
from ui.terminal.bottom_toolbar import _BottomToolbarMixin


@pytest.fixture
def terminal():
    with patch("ui.terminal.InteractiveTerminal.__init__", return_value=None):
        t = InteractiveTerminal.__new__(InteractiveTerminal)
        t.session = MagicMock()
        t.session.verbose = False
        t.session.current_model = "gemini-3.1-flash-lite"
        t.session.config.get.side_effect = lambda key, default=None: {
            "agent.plan_preview": False,
            "ui.spinner": "benzene_breathing",
        }.get(key, default)
        t._show_exit_hint = False
        t._show_interrupt_hint = False
        t._verbose_hint = None
        t._cli_specialist_label = None
        t._cli_sandbox_label = "Local Sandbox"
        t._run_lock = MagicMock()
        t._run_lock.__enter__ = MagicMock(return_value=None)
        t._run_lock.__exit__ = MagicMock(return_value=False)
        t._queued_queries = []
        t._active_activity = None
        t._active_activity_updated_at = time.time()
        t._active_query_started_at = time.time()
        t._active_input_tokens = 0
        t._active_output_tokens = 0
        t._active_streamed_chars = 0
        t._toolbar_words = ["folding", "docking"]
        t._toolbar_word_interval_s = 1.0
        t._toolbar_frames = ["⠋", "⠙"]
        t._toolbar_frame_interval_s = 0.2
        t._model_display_name = MagicMock(return_value="gemini-3.1-flash-lite")
        t._current_compatible_backend_label = MagicMock(return_value=None)
        t._has_active_query = MagicMock(return_value=False)
        t._mention_completing = MagicMock(return_value=False)
        t._estimate_output_tokens_from_chars = MagicMock(return_value=3)
        t._toolbar_spinner_markup = MagicMock(return_value="[*]")
        t._session_sdk_turn_rows = []
        t._session_sdk_input_tokens = 0
        return t


def test_exit_and_interrupt_hints(terminal):
    terminal._show_exit_hint = True
    assert "Ctrl+C again to exit" in str(terminal._bottom_toolbar())

    terminal._show_exit_hint = False
    terminal._show_interrupt_hint = True
    assert "Interrupt requested" in str(terminal._bottom_toolbar())


def test_mention_tab_bar(terminal):
    terminal._mention_completing.return_value = True
    terminal._merged_completer = SimpleNamespace(
        mention_completer=SimpleNamespace(
            TABS=["Files", "Skills"],
            _active_tab=0,
        )
    )
    text = str(terminal._bottom_toolbar())
    assert "[Files]" in text
    assert "Skills" in text


def test_active_query_toolbar_elapsed_and_usage(terminal):
    terminal._has_active_query.return_value = True
    terminal._active_activity = "searching"
    terminal._active_activity_updated_at = time.time()
    terminal._active_query_started_at = time.time() - 5
    terminal._active_input_tokens = 12
    terminal._active_output_tokens = 4
    text = str(terminal._bottom_toolbar())
    assert "running 5s" in text
    assert "↑ 12" in text
    assert "↓ 4 tokens" in text
    assert "/interrupt" in text


def test_active_query_stale_status_and_minute_elapsed(terminal):
    terminal._has_active_query.return_value = True
    terminal._active_activity = "thinking..."
    terminal._active_activity_updated_at = time.time() - 10
    terminal._active_query_started_at = time.time() - 75
    terminal._queued_queries = ["next"]
    terminal._active_input_tokens = 0
    terminal._active_output_tokens = 0
    terminal._active_streamed_chars = 40
    text = str(terminal._bottom_toolbar())
    assert "running 1m15s" in text
    assert "queued 1" in text
    assert "↑ …" in text
    assert "↓ 3 tokens" in text


def test_idle_toolbar_plan_modal_colors(terminal):
    terminal.session.config.get.side_effect = lambda key, default=None: {
        "agent.plan_preview": True,
    }.get(key, default)
    terminal._cli_specialist_label = "Protein Designer"
    terminal._cli_sandbox_label = "Modal Sandbox"
    text = str(terminal._bottom_toolbar())
    assert "plan mode" in text
    assert "#9a7429" in text
    assert "#7fee64" in text
    assert "Protein Designer" in text
    assert "verbose" not in text
    assert "? for commands" not in text
    assert "Ctrl+O" not in text


def test_idle_toolbar_shows_folder_and_context(terminal, monkeypatch):
    monkeypatch.setattr(
        "ui.terminal.bottom_toolbar._short_cwd_label",
        lambda: "~/Projects/sandwalk/cli",
    )
    monkeypatch.setattr(
        "ui.terminal.bottom_toolbar.get_terminal_size",
        lambda: type("T", (), {"columns": 120})(),
    )
    terminal.session.current_model = "gemini-3.1-flash-lite"
    terminal._session_sdk_turn_rows = [{"input_tokens": 19800}]
    with patch(
        "agent.model_catalog.context_window_for_model",
        return_value=1_048_576,
    ):
        text = str(terminal._bottom_toolbar())
    assert "~/Projects/sandwalk/cli" in text
    assert "context:" in text
    assert "1M" in text or "1048.6k" in text or "1.0M" in text


def test_toolbar_context_tokens_does_not_deadlock_on_real_lock(terminal):
    """Regression: never call _has_active_query while holding _run_lock."""
    import threading

    terminal._run_lock = threading.Lock()
    terminal._active_query = None
    terminal._active_input_tokens = 0
    terminal._session_sdk_turn_rows = [{"input_tokens": 1200}]
    terminal._session_sdk_input_tokens = 1200
    # Real Lock + nested acquire would hang forever; this must return promptly.
    assert terminal._toolbar_context_used_tokens() == 1200
    text = str(terminal._bottom_toolbar())
    assert "gemini" in text or "Local Sandbox" in text or "sandwalk" in text


def test_init_toolbar_animation_profile_loads_frames(terminal):
    terminal._toolbar_frames = []
    terminal._toolbar_words = []
    _BottomToolbarMixin._init_toolbar_animation_profile(terminal)
    assert terminal._toolbar_frames
    assert terminal._toolbar_words


def test_init_toolbar_animation_profile_swallows_errors(terminal):
    terminal.session.config.get.side_effect = RuntimeError("boom")
    _BottomToolbarMixin._init_toolbar_animation_profile(terminal)
