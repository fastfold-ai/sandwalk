"""Additional coverage-focused tests for agent.runner helpers."""

from __future__ import annotations

import asyncio
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import agent.runner as runner_mod
from agent.runner import AgentRunner, _classify_llm_error


def _mk_runner(headless: bool = True):
    cfg = SimpleNamespace(get=lambda key, default=None: default)
    console = MagicMock()
    console.width = 80
    session = SimpleNamespace(config=cfg, console=console)
    return AgentRunner(session=session, trajectory=None, headless=headless)


class _Err(Exception):
    def __init__(self, message: str, *, status_code=None, code=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class _OpenAIStyleErr(Exception):
    pass


_OpenAIStyleErr.__module__ = "openai"


class TestClassifyLlmError:
    def test_auth_by_status(self):
        title, body = _classify_llm_error(_Err("nope", status_code=401))
        assert title == "Authentication failed"
        assert "401" in body

    def test_auth_by_message(self):
        title, _ = _classify_llm_error(_Err("authentication_error: invalid x-api-key"))
        assert title == "Authentication failed"

    def test_rate_limit(self):
        title, body = _classify_llm_error(_Err("rate limit reached", status_code=429))
        assert title == "Rate limited"
        assert "429" in body

    def test_connection(self):
        title, body = _classify_llm_error(ConnectionError("connection error"))
        assert title == "Connection problem"
        assert "network" in body.lower()

    def test_connection_refused_text(self):
        title, body = _classify_llm_error(_Err("dial tcp: connection refused"))
        assert title == "Connection problem"
        assert "could not reach" in body.lower()

    def test_model_or_endpoint_not_found(self):
        title, body = _classify_llm_error(
            _Err("model 'gpt-5-nano' not found", status_code=404)
        )
        assert title == "Model or endpoint not found"
        assert "llm.model" in body

    def test_openai_style_error_falls_back_to_provider_message(self):
        title, body = _classify_llm_error(_OpenAIStyleErr("something odd happened"))
        assert title == "Model provider request failed"
        assert "openai-compatible" in body.lower()

    def test_unrecognized(self):
        assert _classify_llm_error(_Err("completely unknown")) is None


class TestTaskOutputDiscovery:
    def test_default_output_path_returns_empty_when_uid_unavailable(self, monkeypatch):
        def _boom():
            raise RuntimeError("no uid")

        monkeypatch.setattr(runner_mod.os, "getuid", _boom)
        assert runner_mod._default_local_task_output_path("task_1") == ""

    def test_discover_uses_direct_path(self, monkeypatch, tmp_path):
        p = tmp_path / "tasks" / "task_abc.output"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("ok", encoding="utf-8")
        monkeypatch.setattr(runner_mod, "_default_local_task_output_path", lambda _task_id: str(p))
        found = runner_mod._discover_local_task_output_file("task_abc")
        assert found == str(p)

    def test_discover_returns_empty_when_uid_lookup_fails(self, monkeypatch):
        monkeypatch.setattr(runner_mod, "_default_local_task_output_path", lambda _task_id: "")

        def _boom():
            raise RuntimeError("uid fail")

        monkeypatch.setattr(runner_mod.os, "getuid", _boom)
        assert runner_mod._discover_local_task_output_file("task_xyz") == ""

    def test_discover_finds_output_via_tmp_glob(self, monkeypatch):
        uid = 9191
        task_id = "task_glob_123"
        root = runner_mod.Path(f"/tmp/claude-{uid}")
        out = root / "demo" / "tasks" / f"{task_id}.output"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("done", encoding="utf-8")
        monkeypatch.setattr(runner_mod, "_default_local_task_output_path", lambda _task_id: "")
        monkeypatch.setattr(runner_mod.os, "getuid", lambda: uid)
        try:
            found = runner_mod._discover_local_task_output_file(task_id)
            assert found.endswith(f"/tasks/{task_id}.output")
            assert f"/claude-{uid}/" in found
        finally:
            # Best-effort cleanup to avoid /tmp buildup.
            try:
                out.unlink(missing_ok=True)
                out.parent.rmdir()
                (root / "demo").rmdir()
                root.rmdir()
            except Exception:
                pass

    def test_parse_task_probe_json_non_dict_payload(self):
        assert runner_mod._parse_task_probe_json("[1,2,3]") == {}


class TestInterruptTtyHelpers:
    def test_ensure_sigint_tty_mode_non_posix(self, monkeypatch):
        r = _mk_runner()
        monkeypatch.setattr(runner_mod.os, "name", "nt")
        assert r._ensure_sigint_tty_mode() is None

    def test_ensure_sigint_tty_mode_handles_stdin_errors(self, monkeypatch):
        r = _mk_runner()
        monkeypatch.setattr(runner_mod.os, "name", "posix")
        fake_stdin = SimpleNamespace(fileno=lambda: (_ for _ in ()).throw(RuntimeError("bad fd")))
        monkeypatch.setattr(runner_mod.sys, "stdin", fake_stdin)
        assert r._ensure_sigint_tty_mode() is None

    def test_ensure_sigint_tty_mode_updates_int_cc(self, monkeypatch):
        r = _mk_runner()
        monkeypatch.setattr(runner_mod.os, "name", "posix")

        calls: list[tuple] = []
        fake_termios = types.SimpleNamespace(
            ISIG=1,
            ICANON=2,
            VINTR=0,
            VMIN=1,
            VTIME=2,
            TCSANOW=0,
            tcgetattr=lambda _fd: [0, 0, 0, 0, 0, 0, [0, 0, 1]],
            tcsetattr=lambda fd, when, attrs: calls.append((fd, when, attrs)),
        )
        monkeypatch.setitem(runner_mod.sys.modules, "termios", fake_termios)
        monkeypatch.setattr(runner_mod.sys, "stdin", SimpleNamespace(fileno=lambda: 9))
        state = r._ensure_sigint_tty_mode()
        assert state is not None
        assert calls, "tcsetattr should be called when attrs change"

    def test_ensure_sigint_tty_mode_updates_bytes_cc(self, monkeypatch):
        r = _mk_runner()
        monkeypatch.setattr(runner_mod.os, "name", "posix")

        calls: list[tuple] = []
        fake_termios = types.SimpleNamespace(
            ISIG=1,
            ICANON=2,
            VINTR=0,
            VMIN=1,
            VTIME=2,
            TCSANOW=0,
            tcgetattr=lambda _fd: [0, 0, 0, 0, 0, 0, [b"\x00", b"\x00", b"\x01"]],
            tcsetattr=lambda fd, when, attrs: calls.append((fd, when, attrs)),
        )
        monkeypatch.setitem(runner_mod.sys.modules, "termios", fake_termios)
        monkeypatch.setattr(runner_mod.sys, "stdin", SimpleNamespace(fileno=lambda: 10))
        state = r._ensure_sigint_tty_mode()
        assert state is not None
        assert calls, "tcsetattr should be called when byte attrs change"

    def test_restore_tty_mode(self, monkeypatch):
        r = _mk_runner()
        calls: list[tuple] = []
        fake_termios = types.SimpleNamespace(
            TCSANOW=0,
            tcsetattr=lambda fd, when, attrs: calls.append((fd, when, attrs)),
        )
        monkeypatch.setitem(runner_mod.sys.modules, "termios", fake_termios)
        r._restore_tty_mode((7, ["attrs"]))
        assert calls == [(7, 0, ["attrs"])]
        r._restore_tty_mode(None)  # no-op branch


class TestCancelLoopTasks:
    def test_cancel_loop_tasks_with_pending_task(self):
        r = _mk_runner()
        loop = asyncio.new_event_loop()
        try:
            pending = loop.create_task(asyncio.sleep(60))
            r._cancel_loop_tasks(loop)
            assert pending.cancelled() or pending.done()
        finally:
            loop.close()


class TestTaskNotificationEdge:
    def test_notify_returns_when_body_is_sanitized_empty(self, monkeypatch):
        r = _mk_runner(headless=False)
        monkeypatch.setattr(runner_mod, "_is_warp_terminal_env", lambda env=None: True)
        # First call sanitizes title, second call sanitizes body.
        values = iter(["title", ""])
        monkeypatch.setattr(runner_mod, "_sanitize_notification_text", lambda *_a, **_k: next(values))
        write = MagicMock()
        flush = MagicMock()
        monkeypatch.setattr(runner_mod.sys, "stdout", SimpleNamespace(write=write, flush=flush))
        r._notify_terminal_task_completion("task1", "completed")
        write.assert_not_called()
        flush.assert_not_called()
