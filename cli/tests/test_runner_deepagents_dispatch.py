"""Tests for the AgentRunner deepagents dispatch and result assembly."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from agent.runner import AgentRunner


class _Cfg:
    def __init__(self, data=None):
        self.data = dict(data or {})

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def llm_api_key(self, _provider=None):
        return "k"


def _mk_runner(provider="anthropic", *, headless=True, trace_store=None, extra=None):
    data = {"llm.provider": provider}
    data.update(extra or {})
    session = SimpleNamespace(config=_Cfg(data), console=MagicMock())
    return AgentRunner(
        session=session, trajectory=None, headless=headless, trace_store=trace_store
    )


def _run(coro):
    return asyncio.run(coro)


class TestRunAsyncDispatch:
    def test_anthropic_routes_to_deepagents(self):
        runner = _mk_runner("anthropic")
        sentinel = object()

        async def fake(query, context, progress_callback):
            return sentinel

        runner._run_async_deepagents = fake
        assert _run(runner._run_async("q")) is sentinel

    def test_openai_routes_to_deepagents(self):
        runner = _mk_runner("openai")
        sentinel = object()

        async def fake(query, context, progress_callback):
            return sentinel

        runner._run_async_deepagents = fake
        assert _run(runner._run_async("q")) is sentinel

    def test_unsupported_provider_returns_error(self):
        runner = _mk_runner("cohere")
        result = _run(runner._run_async("q"))
        assert "Unsupported llm.provider 'cohere'" in result.summary


class TestPlanPreview:
    def _model(self, content):
        class _M:
            async def ainvoke(self, _messages):
                return SimpleNamespace(content=content)

        return _M()

    def test_plan_accepted(self):
        runner = _mk_runner()
        with patch("builtins.input", return_value="y"):
            assert _run(runner._deepagents_plan_preview(self._model("plan"), "x")) is True

    def test_plan_accepted_on_empty_enter(self):
        runner = _mk_runner()
        with patch("builtins.input", return_value=""):
            assert _run(runner._deepagents_plan_preview(self._model("plan"), "x")) is True

    def test_plan_rejected(self):
        runner = _mk_runner()
        with patch("builtins.input", return_value="n"):
            assert _run(runner._deepagents_plan_preview(self._model("plan"), "x")) is False

    def test_plan_preview_model_error_defaults_true(self):
        runner = _mk_runner()

        class _Bad:
            async def ainvoke(self, _messages):
                raise RuntimeError("boom")

        assert _run(runner._deepagents_plan_preview(_Bad(), "x")) is True

    def test_plan_preview_renders_mermaid_diagram_when_enabled(self):
        runner = _mk_runner(extra={"ui.mermaid.enabled": True})
        plan_text = "1. Gather target context\n2. Run expression analysis\n3. Synthesize findings"
        with patch("builtins.input", return_value="y"), patch(
            "ui.markdown.print_markdown_with_mermaid"
        ) as mock_mermaid:
            assert _run(runner._deepagents_plan_preview(self._model(plan_text), "x")) is True

        assert mock_mermaid.called
        rendered_text = mock_mermaid.call_args.args[1]
        assert "```mermaid" in rendered_text
        assert "flowchart TD" in rendered_text
        assert "Gather target context" in rendered_text

    def test_plan_preview_skips_mermaid_when_disabled(self):
        runner = _mk_runner(extra={"ui.mermaid.enabled": False})
        with patch("builtins.input", return_value="y"), patch(
            "ui.markdown.print_markdown_with_mermaid"
        ) as mock_mermaid:
            assert _run(runner._deepagents_plan_preview(self._model("1. Only step"), "x")) is True

        mock_mermaid.assert_not_called()

    def test_extract_plan_preview_steps_parses_mixed_formats(self):
        text = "\n".join(
            [
                "# Proposed Plan",
                "1. Collect target context",
                "- Run expression tool",
                "Step 3: Synthesize findings",
                "```",
                "1. this should be ignored in code fence",
                "```",
                "Execution Plan",
                "",
            ]
        )
        steps = AgentRunner._extract_plan_preview_steps(text)
        assert steps == [
            "Collect target context",
            "Run expression tool",
            "Synthesize findings",
        ]

    def test_extract_plan_preview_steps_handles_empty_and_fallback(self):
        assert AgentRunner._extract_plan_preview_steps("") == []
        fallback = AgentRunner._extract_plan_preview_steps("Plan")
        assert fallback == ["Plan"]

    def test_extract_plan_preview_steps_respects_max_steps(self):
        text = "\n".join([f"{i}. Step {i}" for i in range(1, 8)])
        steps = AgentRunner._extract_plan_preview_steps(text, max_steps=3)
        assert steps == ["Step 1", "Step 2", "Step 3"]

    def test_sanitize_mermaid_label_truncates_and_escapes(self):
        raw = 'A [quoted] "label" with backslash \\ and many words'
        label = AgentRunner._sanitize_mermaid_label(raw, max_len=256)
        assert '\\"' in label
        assert "\\\\" in label
        assert "[" not in label and "]" not in label

        long_label = AgentRunner._sanitize_mermaid_label(raw + (" x" * 120), max_len=32)
        assert long_label.endswith("...")

    def test_plan_preview_mermaid_markdown_empty_when_no_steps(self):
        runner = _mk_runner(extra={"ui.mermaid.enabled": True})
        with patch.object(runner, "_extract_plan_preview_steps", return_value=[]):
            assert runner._plan_preview_mermaid_markdown("ignored") == ""

    def test_plan_preview_mermaid_markdown_builds_chain(self):
        runner = _mk_runner(extra={"ui.mermaid.enabled": True})
        md = runner._plan_preview_mermaid_markdown(
            "1. First action\n2) Second action\nStep 3: Third action"
        )
        assert "```mermaid" in md
        assert "flowchart TD" in md
        assert "start --> s1" in md
        assert "s1 --> s2" in md
        assert "s2 --> s3" in md
        assert "s3 --> done" in md
        assert "First action" in md
        assert "Second action" in md
        assert "Third action" in md

    def test_plan_preview_mermaid_render_failure_is_non_fatal(self):
        runner = _mk_runner(extra={"ui.mermaid.enabled": True})
        with patch("builtins.input", return_value="y"), patch(
            "ui.markdown.print_markdown_with_mermaid",
            side_effect=RuntimeError("render boom"),
        ):
            assert _run(runner._deepagents_plan_preview(self._model("1. A\n2. B"), "x")) is True


class TestRunnerInterruptHelpers:
    def test_request_interrupt_returns_false_when_no_active_loop(self):
        runner = _mk_runner()
        assert runner.request_interrupt() is False

    def test_request_interrupt_force_cancels_active_task(self):
        runner = _mk_runner()
        loop = MagicMock()
        loop.is_running.return_value = True
        task = MagicMock()
        task.done.return_value = False
        runner._active_loop = loop
        runner._active_task = task
        assert runner.request_interrupt(force=True) is True
        loop.call_soon_threadsafe.assert_called()

    def test_request_interrupt_force_returns_false_when_task_done(self):
        runner = _mk_runner()
        loop = MagicMock()
        loop.is_running.return_value = True
        task = MagicMock()
        task.done.return_value = True
        runner._active_loop = loop
        runner._active_task = task
        assert runner.request_interrupt(force=True) is False

    def test_request_interrupt_with_client_uses_run_coroutine_threadsafe(self):
        runner = _mk_runner()
        loop = MagicMock()
        loop.is_running.return_value = True
        task = MagicMock()
        task.done.return_value = False
        client = MagicMock()
        runner._active_loop = loop
        runner._active_task = task
        runner._active_client = client

        future = MagicMock()
        with patch("agent.runner.asyncio.run_coroutine_threadsafe", return_value=future) as run_threadsafe:
            assert runner.request_interrupt(force=False) is True

        run_threadsafe.assert_called_once()
        future.result.assert_called_once_with(timeout=2.0)

    def test_request_interrupt_client_failure_falls_back_to_cancel(self):
        runner = _mk_runner()
        loop = MagicMock()
        loop.is_running.return_value = True
        task = MagicMock()
        task.done.return_value = False
        client = MagicMock()
        runner._active_loop = loop
        runner._active_task = task
        runner._active_client = client

        with patch("agent.runner.asyncio.run_coroutine_threadsafe", side_effect=RuntimeError("boom")):
            assert runner.request_interrupt(force=False) is True
        loop.call_soon_threadsafe.assert_called()

    def test_request_interrupt_without_client_and_pending_task_cancels(self):
        runner = _mk_runner()
        loop = MagicMock()
        loop.is_running.return_value = True
        task = MagicMock()
        task.done.return_value = False
        runner._active_loop = loop
        runner._active_task = task
        runner._active_client = None
        assert runner.request_interrupt(force=False) is True
        loop.call_soon_threadsafe.assert_called()

    def test_request_interrupt_without_client_done_task_returns_false(self):
        runner = _mk_runner()
        loop = MagicMock()
        loop.is_running.return_value = True
        task = MagicMock()
        task.done.return_value = True
        runner._active_loop = loop
        runner._active_task = task
        runner._active_client = None
        assert runner.request_interrupt(force=False) is False

    def test_request_interrupt_force_returns_false_when_schedule_fails(self):
        runner = _mk_runner()
        loop = MagicMock()
        loop.is_running.return_value = True
        loop.call_soon_threadsafe.side_effect = RuntimeError("no loop")
        task = MagicMock()
        task.done.return_value = False
        runner._active_loop = loop
        runner._active_task = task
        assert runner.request_interrupt(force=True) is False

    def test_request_interrupt_client_failure_without_pending_task_returns_false(self):
        runner = _mk_runner()
        loop = MagicMock()
        loop.is_running.return_value = True
        task = MagicMock()
        task.done.return_value = True
        client = MagicMock()
        runner._active_loop = loop
        runner._active_task = task
        runner._active_client = client

        with patch("agent.runner.asyncio.run_coroutine_threadsafe", side_effect=RuntimeError("boom")):
            assert runner.request_interrupt(force=False) is False


class TestRunCoroSync:
    def test_run_coro_sync_returns_result_and_cleans_up(self):
        runner = _mk_runner(headless=False)

        async def _ok():
            return "ok"

        with patch.object(runner, "_ensure_sigint_tty_mode", return_value=None), patch.object(
            runner, "_restore_tty_mode"
        ) as restore_tty, patch.object(runner, "_cancel_loop_tasks") as cancel_tasks:
            result = runner._run_coro_sync(_ok())

        assert result == "ok"
        assert runner._active_loop is None
        assert runner._active_task is None
        restore_tty.assert_called_once_with(None)
        cancel_tasks.assert_called()

    def test_run_coro_sync_keyboard_interrupt_cancels_and_raises(self):
        runner = _mk_runner(headless=True)
        sentinel_coro = object()

        fake_task = MagicMock()
        fake_task.done.return_value = False

        fake_loop = MagicMock()
        fake_loop.create_task.return_value = fake_task
        fake_loop.run_until_complete.side_effect = KeyboardInterrupt()

        def _no_interrupt():
            return False

        with patch("agent.runner.asyncio.new_event_loop", return_value=fake_loop), patch.object(
            runner, "_ensure_sigint_tty_mode", return_value=None
        ), patch.object(runner, "_restore_tty_mode"), patch.object(
            runner, "_cancel_loop_tasks"
        ) as cancel_tasks, patch.object(
            runner, "_interrupt_active_query", side_effect=_no_interrupt, create=True
        ), patch("agent.runner.signal.signal"), patch(
            "agent.runner.signal.getsignal", return_value=0
        ):
            with patch("agent.runner.threading.current_thread", return_value=threading.main_thread()), patch(
                "agent.runner.threading.main_thread", return_value=threading.main_thread()
            ):
                with patch("agent.runner.asyncio.set_event_loop"):
                    with pytest.raises(KeyboardInterrupt):
                        runner._run_coro_sync(sentinel_coro)
        cancel_tasks.assert_called()

    def test_run_coro_sync_starts_stdin_watcher_and_handles_ctrl_c_byte(self):
        runner = _mk_runner(headless=False)

        async def _slow_ok():
            await asyncio.sleep(0.03)
            return "ok"

        # One ready-read cycle with Ctrl+C byte, then no readiness.
        select_calls = [([123], [], []), ([], [], [])]

        def _fake_select(*_args, **_kwargs):
            if select_calls:
                return select_calls.pop(0)
            return ([], [], [])

        with patch.object(runner, "_ensure_sigint_tty_mode", return_value=None), patch.object(
            runner, "_restore_tty_mode"
        ), patch.object(runner, "_cancel_loop_tasks"), patch(
            "agent.runner.sys.stdin.fileno", return_value=123
        ), patch("agent.runner.select.select", side_effect=_fake_select), patch(
            "agent.runner.os.read", return_value=b"\x03"
        ), patch("agent.runner.os.kill") as mock_kill, patch(
            "agent.runner.signal.signal"
        ), patch(
            "agent.runner.signal.getsignal", return_value=0
        ), patch(
            "agent.runner.asyncio.set_event_loop"
        ):
            with patch("agent.runner.threading.current_thread", return_value=threading.main_thread()), patch(
                "agent.runner.threading.main_thread", return_value=threading.main_thread()
            ):
                assert runner._run_coro_sync(_slow_ok()) == "ok"

        assert mock_kill.called

    def test_run_coro_sync_stdin_watcher_handles_select_error(self):
        runner = _mk_runner(headless=False)

        async def _slow_ok():
            await asyncio.sleep(0.02)
            return "ok"

        with patch.object(runner, "_ensure_sigint_tty_mode", return_value=None), patch.object(
            runner, "_restore_tty_mode"
        ), patch.object(runner, "_cancel_loop_tasks"), patch(
            "agent.runner.sys.stdin.fileno", return_value=123
        ), patch("agent.runner.select.select", side_effect=RuntimeError("select failed")), patch(
            "agent.runner.signal.signal"
        ), patch(
            "agent.runner.signal.getsignal", return_value=0
        ), patch(
            "agent.runner.asyncio.set_event_loop"
        ):
            with patch("agent.runner.threading.current_thread", return_value=threading.main_thread()), patch(
                "agent.runner.threading.main_thread", return_value=threading.main_thread()
            ):
                assert runner._run_coro_sync(_slow_ok()) == "ok"

    def test_run_coro_sync_stdin_watcher_handles_read_error(self):
        runner = _mk_runner(headless=False)

        async def _slow_ok():
            await asyncio.sleep(0.02)
            return "ok"

        with patch.object(runner, "_ensure_sigint_tty_mode", return_value=None), patch.object(
            runner, "_restore_tty_mode"
        ), patch.object(runner, "_cancel_loop_tasks"), patch(
            "agent.runner.sys.stdin.fileno", return_value=123
        ), patch("agent.runner.select.select", return_value=([123], [], [])), patch(
            "agent.runner.os.read", side_effect=RuntimeError("read failed")
        ), patch(
            "agent.runner.signal.signal"
        ), patch(
            "agent.runner.signal.getsignal", return_value=0
        ), patch(
            "agent.runner.asyncio.set_event_loop"
        ):
            with patch("agent.runner.threading.current_thread", return_value=threading.main_thread()), patch(
                "agent.runner.threading.main_thread", return_value=threading.main_thread()
            ):
                assert runner._run_coro_sync(_slow_ok()) == "ok"


class TestRunAsyncDeepagentsHappyPath:
    def test_assembles_execution_result(self):
        runner = _mk_runner(
            "anthropic",
            extra={"llm.model": "claude-sonnet-4-5-20250929"},
        )

        fake_sandbox = SimpleNamespace(
            get_variable=lambda name: {"answer": "the answer"} if name == "result" else None
        )

        process_result = {
            "full_text": ["This is the synthesized answer."],
            "tool_calls": [{"name": "target.neo", "input": {"gene": "TP53"}}],
            "token_usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_creation_input_tokens": 5,
                "cache_read_input_tokens": 10,
            },
            "model_call_count": 2,
        }

        async def fake_process_events(events, **kwargs):
            return process_result

        fake_agent = SimpleNamespace(astream_events=lambda *a, **k: MagicMock())

        with patch("agent.deepagents_runtime.build_chat_model", return_value=MagicMock()), \
            patch(
                "agent.deepagents_runtime.create_ct_langchain_tools",
                return_value=([MagicMock(name="t")], fake_sandbox, [], {}),
            ), \
            patch("agent.deepagents_runtime.skill_source_dirs", return_value=[]), \
            patch("agent.deepagents_runtime.process_events", side_effect=fake_process_events), \
            patch("agent.system_prompt.build_system_prompt", return_value="SYS"), \
            patch("ui.traces.TraceRenderer", return_value=MagicMock()), \
            patch("deepagents.create_deep_agent", return_value=fake_agent), \
            patch("deepagents.backends.FilesystemBackend", return_value=MagicMock()):
            result = _run(runner._run_async_deepagents("find TP53 degraders"))

        assert result.summary == "This is the synthesized answer."
        assert result.metadata["runtime"] == "deepagents"
        assert result.metadata["sdk_input_tokens"] == 100
        assert result.metadata["sdk_output_tokens"] == 20
        assert result.metadata["sdk_cache_read_input_tokens"] == 10
        assert result.raw_results["answer"] == "the answer"
        assert len(result.raw_results["tool_calls"]) == 1

    def test_build_chat_model_value_error_returns_error_result(self):
        runner = _mk_runner("anthropic")
        with patch(
            "agent.deepagents_runtime.build_chat_model",
            side_effect=ValueError("bad provider config"),
        ):
            result = _run(runner._run_async_deepagents("q"))
        assert "bad provider config" in result.summary
