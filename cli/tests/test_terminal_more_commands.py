"""Additional unit tests for InteractiveTerminal command/helper branches."""

from __future__ import annotations

import io
import json
import tempfile
import urllib.error
from collections import deque
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from rich.panel import Panel
from rich.table import Table

from agent.config import Config
from ui.terminal import InteractiveTerminal


def _mk_terminal() -> InteractiveTerminal:
    with patch("ui.terminal.InteractiveTerminal.__init__", return_value=None):
        term = InteractiveTerminal.__new__(InteractiveTerminal)
    term.console = MagicMock()
    term.console.width = 100
    term.session = MagicMock()
    term.session.current_model = "claude-sonnet-4-5-20250929"
    term.session.config = MagicMock()
    term.session.config.get.side_effect = lambda key, default=None: default
    term._plain_prompt_session = MagicMock()
    term._prompt_session = MagicMock()
    term._secret_prompt_session = MagicMock()
    term._last_response = None
    term._run_lock = MagicMock()
    term._run_lock.__enter__ = MagicMock(return_value=None)
    term._run_lock.__exit__ = MagicMock(return_value=False)
    term._session_sdk_calls = 0
    term._session_sdk_input_tokens = 0
    term._session_sdk_output_tokens = 0
    term._session_sdk_cache_read_tokens = 0
    term._session_sdk_cache_creation_tokens = 0
    term._session_sdk_cost_usd = 0.0
    term._session_sdk_total_cost_usd = 0.0
    term._session_sdk_extra_server_tool_cost_usd = 0.0
    term._session_sdk_models = set()
    term._session_sdk_turn_rows = []
    term._worker_thread = None
    term._queued_queries = deque()
    term._live_refresh_thread = None
    term._active_query = None
    term._active_query_started_at = 0.0
    term._active_activity = ""
    term._active_activity_updated_at = 0.0
    term._active_input_tokens = 0
    term._active_output_tokens = 0
    term._active_streamed_chars = 0
    term._prompt_session.app = SimpleNamespace(is_running=False, invalidate=MagicMock())
    return term


class _UrlOpenResponse:
    def __init__(self, payload: object):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestSettingsAndCommands:
    def test_change_settings_spinner_and_profile_and_html(self):
        term = _mk_terminal()
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: {
            "ui.spinner": "dna_helix",
            "agent.profile": "research",
            "output.auto_publish_html_interactive": True,
        }.get(key, default)

        with patch("agent.config.Config.load", return_value=cfg), patch(
            "ui.status.SPINNERS", {"dna_helix": object(), "dots": object()}
        ), patch("sys.stdout.flush"):
            term._getch = MagicMock(side_effect=["1", "2", "2", "2", "3", "n", "0"])
            term._change_settings()

        cfg.set.assert_any_call("ui.spinner", "dots")
        profile_sets = [
            c for c in cfg.set.call_args_list if c.args and c.args[0] == "agent.profile"
        ]
        assert profile_sets
        assert profile_sets[0].args[1] != "research"
        cfg.set.assert_any_call("output.auto_publish_html_interactive", False)
        assert cfg.save.call_count == 3

    def test_change_settings_invalid_top_level_choice(self):
        term = _mk_terminal()
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: default
        with patch("agent.config.Config.load", return_value=cfg), patch("sys.stdout.flush"):
            term._getch = MagicMock(side_effect=["x", "0"])
            term._change_settings()
        assert any("Invalid choice" in str(call) for call in term.console.print.call_args_list)

    def test_toggle_plan_mode_flips_config(self):
        term = _mk_terminal()
        term.session.config.get.return_value = False
        term._toggle_plan_mode()
        term.session.config.set.assert_called_once_with("agent.plan_preview", True)

    def test_show_usage_fallback_when_no_calls(self):
        term = _mk_terminal()
        llm = MagicMock()
        llm.usage.calls = 0
        term.session.get_llm.return_value = llm
        term._show_usage()
        assert any("No LLM calls made yet" in str(c) for c in term.console.print.call_args_list)


class TestOpenAICompatibleSetupAndFetch:
    def test_switch_model_lists_configured_profile_models_top_level(self):
        term = _mk_terminal()
        cfg = Config(data={"llm.provider": "openai", "llm.model": "gpt-5.5"})
        cfg.upsert_openai_profile(
            profile_id="omlx_local",
            label="oMLX Local",
            backend="omlx",
            base_url="http://localhost:8000/v1",
            api_key="sk-omlx-test",
            default_model="omlx-default",
            set_active=True,
        )
        cfg.upsert_openai_profile(
            profile_id="unsloth_local",
            label="Unsloth Local",
            backend="unsloth",
            base_url="http://localhost:8888/v1",
            api_key="sk-unsloth-test",
            default_model="unsloth-default",
        )
        term.session.config = cfg
        term.session.config.save = MagicMock()
        term.session.current_model = "gpt-5.5"
        term._prompt_session.prompt.return_value = "12"  # first profile model option after static entries
        term._fetch_compatible_models = MagicMock(
            side_effect=[["omlx-a", "omlx-b"], ["unsloth-a"]]
        )

        term._switch_model()

        term.session.set_model.assert_called_once_with("omlx-a", provider="openai")
        assert cfg.active_openai_profile_id() == "omlx_local"
        rendered = "\n".join(
            str(call.args[0]) for call in term.console.print.call_args_list if call.args
        )
        assert "[0] OpenAI-compatible profiles" not in rendered
        assert "(custom)" not in rendered
        assert "oMLX Local: omlx-a" in rendered
        assert "Unsloth Local: unsloth-a" in rendered
        assert "(oMLX)" in rendered
        assert "(openai:omlx_local)" not in rendered

    def test_switch_model_warns_when_configured_compatible_profile_has_no_models(self):
        term = _mk_terminal()
        cfg = Config(data={"llm.provider": "openai", "llm.model": "gpt-5.5"})
        cfg.upsert_openai_profile(
            profile_id="unsloth_local",
            label="Unsloth Local",
            backend="unsloth",
            base_url="http://localhost:8888/v1",
            api_key="sk-unsloth-test",
            default_model="unsloth-default",
        )
        term.session.config = cfg
        term.session.config.save = MagicMock()
        term.session.current_model = "gpt-5.5"
        term._prompt_session.prompt.return_value = "x"
        term._fetch_compatible_models = MagicMock(return_value=[])
        term._probe_compatible_profile = MagicMock(
            return_value={
                "health": "[red]error[/red]",
                "models_path": "/v1/models",
                "models": [],
                "error": "url=http://localhost:8888/v1/models | connection refused",
            }
        )

        term._switch_model()

        rendered = "\n".join(
            str(call.args[0]) for call in term.console.print.call_args_list if call.args
        )
        assert "Warning: some compatible providers are unhealthy or returned no models." in rendered
        assert "Run /model-manager to inspect health and provider config." in rendered
        term._probe_compatible_profile.assert_called_once_with(
            base_url="http://localhost:8888/v1",
            backend="unsloth",
            api_key="sk-unsloth-test",
        )
        term.session.set_model.assert_not_called()

    def test_handle_model_manager_command_renders_diagnostics_table(self):
        term = _mk_terminal()
        cfg = Config(data={"llm.provider": "openai", "llm.model": "gpt-5.5"})
        cfg.upsert_openai_profile(
            profile_id="omlx_local",
            label="oMLX Local",
            backend="omlx",
            base_url="http://127.0.0.1:8005/v1",
            api_key="sk-omlx-test",
            set_active=True,
        )

        with patch("agent.config.Config.load", return_value=cfg):
            term._getch = MagicMock(return_value="0")
            term._probe_compatible_profile = MagicMock(
                return_value={
                    "health": "[green]healthy[/green]",
                    "models_path": "/v1/models",
                    "models": ["diffusiongemma-26B-A4B-it-4bit", "qwen3.5"],
                    "error": "",
                }
            )
            with patch("sys.stdout.flush"):
                term._handle_model_manager_command("/model-manager")

        table_calls = [c for c in term.console.print.call_args_list if c.args and isinstance(c.args[0], Table)]
        assert table_calls
        table = table_calls[-1].args[0]
        first_col = list(getattr(table.columns[0], "_cells", []))
        backend_col = list(getattr(table.columns[1], "_cells", []))
        endpoint_col = list(getattr(table.columns[2], "_cells", []))
        path_col = list(getattr(table.columns[3], "_cells", []))
        models_col = list(getattr(table.columns[6], "_cells", []))
        assert any("oMLX Local" in cell for cell in first_col)
        assert any(cell == "oMLX" for cell in backend_col)
        assert any("http://127.0.0.1:8005/v1" in cell for cell in endpoint_col)
        assert any(cell == "/v1/models" for cell in path_col)
        assert any("diffusiongemma-26B-A4B-it-4bit" in cell for cell in models_col)

    def test_handle_model_manager_command_supports_add_edit_delete_actions(self):
        term = _mk_terminal()
        cfg = Config(data={"llm.provider": "openai", "llm.model": "gpt-5.5"})
        cfg.upsert_openai_profile(
            profile_id="omlx_local",
            label="oMLX Local",
            backend="omlx",
            base_url="http://127.0.0.1:8005/v1",
            api_key="sk-omlx-test",
            set_active=True,
        )
        cfg.save = MagicMock()
        cfg.remove_openai_profile = MagicMock(return_value=True)

        with patch("agent.config.Config.load", return_value=cfg):
            term._probe_compatible_profile = MagicMock(
                return_value={
                    "health": "[green]healthy[/green]",
                    "models_path": "/v1/models",
                    "models": ["model-a"],
                    "error": "",
                }
            )
            term._create_or_edit_compatible_profile = MagicMock(
                side_effect=["new_profile", "updated_profile"]
            )
            term._prompt_select_compatible_profile_id = MagicMock(return_value="omlx_local")
            term._getch = MagicMock(side_effect=["1", "2", "3", "0"])
            with patch("sys.stdout.flush"):
                term._handle_model_manager_command("/model-manager")

        assert term._create_or_edit_compatible_profile.call_args_list[0].kwargs == {}
        assert term._create_or_edit_compatible_profile.call_args_list[1].kwargs == {
            "profile_id": "omlx_local"
        }
        cfg.remove_openai_profile.assert_called_once_with("omlx_local")

    def test_configure_openai_compatible_model_allows_blank_ollama_key(self):
        term = _mk_terminal()
        term.session.config.get.side_effect = lambda key, default=None: {
            "llm.openai_base_url": "http://localhost:11434/v1",
            "llm.openai_compatible_api_key": "",
        }.get(key, default)
        term._prompt_openai_compatible_backend = MagicMock(return_value="ollama")
        term._plain_prompt_session.prompt.side_effect = ["", "1"]
        term._secret_prompt_session.prompt.return_value = ""
        term._fetch_compatible_models = MagicMock(return_value=["llama3.1"])
        term._choose_model_from_discovered_tags = MagicMock(return_value="llama3.1")

        term._configure_openai_compatible_model()

        term.session.config.unset.assert_any_call("llm.openai_compatible_api_key")
        term.session.set_model.assert_called_once_with("llama3.1", provider="openai")

    def test_configure_openai_compatible_model_cancelled_backend(self):
        term = _mk_terminal()
        term._prompt_openai_compatible_backend = MagicMock(return_value=None)
        term._configure_openai_compatible_model()
        term.session.set_model.assert_not_called()

    def test_configure_openai_compatible_model_clears_existing_key_when_blank(self):
        term = _mk_terminal()
        term.session.config.get.side_effect = lambda key, default=None: {
            "llm.openai_base_url": "http://localhost:8888/v1",
            "llm.openai_compatible_api_key": "sk-existing",
        }.get(key, default)
        term._prompt_openai_compatible_backend = MagicMock(return_value="unsloth")
        term._plain_prompt_session.prompt.side_effect = ["", "1"]
        term._secret_prompt_session.prompt.return_value = ""
        term._fetch_compatible_models = MagicMock(return_value=["gpt-oss"])
        term._choose_model_from_discovered_tags = MagicMock(return_value="gpt-oss")

        term._configure_openai_compatible_model()

        term.session.config.unset.assert_any_call("llm.openai_compatible_api_key")

    def test_configure_openai_compatible_model_retry_with_new_api_key(self):
        term = _mk_terminal()
        term.session.config.get.side_effect = lambda key, default=None: {
            "llm.openai_base_url": "http://localhost:8000/v1",
            "llm.openai_compatible_api_key": "",
        }.get(key, default)
        term._prompt_openai_compatible_backend = MagicMock(return_value="omlx")
        term._plain_prompt_session.prompt.side_effect = [
            "",  # keep default endpoint
            "1",  # retry with new API key
            "1",  # choose discovered model
        ]
        term._secret_prompt_session.prompt.side_effect = [
            "",  # initial key prompt (blank)
            "sk-omlx-retry",  # retry key
        ]
        term._fetch_compatible_models = MagicMock(side_effect=[[], ["omlx-model"]])
        term._choose_model_from_discovered_tags = MagicMock(return_value="omlx-model")

        term._configure_openai_compatible_model()

        term._fetch_compatible_models.assert_any_call(
            "http://localhost:8000/v1",
            backend="omlx",
            api_key=None,
        )
        term._fetch_compatible_models.assert_any_call(
            "http://localhost:8000/v1",
            backend="omlx",
            api_key="sk-omlx-retry",
        )
        term.session.config.set.assert_any_call("llm.openai_compatible_api_key", "sk-omlx-retry")
        term.session.set_model.assert_called_once_with("omlx-model", provider="openai")

    def test_fetch_openai_models_success_and_dedup(self):
        term = _mk_terminal()
        payload = {"data": [{"id": "a"}, {"id": "a"}, {"id": "b"}]}
        with patch("urllib.request.urlopen", return_value=_UrlOpenResponse(payload)):
            names = term._fetch_openai_models("http://localhost:8888/v1", api_key="k")
        assert names == ["a", "b"]

    def test_fetch_openai_models_auth_error_returns_empty(self):
        term = _mk_terminal()
        err = urllib.error.HTTPError("http://x", 401, "unauthorized", hdrs=None, fp=io.BytesIO(b""))
        with patch("urllib.request.urlopen", side_effect=err):
            names = term._fetch_openai_models("http://localhost:8888/v1", api_key="k")
        assert names == []

    def test_fetch_ollama_tags_success(self):
        term = _mk_terminal()
        payload = {"models": [{"name": "phi4"}, {"model": "qwen3"}, {"name": "phi4"}]}
        with patch("urllib.request.urlopen", return_value=_UrlOpenResponse(payload)):
            names = term._fetch_ollama_tags("http://localhost:11434/v1")
        assert names == ["phi4", "qwen3"]

    def test_fetch_compatible_models_fallback_orders(self):
        term = _mk_terminal()
        with patch.object(term, "_fetch_openai_models", return_value=["m1"]) as openai_mock, patch.object(
            term, "_fetch_ollama_tags", return_value=[]
        ) as ollama_mock:
            assert term._fetch_compatible_models("http://x/v1", backend="unsloth", api_key="k") == ["m1"]
        openai_mock.assert_called_once()
        ollama_mock.assert_not_called()

        with patch.object(term, "_fetch_ollama_tags", return_value=[]), patch.object(
            term, "_fetch_openai_models", return_value=["fallback"]
        ):
            assert term._fetch_compatible_models("http://x/v1", backend="ollama", api_key="k") == ["fallback"]

        with patch.object(term, "_fetch_openai_models", return_value=[]), patch.object(
            term, "_fetch_ollama_tags", return_value=[]
        ):
            assert term._fetch_compatible_models("http://x/v1", backend="other", api_key=None) == []


class TestTasksClipboardAndTraceHelpers:
    def test_show_tasks_renders_status_branches(self):
        term = _mk_terminal()
        runner = MagicMock()
        term.agent = SimpleNamespace(_runner=runner)
        runner.get_background_watch_status.return_value = [
            {"session_id": "abcdef0123", "status": "running", "watcher_alive": True, "pending_task_ids": ["a"], "completed_task_ids": [], "connection_attempts": 1, "last_disconnect_reason": None, "last_update_at": 95},
            {"session_id": "bbbbbbbbbb", "status": "completed", "watcher_alive": False, "pending_task_ids": [], "completed_task_ids": ["x"], "connection_attempts": 2, "last_disconnect_reason": "stream_closed", "last_update_at": 94},
            {"session_id": "cccccccccc", "status": "timeout", "watcher_alive": False, "pending_task_ids": ["p1", "p2", "p3", "p4"], "completed_task_ids": [], "connection_attempts": 3, "last_disconnect_reason": "unknown", "last_update_at": 30},
            {"session_id": "dddddddddd", "status": "error", "watcher_alive": False, "pending_task_ids": [], "completed_task_ids": [], "connection_attempts": 4, "last_disconnect_reason": "connect_error", "last_update_at": 0},
        ]
        with patch("time.time", return_value=100):
            term._show_tasks(force_refresh=True)

        runner.refresh_background_watch_status.assert_called_once_with(force=True)
        table_calls = [c for c in term.console.print.call_args_list if c.args and isinstance(c.args[0], Table)]
        assert table_calls
        table = table_calls[-1].args[0]
        status_cells = list(getattr(table.columns[1], "_cells", []))
        assert any("[cyan]running[/cyan]" in s for s in status_cells)
        assert any("[green]completed[/green]" in s for s in status_cells)
        assert any("[yellow]timeout[/yellow]" in s for s in status_cells)
        assert any("[red]error[/red]" in s for s in status_cells)

    def test_copy_last_response_nonzero_return_code(self):
        term = _mk_terminal()
        term._last_response = "text"
        proc = MagicMock(returncode=1)
        with patch("subprocess.run", return_value=proc):
            term._copy_last_response()
        assert any("Clipboard not available" in str(c) for c in term.console.print.call_args_list)

    @pytest.mark.parametrize(
        "text,max_chars,expect",
        [
            ("  hello  ", 10, "hello"),
            ("x" * 12, 5, "xxxxx... [12 chars total]"),
            ("", 5, ""),
        ],
    )
    def test_truncate_for_export(self, text, max_chars, expect):
        term = _mk_terminal()
        assert term._truncate_for_export(text, max_chars=max_chars) == expect

    def test_format_tool_args_for_export(self):
        term = _mk_terminal()
        out = term._format_tool_args_for_export({"a": "x", "_meta": "skip", "b": "y\nz"})
        assert "a=x" in out
        assert "_meta" not in out
        assert "b=y z" in out

    def test_load_trace_blocks_groups_query_boundaries(self, tmp_path):
        term = _mk_terminal()
        trace_file = tmp_path / "trace.jsonl"
        trace_file.write_text("{}", encoding="utf-8")
        term.agent = SimpleNamespace(trace_store=SimpleNamespace(path=str(trace_file)))
        events = [
            {"type": "text", "content": "orphan"},
            {"type": "query_start", "q": 1},
            {"type": "tool_start", "tool": "x"},
            {"type": "query_end", "duration_s": 1.2},
            {"type": "query_start", "q": 2},
            {"type": "text", "content": "tail"},
        ]
        with patch("agent.trace_store.TraceStore.load", return_value=events):
            blocks = term._load_trace_blocks()
        assert len(blocks) == 3
        assert blocks[0]["start"] is None
        assert blocks[1]["start"]["type"] == "query_start"
        assert blocks[1]["end"]["type"] == "query_end"
        assert blocks[2]["end"] is None

    def test_render_trace_timeline_markdown_handles_event_types(self):
        term = _mk_terminal()
        block = {
            "events": [
                {"type": "text", "content": "a" * 300},
                {"type": "tool_start", "tool": "tool.a", "tool_use_id": "u1", "input": {"x": "y"}},
                {"type": "tool_result", "tool": "tool.a", "tool_use_id": "u1", "duration_s": 0.25, "result_text": "ok", "is_error": False},
                {"type": "mystery_event"},
            ]
        }
        lines = term._render_trace_timeline_markdown(block)
        joined = "\n".join(lines)
        assert "assistant:" in joined
        assert "tool start: `tool.a` (attempt 1)" in joined
        assert "tool result: `tool.a` (attempt 1) — status=ok, duration=0.25s" in joined
        assert "event: `mystery_event`" in joined


class TestTerminalWorkerAndUsageHelpers:
    def test_record_sdk_usage_updates_counters_and_persists(self):
        term = _mk_terminal()
        trajectory = MagicMock()
        term.agent = SimpleNamespace(trajectory=trajectory)
        result = SimpleNamespace(
            metadata={
                "sdk_input_tokens": 100,
                "sdk_output_tokens": 25,
                "sdk_cache_read_input_tokens": 5,
                "sdk_cache_creation_input_tokens": 2,
                "sdk_turns": 2,
                "sdk_cost_split_known": True,
                "sdk_total_cost_usd": 1.5,
                "sdk_model_usage_cost_usd": 1.0,
                "sdk_server_tool_cost_usd": 0.5,
                "sdk_models": ["claude-sonnet-4-5-20250929"],
            }
        )

        term._record_sdk_usage(result)

        assert term._session_sdk_calls == 1
        assert term._session_sdk_input_tokens == 100
        assert term._session_sdk_output_tokens == 25
        assert "claude-sonnet-4-5-20250929" in term._session_sdk_models
        trajectory.set_usage_data.assert_called_once()
        trajectory.save.assert_called_once()

    def test_submit_query_queues_when_worker_active(self):
        term = _mk_terminal()
        busy_worker = MagicMock()
        busy_worker.is_alive.return_value = True
        term._worker_thread = busy_worker

        term._submit_query("q1", {"a": 1})

        assert len(term._queued_queries) == 1
        assert term._queued_queries[0][0] == "q1"

    def test_submit_query_starts_worker_when_idle(self):
        term = _mk_terminal()
        term._ensure_live_refresh_thread = MagicMock()

        class _FakeThread:
            def __init__(self, target=None, args=None, daemon=None, name=None):
                self._target = target
                self._args = args
                self._alive = False

            def start(self):
                self._alive = True

            def is_alive(self):
                return self._alive

        with patch("ui.terminal.threading.Thread", _FakeThread), patch("ui.terminal.time.time", return_value=10.0):
            term._submit_query("q1", {"a": 1})

        assert term._worker_thread is not None
        term._ensure_live_refresh_thread.assert_called_once()
        assert term._active_query == "q1"
        assert term._active_input_tokens == 0

    def test_run_query_worker_handles_success_and_queued_follow_up(self):
        term = _mk_terminal()
        term._queued_queries = deque([("q2", {"x": 2})])
        term._record_sdk_usage = MagicMock()
        term._update_suggestions = MagicMock()
        term._run_with_clarification = MagicMock(
            side_effect=[
                SimpleNamespace(summary="s1", plan=SimpleNamespace()),
                SimpleNamespace(summary="s2", plan=SimpleNamespace()),
            ]
        )

        term._run_query_worker(("q1", {"x": 1}))

        assert term._run_with_clarification.call_count == 2
        assert term._record_sdk_usage.call_count == 2
        assert term._update_suggestions.call_count == 2
        assert term._worker_thread is None

    def test_run_query_worker_handles_exception_path(self):
        term = _mk_terminal()
        term._queued_queries = deque()
        term._run_with_clarification = MagicMock(side_effect=RuntimeError("boom"))
        term._record_sdk_usage = MagicMock()

        term._run_query_worker(("q1", {}))

        term._record_sdk_usage.assert_not_called()
        assert term._worker_thread is None


class TestTerminalPresentationAndSkills:
    def test_replay_trace_events_handles_all_event_types(self):
        term = _mk_terminal()
        renderer = MagicMock()
        events = [
            {"type": "text", "content": "reasoning text"},
            {"type": "tool_start", "tool": "tool.a", "tool_use_id": "u1", "input": {"x": 1}},
            {"type": "tool_result", "tool_use_id": "u1", "result_text": "ok", "duration_s": 0.2},
            {"type": "task_started", "task_id": "t1", "description": "desc", "task_type": "shell"},
            {"type": "task_progress", "task_id": "t1", "description": "desc", "usage": {"x": 1}},
            {"type": "task_notification", "task_id": "t1", "status": "completed", "summary": "done"},
        ]
        with patch("ui.traces.TraceRenderer", return_value=renderer):
            rendered = term._replay_trace_events(events)
        assert rendered is True
        renderer.render_reasoning.assert_called_once()
        renderer.render_tool_start.assert_called_once()
        renderer.render_tool_complete.assert_called_once()
        renderer.render_task_started.assert_called_once()
        renderer.render_task_progress.assert_called_once()
        renderer.render_task_notification.assert_called_once()

    def test_show_help_renders_panel(self):
        term = _mk_terminal()
        term._show_help()
        panel_calls = [c for c in term.console.print.call_args_list if c.args and isinstance(c.args[0], Panel)]
        assert panel_calls

    def test_skills_commands_cover_usage_and_success_paths(self):
        term = _mk_terminal()
        with patch("agent.skills.list_skills", return_value=[]):
            term._show_skills()
        with patch(
            "agent.skills.list_skills",
            return_value=[SimpleNamespace(name="fold", source="repo", description="desc")],
        ):
            term._show_skills()
        with patch("agent.skills.install_skill", return_value={"ok": True, "summary": "installed"}):
            term._add_skill("owner/repo@skills/fold")
        with patch("agent.skills.install_skill", return_value={"ok": False, "summary": "failed"}):
            term._add_skill("owner/repo@skills/fold")
        term._add_skill("")
        with patch("agent.skills.discover_skills", return_value=[]):
            term._find_skills("fold")
        with patch(
            "agent.skills.discover_skills",
            return_value=[{"name": "fold", "install_source": "owner/repo@skills/fold", "description": "desc"}],
        ):
            term._find_skills("fold")
        with patch("agent.skills.remove_skill", return_value={"ok": True, "summary": "removed"}):
            term._remove_skill("fold")
        term._remove_skill("")
        assert term.console.print.called

    def test_resolve_session_identifier_branches(self):
        term = _mk_terminal()
        sessions = [{"session_id": "abc123"}, {"session_id": "abc999"}, {"session_id": "xyz111"}]
        assert term._resolve_session_identifier("1", sessions) == "abc123"
        assert term._resolve_session_identifier("last", sessions) == "abc123"
        assert term._resolve_session_identifier("xyz", sessions) == "xyz111"
        assert term._resolve_session_identifier("999", sessions) is None
        assert term._resolve_session_identifier("abc", sessions) is None
        assert term._resolve_session_identifier("missing", sessions) is None


class TestTerminalInitAndMentionCandidates:
    def test_init_builds_prompt_sessions_and_hooks(self):
        class _Hook:
            def __init__(self):
                self.handlers = []

            def __iadd__(self, fn):
                self.handlers.append(fn)
                return self

        def _mk_prompt(*_a, **_k):
            return SimpleNamespace(
                app=SimpleNamespace(is_running=False, invalidate=MagicMock()),
                default_buffer=SimpleNamespace(on_completions_changed=_Hook()),
            )

        fake_session = SimpleNamespace(
            config=SimpleNamespace(get=lambda key, default=None: default),
            current_model="claude-sonnet-4-5-20250929",
            verbose=False,
        )

        with patch("agent.session.Session", return_value=fake_session), patch(
            "ui.terminal.Console", return_value=MagicMock()
        ), patch("ui.terminal.PromptSession", side_effect=_mk_prompt), patch.object(
            InteractiveTerminal, "_build_mention_candidates", return_value=[]
        ):
            term = InteractiveTerminal(config=None, verbose=False)

        assert term._prompt_session is not None
        assert term._secret_prompt_session is not None
        assert term._plain_prompt_session is not None
        assert term._merged_completer is not None

    def test_build_mention_candidates_includes_tools_workflows_and_files(self):
        term = _mk_terminal()
        with tempfile.TemporaryDirectory() as td:
            from pathlib import Path

            root = Path(td)
            (root / "a.txt").write_text("x", encoding="utf-8")
            (root / ".hidden").write_text("x", encoding="utf-8")
            term.session.config.get = MagicMock(
                side_effect=lambda key, default=None: str(root) if key == "data.base" else default
            )

            fake_tool = SimpleNamespace(name="target.search", category="target", description="search")
            fake_registry = SimpleNamespace(list_tools=lambda: [fake_tool])
            fake_workflows = {
                "wf-a": {"description": "workflow", "steps": ["a", "b"]},
            }

            with patch("tools.registry", fake_registry), patch(
                "tools.ensure_loaded", return_value=None
            ), patch("agent.workflows.WORKFLOWS", fake_workflows):
                candidates = term._build_mention_candidates()

        names = [c[0] for c in candidates]
        assert "target.search" in names
        assert "wf-a" in names
        assert "a.txt" in names
        assert ".hidden" not in names


class TestTerminalSessionAndCommandBranches:
    def test_resume_and_delete_session_no_saved_sessions(self):
        term = _mk_terminal()
        with patch("agent.trajectory.Trajectory.list_sessions", return_value=[]):
            term._resume_session()
            term._delete_session()
        assert term.console.print.called

    def test_resume_session_prompt_cancel_and_empty_choice(self):
        term = _mk_terminal()
        term._list_sessions = MagicMock()
        sessions = [{"session_id": "abc123"}]
        term._prompt_session.prompt.side_effect = [KeyboardInterrupt(), ""]
        with patch("agent.trajectory.Trajectory.list_sessions", return_value=sessions):
            term._resume_session()
            term._resume_session()
        term._list_sessions.assert_called()

    def test_delete_session_prompt_cancel_and_empty_choice(self):
        term = _mk_terminal()
        term._list_sessions = MagicMock()
        sessions = [{"session_id": "abc123"}]
        term._prompt_session.prompt.side_effect = [KeyboardInterrupt(), ""]
        with patch("agent.trajectory.Trajectory.list_sessions", return_value=sessions):
            term._delete_session()
            term._delete_session()
        term._list_sessions.assert_called()

    def test_handle_agents_command_usage_and_prompt_branches(self):
        term = _mk_terminal()
        term._run_orchestrated = MagicMock()
        term._handle_agents_command("/agents", {})
        term._handle_agents_command("/agents 0", {})
        term._prompt_session.prompt.side_effect = [KeyboardInterrupt(), ""]
        term._handle_agents_command("/agents 2", {})
        term._handle_agents_command("/agents 2", {})
        term._run_orchestrated.assert_not_called()

    def test_handle_case_study_list_and_unknown(self):
        term = _mk_terminal()
        fake_cases = {
            "demo": SimpleNamespace(
                name="Demo Case",
                description="A" * 120,
                thread_goals=["a", "b"],
                compound="lenalidomide",
            )
        }
        with patch("agent.case_studies.CASE_STUDIES", fake_cases):
            term._handle_case_study_command("/case-study list", {})
            term._handle_case_study_command("/case-study unknown", {})
        assert term.console.print.called


class TestTerminalUsageAndSpinnerHelpers:
    def test_coerce_helpers_and_spinner_markup(self):
        term = _mk_terminal()

        assert term._coerce_token_count("12.9") == 12
        assert term._coerce_token_count(True) == 1
        assert term._coerce_token_count("bad") == 0
        assert term._coerce_cost("2.50") == 2.5
        assert term._coerce_cost(False) == 0.0
        assert term._estimate_output_tokens_from_chars(21) == 5

        term._toolbar_frames = ["A", "B"]
        term._toolbar_frame_interval_s = 0.25
        term._toolbar_spinner_palette = ["#111111", "#222222"]
        with patch("ui.terminal.time.time", return_value=1.0):
            markup = term._toolbar_spinner_markup()
        assert "style fg" in markup
        assert "A" in markup or "B" in markup

    def test_record_sdk_usage_handles_missing_and_split_costs(self):
        term = _mk_terminal()
        term._persist_usage_to_trajectory = MagicMock()
        term.session.current_model = "fallback-model"

        term._record_sdk_usage(SimpleNamespace(metadata="invalid"))
        assert term._session_sdk_calls == 0

        term._record_sdk_usage(
            SimpleNamespace(
                metadata={
                    "sdk_input_tokens": 100,
                    "sdk_output_tokens": 40,
                    "sdk_cache_read_input_tokens": 10,
                    "sdk_cache_creation_input_tokens": 8,
                    "sdk_turns": 1,
                    "sdk_cost_split_known": True,
                    "sdk_total_cost_usd": 0.12,
                    "sdk_model_usage_cost_usd": 0.1,
                    "sdk_model": "claude-sonnet-4-5-20250929",
                }
            )
        )

        assert term._session_sdk_calls == 1
        assert term._session_sdk_extra_server_tool_cost_usd == pytest.approx(0.02)
        assert "claude-sonnet-4-5-20250929" in term._session_sdk_models
        term._persist_usage_to_trajectory.assert_called_once()

    def test_restore_usage_from_trajectory_invalid_payloads(self):
        term = _mk_terminal()

        term.agent = SimpleNamespace(trajectory=SimpleNamespace(get_usage_data=lambda: "bad"))
        term._restore_usage_from_trajectory()
        assert term._session_sdk_calls == 0

        payload = {
            "sdk_calls": "2",
            "sdk_input_tokens": "33",
            "sdk_output_tokens": "9",
            "sdk_cache_read_tokens": "4",
            "sdk_cache_creation_tokens": "1",
            "sdk_cost_usd": "0.15",
            "sdk_total_cost_usd": "0.19",
            "sdk_extra_server_tool_cost_usd": "0.04",
            "sdk_models": ["gpt-4o", ""],
            "sdk_turn_rows": [{"turn": 1}, "bad-row"],
        }
        term.agent = SimpleNamespace(trajectory=SimpleNamespace(get_usage_data=lambda: payload))
        term._restore_usage_from_trajectory()

        assert term._session_sdk_calls == 2
        assert term._session_sdk_input_tokens == 33
        assert term._session_sdk_models == {"gpt-4o"}
        assert term._session_sdk_turn_rows == [{"turn": 1}]


class TestTerminalCompatibleProfilePrompts:
    def test_prompt_select_compatible_profile_empty_and_create(self):
        term = _mk_terminal()
        cfg = MagicMock()
        cfg.openai_profiles.return_value = {}

        assert term._prompt_select_compatible_profile_id(cfg=cfg, allow_create=True) == "__create__"
        assert term._prompt_select_compatible_profile_id(cfg=cfg, allow_create=False) is None

    def test_prompt_select_compatible_profile_selection_paths(self):
        term = _mk_terminal()
        cfg = MagicMock()
        cfg.openai_profiles.return_value = {
            "p1": {"label": "First", "backend": "omlx", "base_url": "http://localhost:8000/v1"},
            "p2": {"label": "Second", "backend": "unsloth", "base_url": "http://localhost:8888/v1"},
        }
        cfg.active_openai_profile_id.return_value = "p2"

        term._plain_prompt_session.prompt.side_effect = [
            "1",        # by index
            "Second",   # by label
            "3",        # create new
            "invalid",  # invalid entry
            KeyboardInterrupt(),
        ]

        assert term._prompt_select_compatible_profile_id(cfg=cfg, allow_create=True) == "p1"
        assert term._prompt_select_compatible_profile_id(cfg=cfg, allow_create=True) == "p2"
        assert term._prompt_select_compatible_profile_id(cfg=cfg, allow_create=True) == "__create__"
        assert term._prompt_select_compatible_profile_id(cfg=cfg, allow_create=True) is None
        assert term._prompt_select_compatible_profile_id(cfg=cfg, allow_create=True) is None

    def test_prompt_profile_label_and_template_backend(self):
        term = _mk_terminal()
        term._plain_prompt_session.prompt.side_effect = ["  custom label  ", EOFError()]
        assert term._prompt_profile_label("Default Label") == "custom label"
        assert term._prompt_profile_label("Default Label") is None

        term = _mk_terminal()
        term._plain_prompt_session.prompt.side_effect = [
            "",          # default other
            "5",         # llama_cpp
            "invalid",   # invalid
            KeyboardInterrupt(),
        ]
        assert term._prompt_profile_template_backend(default_backend="other") == "other"
        assert term._prompt_profile_template_backend(default_backend="bad-backend") == "llama_cpp"
        assert term._prompt_profile_template_backend(default_backend="ollama") is None
        assert term._prompt_profile_template_backend(default_backend="ollama") is None

    def test_current_provider_status_handles_legacy_compat_and_modes(self):
        term = _mk_terminal()
        values = {
            "llm.provider": "openai",
            "llm.openai_base_url": "http://localhost:8000/v1",
            "llm.openai_compatible_backend": "omlx",
            "llm.openai_compatible_api_key": "sk-omlx",
            "llm.openai_api_key": "sk-openai",
        }
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: values.get(key, default)
        cfg.get_openai_profile.side_effect = RuntimeError("profile read failed")
        cfg.llm_openai_base_url.return_value = "http://localhost:8000/v1"
        term.session.config = cfg
        term.session.current_model = "custom-model"

        provider, label, endpoint = term._current_provider_status()
        assert provider == "openai"
        assert "OpenAI-compatible custom endpoint" in label
        assert endpoint == "http://localhost:8000/v1"

        values["llm.provider"] = "anthropic"
        provider2, label2, endpoint2 = term._current_provider_status()
        assert provider2 == "openai"
        assert "OpenAI-compatible custom endpoint" in label2
        assert endpoint2 == "http://localhost:8000/v1"
