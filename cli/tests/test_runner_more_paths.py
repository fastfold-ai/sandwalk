"""Additional branch-heavy unit tests for AgentRunner helpers."""

from __future__ import annotations

import asyncio
import importlib
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.runner import AgentRunner


def _mk_runner(headless: bool = True):
    cfg = SimpleNamespace(
        get=lambda key, default=None: default,
        llm_api_key=lambda provider: None,
    )
    console = MagicMock()
    console.width = 50
    session = SimpleNamespace(config=cfg, console=console)
    return AgentRunner(session=session, trajectory=None, headless=headless), session


class _FakeFuture:
    def result(self, timeout=None):
        return None


class _AssistantMessage:
    def __init__(self, content):
        self.content = content


class _TextBlock:
    def __init__(self, text):
        self.text = text


class _FakeClient:
    def __init__(self, options, text):
        self.options = options
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def query(self, prompt):
        return None

    async def receive_response(self):
        yield _AssistantMessage([_TextBlock(self._text)])


class TestWatcherStartAndInterrupt:
    def test_request_interrupt_client_success_path(self):
        runner, _ = _mk_runner(headless=True)
        loop = MagicMock()
        loop.is_running.return_value = True
        task = MagicMock()
        task.done.return_value = False
        runner._active_loop = loop
        runner._active_task = task
        runner._active_client = MagicMock()
        runner._active_client.interrupt.return_value = "coro"

        with patch("agent.runner.asyncio.run_coroutine_threadsafe", return_value=_FakeFuture()) as call_mock:
            assert runner.request_interrupt(force=False) is True
        call_mock.assert_called_once_with("coro", loop)


class TestProbePaths:
    def test_probe_local_task_outputs_marks_failed_when_exit_code_nonzero(self, tmp_path):
        runner, _ = _mk_runner(headless=False)
        output = tmp_path / "task_fail.output"
        output.write_text("hello\nexit_code: 2\n", encoding="utf-8")
        runner._bg_watch_state = {
            "sess-1": {
                "pending_task_ids": ["task_fail"],
                "completed_task_ids": [],
                "output_files": {"task_fail": str(output)},
            }
        }
        remaining = {"task_fail"}
        trace_renderer = MagicMock()
        with patch.object(runner, "_notify_terminal_task_completion") as notify_mock:
            runner._probe_local_task_outputs("sess-1", remaining, trace_renderer)
        assert "task_fail" not in remaining
        trace_renderer.render_task_notification.assert_called_once()
        notify_mock.assert_called_once()
        assert notify_mock.call_args.args[1] == "failed"

class TestNotificationAndUsageFormatting:
    def test_notify_terminal_task_completion_ignores_non_terminal_status(self):
        runner, _ = _mk_runner(headless=False)
        with patch("agent.runner._is_warp_terminal_env", return_value=True), patch(
            "agent.runner.sys.stdout.write"
        ) as write_mock:
            runner._notify_terminal_task_completion("task-1", "running", "still going", "")
        write_mock.assert_not_called()

    def test_print_usage_long_duration_wraps_line(self):
        runner, session = _mk_runner(headless=True)
        session.console.width = 28
        with patch.object(runner, "_random_usage_word", return_value="Tested"):
            runner._print_usage(
                result_msg=None,
                duration=65.0,
                input_tokens=123456789012345,
                output_tokens=987654321,
            )
        rendered = " ".join(str(c) for c in session.console.print.call_args_list)
        assert "Tested for 1m 5s" in rendered
        assert "·" in rendered

    def test_make_error_result_contains_error_and_query(self):
        result = AgentRunner._make_error_result("check target", "boom", 3.5)
        assert result.plan.query == "check target"
        assert result.summary == "Agent SDK error: boom"
        assert result.raw_results["error"] == "boom"
        assert result.duration_s == 3.5
