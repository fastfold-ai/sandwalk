"""Extra coverage for InteractiveTerminal settings/tasks helpers."""

import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ui.terminal import InteractiveTerminal


def _mk_terminal_stub():
    term = InteractiveTerminal.__new__(InteractiveTerminal)
    store = {"agent.plan_preview": False, "llm.openai_compatible_api_key": ""}

    def _get(key, default=None):
        return store.get(key, default)

    def _set(key, value):
        store[key] = value

    cfg = SimpleNamespace(get=_get, set=_set, save=MagicMock(), unset=MagicMock())
    llm = SimpleNamespace(usage=SimpleNamespace(calls=[]))
    term.session = SimpleNamespace(config=cfg, get_llm=lambda: llm)
    term.console = MagicMock()
    term._run_lock = MagicMock()
    term._run_lock.__enter__ = lambda *_a: None
    term._run_lock.__exit__ = lambda *_a: None
    term._session_sdk_calls = 0
    term._session_sdk_input_tokens = 0
    term._session_sdk_output_tokens = 0
    term._session_sdk_cache_read_tokens = 0
    term._session_sdk_cache_creation_tokens = 0
    term._session_sdk_models = set()
    term._session_sdk_turn_rows = []
    term._plain_prompt_session = SimpleNamespace(prompt=MagicMock(return_value=""))
    return term, store


class TestTerminalTasksAndUsage:
    def test_show_tasks_no_runner(self):
        term, _ = _mk_terminal_stub()
        term._show_tasks()
        term.console.print.assert_called()

    def test_show_tasks_with_status_rows(self):
        term, _ = _mk_terminal_stub()
        runner = SimpleNamespace(
            refresh_background_watch_status=MagicMock(),
            get_background_watch_status=MagicMock(
                return_value=[
                    {
                        "session_id": "session-abcdefgh",
                        "status": "running",
                        "watcher_alive": True,
                        "connection_attempts": 2,
                        "pending_task_ids": ["task1", "task2", "task3", "task4"],
                        "completed_task_ids": ["done1"],
                        "last_update_at": 1.0,
                        "last_disconnect_reason": "stream_closed",
                    }
                ]
            ),
        )
        term.agent = SimpleNamespace(_runner=runner)
        with patch("ui.terminal.time.time", return_value=90.0):
            term._show_tasks(force_refresh=True)
        runner.refresh_background_watch_status.assert_called_once_with(force=True)
        term.console.print.assert_called()

    def test_show_usage_fallback_no_calls(self):
        term, _ = _mk_terminal_stub()
        term._show_usage()
        term.console.print.assert_called()

    def test_show_usage_sdk_table_branch(self):
        term, _ = _mk_terminal_stub()
        term._session_sdk_calls = 1
        term._session_sdk_input_tokens = 12
        term._session_sdk_output_tokens = 3
        term._session_sdk_models = {"claude-x"}
        term._session_sdk_turn_rows = [
            {
                "turn": 1,
                "input_tokens": 12,
                "output_tokens": 3,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
                "models": ["claude-x"],
            }
        ]
        term._show_usage()
        term.console.print.assert_called()


class TestTerminalOpenAICompatibleHelpers:
    def test_prompt_openai_compatible_backend_defaults_and_invalid(self):
        term, store = _mk_terminal_stub()
        store["llm.openai_compatible_api_key"] = "sk-unsloth-abc"
        term._plain_prompt_session.prompt = MagicMock(side_effect=["", "9"])
        assert term._prompt_openai_compatible_backend("http://localhost:11434/v1") == "unsloth"
        assert term._prompt_openai_compatible_backend("http://localhost:11434/v1") == "other"

    def test_prompt_openai_compatible_backend_lm_studio_option(self):
        term, _ = _mk_terminal_stub()
        term._plain_prompt_session.prompt = MagicMock(return_value="6")
        assert term._prompt_openai_compatible_backend("http://localhost:11434/v1") == "lm_studio"

    def test_choose_model_from_discovered_tags_manual(self):
        term, _ = _mk_terminal_stub()
        term._plain_prompt_session.prompt = MagicMock(side_effect=["9", "my-model"])
        selected = term._choose_model_from_discovered_tags(["a", "b"], "default-model")
        assert selected == "my-model"

    def test_fetch_openai_models_http_401(self):
        term, _ = _mk_terminal_stub()
        import urllib.error

        err = urllib.error.HTTPError(
            url="http://localhost:11434/v1/models",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"invalid api key","code":"invalid_api_key"}}'),
        )
        with patch("ui.terminal.urllib.request.urlopen", side_effect=err):
            names = term._fetch_openai_models("http://localhost:11434/v1", api_key="x")
        assert names == []
        printed = " ".join(str(call) for call in term.console.print.call_args_list)
        assert "/v1/models request failed" in printed
        assert "invalid api key" in printed
        assert "requires endpoint auth" in printed

    def test_fetch_openai_models_success(self):
        term, _ = _mk_terminal_stub()

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"data": [{"id": "m1"}, {"id": "m2"}]}).encode()

        with patch("ui.terminal.urllib.request.urlopen", return_value=_Resp()):
            names = term._fetch_openai_models("http://localhost:11434/v1", api_key="x")
        assert names == ["m1", "m2"]

    def test_fetch_ollama_tags_success(self):
        term, _ = _mk_terminal_stub()

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"models": [{"name": "llama3.1"}, {"model": "qwen3"}]}).encode()

        with patch("ui.terminal.urllib.request.urlopen", return_value=_Resp()):
            names = term._fetch_ollama_tags("http://localhost:11434/v1")
        assert names == ["llama3.1", "qwen3"]

    def test_fetch_compatible_models_empty_warning(self):
        term, _ = _mk_terminal_stub()
        term._fetch_openai_models = MagicMock(return_value=[])
        term._fetch_ollama_tags = MagicMock(return_value=[])
        names = term._fetch_compatible_models("http://localhost:11434/v1", backend="other")
        assert names == []
        term.console.print.assert_called()

    def test_fetch_compatible_models_lm_studio_uses_openai_only(self):
        term, _ = _mk_terminal_stub()
        term._fetch_openai_models = MagicMock(return_value=["local-model"])
        term._fetch_ollama_tags = MagicMock(return_value=["should-not-run"])
        names = term._fetch_compatible_models("http://localhost:1234/v1", backend="lm_studio")
        assert names == ["local-model"]
        term._fetch_openai_models.assert_called_once()
        term._fetch_ollama_tags.assert_not_called()

    def test_prompt_discovery_followup_action_defaults_to_manual(self):
        term, _ = _mk_terminal_stub()
        term._plain_prompt_session.prompt.return_value = ""
        assert term._prompt_discovery_followup_action() == "manual"


class TestTerminalSettingsMenu:
    def test_toggle_plan_mode(self):
        term, store = _mk_terminal_stub()
        term._toggle_plan_mode()
        assert store["agent.plan_preview"] is True

    def test_change_settings_exit_immediately(self):
        term, _ = _mk_terminal_stub()
        term._getch = MagicMock(side_effect=["0"])
        with patch("sys.stdout.flush"):
            term._change_settings()
        term.console.print.assert_called()
