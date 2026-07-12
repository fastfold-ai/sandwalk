"""Additional focused tests for ui.terminal and agent.runner helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent import runner
from ui.terminal import MentionCompleter, MergedCompleter, SlashCompleter, _build_key_bindings


class _FakeBuffer:
    def __init__(self, text: str = ""):
        self.text = text
        self.inserted = []
        self.started_completion = False
        self.reset_called = False
        self.cancel_called = False
        self.validated = False
        self.complete_state = None
        self.applied_completion = None

    def insert_text(self, text: str):
        self.inserted.append(text)

    def start_completion(self):
        self.started_completion = True

    def reset(self):
        self.reset_called = True

    def cancel_completion(self):
        self.cancel_called = True

    def validate_and_handle(self):
        self.validated = True

    def go_to_completion(self, idx: int):
        if self.complete_state is not None:
            self.complete_state.complete_index = idx
            self.complete_state.current_completion = self.complete_state.completions[idx]

    def apply_completion(self, completion):
        self.applied_completion = completion


def _build_terminal_for_bindings(active_query: bool = False):
    mention = MentionCompleter(
        [
            ("target.druggability", "target", "desc", "tool"),
            ("depmap", "omics", "desc", "dataset"),
        ]
    )
    return SimpleNamespace(
        _suggestion_idx=0,
        _suggestions=["suggested prompt"],
        _last_interrupt=0.0,
        _show_interrupt_hint=False,
        _show_exit_hint=False,
        _verbose_hint=None,
        _has_active_query=lambda: active_query,
        _request_interrupt=MagicMock(),
        session=SimpleNamespace(verbose=False),
        _merged_completer=MergedCompleter(SlashCompleter(), mention),
    )


def _handler(kb, name: str):
    return next(b.handler for b in kb.bindings if b.handler.__name__ == name)


class TestTerminalKeyBindings:
    def test_tab_accepts_suggestion_on_empty_input(self):
        terminal = _build_terminal_for_bindings()
        kb = _build_key_bindings(terminal)
        buf = _FakeBuffer(text="")
        event = SimpleNamespace(app=SimpleNamespace(current_buffer=buf))

        _handler(kb, "_accept_suggestion")(event)

        assert buf.inserted == ["suggested prompt"]

    def test_tab_starts_completion_on_non_empty_input(self):
        terminal = _build_terminal_for_bindings()
        kb = _build_key_bindings(terminal)
        buf = _FakeBuffer(text="hello")
        event = SimpleNamespace(app=SimpleNamespace(current_buffer=buf))

        _handler(kb, "_accept_suggestion")(event)

        assert buf.started_completion is True

    def test_ctrl_c_active_query_requests_interrupt(self):
        terminal = _build_terminal_for_bindings(active_query=True)
        kb = _build_key_bindings(terminal)
        buf = _FakeBuffer(text="run query")
        app = SimpleNamespace(current_buffer=buf, invalidate=MagicMock(), is_running=True)
        event = SimpleNamespace(app=app)

        class _ImmediateThread:
            def __init__(self, target=None, daemon=None):
                self._target = target

            def start(self):
                if self._target:
                    self._target()

        with patch("ui.terminal.threading.Thread", _ImmediateThread), patch(
            "ui.terminal.time.sleep", lambda _s: None
        ), patch("ui.terminal.time.time", return_value=100.0):
            _handler(kb, "_handle_ctrl_c")(event)

        terminal._request_interrupt.assert_called_once_with(force=False)
        assert buf.reset_called is True

    def test_ctrl_c_double_tap_exits(self):
        terminal = _build_terminal_for_bindings(active_query=False)
        kb = _build_key_bindings(terminal)
        buf = _FakeBuffer(text="")
        app = SimpleNamespace(
            current_buffer=buf,
            invalidate=MagicMock(),
            exit=MagicMock(),
            is_running=True,
        )
        event = SimpleNamespace(app=app)

        class _ImmediateThread:
            def __init__(self, target=None, daemon=None):
                self._target = target

            def start(self):
                if self._target:
                    self._target()

        with patch("ui.terminal.threading.Thread", _ImmediateThread), patch(
            "ui.terminal.time.sleep", lambda _s: None
        ), patch("ui.terminal.time.time", side_effect=[1.0, 1.3]):
            _handler(kb, "_handle_ctrl_c")(event)
            _handler(kb, "_handle_ctrl_c")(event)

        app.exit.assert_called_once_with(result="__EXIT__")

    def test_toggle_verbose_and_mention_tabs(self):
        terminal = _build_terminal_for_bindings(active_query=False)
        kb = _build_key_bindings(terminal)
        buf = _FakeBuffer(text="@")
        app = SimpleNamespace(current_buffer=buf, invalidate=MagicMock(), is_running=True)
        event = SimpleNamespace(app=app)

        class _ImmediateThread:
            def __init__(self, target=None, daemon=None):
                self._target = target

            def start(self):
                if self._target:
                    self._target()

        with patch("ui.terminal.threading.Thread", _ImmediateThread), patch(
            "ui.terminal.time.sleep", lambda _s: None
        ):
            _handler(kb, "_toggle_verbose")(event)

        assert terminal.session.verbose is True
        _handler(kb, "_mention_tab_right")(event)
        assert terminal._merged_completer.mention_completer._active_tab == 1
        _handler(kb, "_mention_tab_left")(event)
        assert terminal._merged_completer.mention_completer._active_tab == 0

    def test_enter_accepts_slash_completion_and_submits(self):
        terminal = _build_terminal_for_bindings()
        kb = _build_key_bindings(terminal)
        buf = _FakeBuffer(text="/he")
        buf.complete_state = SimpleNamespace(
            completions=["/help", "/hello"],
            complete_index=None,
            current_completion=None,
        )
        event = SimpleNamespace(app=SimpleNamespace(current_buffer=buf))

        _handler(kb, "_accept_first_completion")(event)

        assert buf.applied_completion == "/help"
        assert buf.validated is True

    def test_enter_non_slash_submits_without_completion(self):
        terminal = _build_terminal_for_bindings()
        kb = _build_key_bindings(terminal)
        buf = _FakeBuffer(text="hello")
        buf.complete_state = SimpleNamespace(
            completions=["ignored"],
            complete_index=0,
            current_completion="ignored",
        )
        event = SimpleNamespace(app=SimpleNamespace(current_buffer=buf))

        _handler(kb, "_accept_first_completion")(event)

        assert buf.cancel_called is True
        assert buf.validated is True

    def test_newline_bindings_insert_newline_text(self):
        terminal = _build_terminal_for_bindings()
        kb = _build_key_bindings(terminal)
        buf = _FakeBuffer(text="line1")
        event = SimpleNamespace(app=SimpleNamespace(current_buffer=buf))

        _handler(kb, "_insert_newline")(event)
        _handler(kb, "_insert_newline_alt")(event)

        assert buf.inserted == ["\n", "\n"]

    def test_mention_tab_handlers_noop_without_completer(self):
        terminal = _build_terminal_for_bindings()
        terminal._merged_completer = None
        kb = _build_key_bindings(terminal)
        buf = _FakeBuffer(text="@x")
        event = SimpleNamespace(app=SimpleNamespace(current_buffer=buf))

        _handler(kb, "_mention_tab_right")(event)
        _handler(kb, "_mention_tab_left")(event)

        assert buf.cancel_called is False


class TestRunnerAdditionalHelpers:
    def test_default_local_task_output_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr("agent.runner.os.getuid", lambda: 501)
        monkeypatch.chdir(tmp_path)
        path = runner._default_local_task_output_path("task_123")
        assert "task_123.output" in path
        assert "/private/tmp/claude-501/" in path

    def test_discover_local_task_output_short_circuits(self):
        assert runner._discover_local_task_output_file("") == ""

    def test_parse_task_probe_json_variants(self):
        fenced = "```json\n{\"t1\": \"completed\", \"t2\": \"BOGUS\"}\n```"
        out = runner._parse_task_probe_json(fenced)
        assert out["t1"] == "completed"
        assert out["t2"] == "unknown"
        assert runner._parse_task_probe_json("not json") == {}

    @pytest.mark.parametrize(
        "env,expected",
        [
            ({"TERM_PROGRAM": "WarpTerminal"}, True),
            ({"WARP_IS_LOCAL_SHELL_SESSION": "1"}, True),
            ({"WARP_SESSION_ID": "abc"}, True),
            ({}, False),
        ],
    )
    def test_is_warp_terminal_env(self, env, expected):
        assert runner._is_warp_terminal_env(env) is expected

    def test_sanitize_notification_text(self):
        text = "line1;\nline2\r\n" + ("x" * 300)
        out = runner._sanitize_notification_text(text, max_len=40)
        assert ";" not in out
        assert "\n" not in out
        assert len(out) <= 40
