"""Additional coverage for AgentRunner background/task helper methods."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.runner import AgentRunner


def _mk_runner(headless: bool = True):
    cfg = SimpleNamespace(
        get=lambda key, default=None: default,
        llm_api_key=lambda provider: None,
    )
    console = MagicMock()
    console.width = 100
    session = SimpleNamespace(config=cfg, console=console)
    return AgentRunner(session=session, trajectory=None, headless=headless), session


class TestRunnerNotifications:
    def test_notify_terminal_task_completion_headless_noop(self):
        runner, _ = _mk_runner(headless=True)
        with patch("agent.runner.sys.stdout.write") as mock_write:
            runner._notify_terminal_task_completion("task_1", "completed", "ok", "/tmp/out")
        mock_write.assert_not_called()

    def test_notify_terminal_task_completion_emits_warp_osc(self):
        runner, _ = _mk_runner(headless=False)
        with patch("agent.runner._is_warp_terminal_env", return_value=True), patch(
            "agent.runner.sys.stdout.write"
        ) as mock_write, patch("agent.runner.sys.stdout.flush"):
            runner._notify_terminal_task_completion("task_1", "completed", "ok", "/tmp/out")
        payload = mock_write.call_args.args[0]
        assert "777;notify;" in payload
        assert "task_1" in payload


class TestRunnerInterrupts:
    def test_request_interrupt_force_false_without_loop(self):
        runner, _ = _mk_runner(headless=True)
        assert runner.request_interrupt(force=False) is False

    def test_request_interrupt_force_cancels_task(self):
        runner, _ = _mk_runner(headless=True)
        task = MagicMock()
        task.done.return_value = False
        loop = MagicMock()
        loop.is_running.return_value = True
        runner._active_loop = loop
        runner._active_task = task
        assert runner.request_interrupt(force=True) is True
        loop.call_soon_threadsafe.assert_called_once()

    def test_request_interrupt_client_interrupt_fallback_cancel(self):
        runner, _ = _mk_runner(headless=True)
        task = MagicMock()
        task.done.return_value = False
        loop = MagicMock()
        loop.is_running.return_value = True
        runner._active_loop = loop
        runner._active_task = task
        runner._active_client = MagicMock()
        with patch("agent.runner.asyncio.run_coroutine_threadsafe", side_effect=RuntimeError("nope")):
            assert runner.request_interrupt(force=False) is True


class TestRunnerBackgroundState:
    def test_get_background_watch_status_sorted(self):
        runner, _ = _mk_runner(headless=True)
        runner._bg_watch_state = {
            "a": {"last_update_at": 1.0, "status": "running"},
            "b": {"last_update_at": 2.0, "status": "completed"},
        }
        rows = runner.get_background_watch_status()
        assert rows[0]["session_id"] == "b"


class TestRunnerOutputProbe:
    def test_probe_local_task_outputs_marks_completed(self, tmp_path):
        runner, _ = _mk_runner(headless=False)
        output = tmp_path / "task_a.output"
        output.write_text("...\nexit_code: 0\n", encoding="utf-8")
        runner._bg_watch_state = {
            "sess-1": {
                "pending_task_ids": ["task_a"],
                "completed_task_ids": [],
                "output_files": {"task_a": str(output)},
            }
        }
        remaining = {"task_a"}
        trace = MagicMock()
        runner._probe_local_task_outputs("sess-1", remaining, trace)
        assert "task_a" not in remaining
        assert "task_a" in runner._bg_watch_state["sess-1"]["completed_task_ids"]
        trace.render_task_notification.assert_called_once()

    def test_refresh_background_watch_status_local_only(self):
        runner, _ = _mk_runner(headless=True)
        runner._bg_watch_state = {
            "sess-1": {
                "pending_task_ids": ["task_a"],
                "model": "claude-sonnet-4-5-20250929",
                "last_probe_at": 0,
            }
        }
        with patch.object(runner, "_probe_local_task_outputs") as mock_probe:
            runner.refresh_background_watch_status()
        mock_probe.assert_called_once()


class TestRunnerPlanAndUsage:
    def test_print_usage_and_error_result(self):
        runner, session = _mk_runner(headless=True)
        usage = SimpleNamespace(input_tokens=1234, output_tokens=56)
        result_msg = SimpleNamespace(usage=usage)
        runner._print_usage(result_msg=result_msg, duration=3.2)
        session.console.print.assert_called()

        err = runner._make_error_result("query", "boom", 1.5)
        assert "boom" in err.summary
        assert err.duration_s == 1.5
