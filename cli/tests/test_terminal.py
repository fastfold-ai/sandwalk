"""Tests for contextual ghost-text suggestions and terminal features."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
from prompt_toolkit.document import Document
from prompt_toolkit.completion import CompleteEvent
from rich.markdown import Markdown
from rich.table import Table
from ui.terminal import (  # type: ignore[import-untyped]
    _extract_llm_suggestions,
    extract_mentions,
    build_mention_context,
    MentionCompleter,
    MergedCompleter,
    SlashCompleter,
    DATASET_CANDIDATES,
    KNOWN_DATASETS,
    DEFAULT_SUGGESTIONS,
    SLASH_COMMANDS,
    InteractiveTerminal,
)



class TestSlashCommands:
    """Verify all expected slash commands are registered."""

    def test_core_commands_registered(self):
        expected = ["/help", "/tools", "/model", "/settings", "/usage", "/copy",
                    "/export", "/compact", "/new", "/sessions", "/resume", "/upgrade",
                    "/clear", "/exit", "/config", "/keys", "/doctor"]
        for cmd in expected:
            assert cmd in SLASH_COMMANDS, f"{cmd} not in SLASH_COMMANDS"

    def test_slash_commands_have_descriptions(self):
        for cmd, desc in SLASH_COMMANDS.items():
            assert isinstance(desc, str) and len(desc) > 5, f"{cmd} has no description"

    def test_skills_commands_registered(self):
        for cmd in ["/skills", "/skills-add", "/skills-find", "/skills-upgrade", "/skills-remove"]:
            assert cmd in SLASH_COMMANDS, f"{cmd} not in SLASH_COMMANDS"



class TestTerminalMethods:
    """Unit tests for InteractiveTerminal methods (no actual REPL)."""

    @pytest.fixture
    def terminal(self):
        """Create a terminal with mocked session."""
        with patch("ui.terminal.InteractiveTerminal.__init__", return_value=None):
            t = InteractiveTerminal.__new__(InteractiveTerminal)
            t.session = MagicMock()
            t.session.verbose = False
            t.session.current_model = "claude-sonnet-4-5-20250929"
            t.console = MagicMock()
            t._last_response = None
            t._verbose_hint = None
            t._show_exit_hint = False
            t._suggestions = list(DEFAULT_SUGGESTIONS)
            t._suggestion_idx = 0
            t._run_lock = MagicMock()
            t._run_lock.__enter__ = MagicMock(return_value=None)
            t._run_lock.__exit__ = MagicMock(return_value=False)
            return t

    def test_model_display_name(self, terminal):
        assert terminal._model_display_name("claude-sonnet-4-5-20250929") == "Sonnet 4.5"
        assert terminal._model_display_name("claude-opus-4-6") == "Opus 4.6"
        assert terminal._model_display_name("gpt-5.5") == "GPT-5.5"
        assert terminal._model_display_name("gpt-5.4-mini") == "GPT-5.4 Mini"
        assert terminal._model_display_name("unknown-model") == "unknown-model"

    def test_current_provider_status_openai_compatible_when_custom_endpoint_active(self, terminal):
        def _cfg_get(key, default=None):
            values = {
                "llm.provider": "anthropic",
                "llm.openai_base_url": "http://ai-server.tailnet:11434/v1",
            }
            return values.get(key, default)

        terminal.session.config.get.side_effect = _cfg_get
        terminal.session.current_model = "qwen3.6:27b"
        provider, label, endpoint = terminal._current_provider_status()
        assert provider == "openai"
        assert label == "OpenAI-compatible custom endpoint"
        assert endpoint == "http://ai-server.tailnet:11434/v1"

    def test_current_compatible_backend_label_prefers_config_value(self, terminal):
        def _cfg_get(key, default=None):
            values = {
                "llm.provider": "openai",
                "llm.openai_base_url": "http://localhost:11434/v1",
                "llm.openai_compatible_backend": "unsloth",
                "llm.openai_compatible_api_key": "sk-unsloth-test",
            }
            return values.get(key, default)

        terminal.session.config.get.side_effect = _cfg_get
        assert terminal._current_compatible_backend_label() == "Unsloth"

    def test_bottom_toolbar_shows_compatible_backend_next_to_model(self, terminal):
        def _cfg_get(key, default=None):
            values = {
                "llm.provider": "openai",
                "llm.openai_base_url": "http://localhost:8888/v1",
                "llm.openai_compatible_backend": "unsloth",
                "agent.plan_preview": False,
            }
            return values.get(key, default)

        terminal.session.config.get.side_effect = _cfg_get
        terminal.session.current_model = "gemma4:e2b-mlx"
        terminal.session.verbose = False
        terminal._show_interrupt_hint = False
        terminal._worker_thread = None
        terminal._queued_queries = []
        toolbar = terminal._bottom_toolbar()
        assert "gemma4:e2b-mlx" in str(toolbar)
        assert "Unsloth" in str(toolbar)

    def test_switch_model_header_shows_compatible_backend_next_to_model(self, terminal):
        def _cfg_get(key, default=None):
            values = {
                "llm.provider": "openai",
                "llm.openai_base_url": "http://localhost:11434/v1",
                "llm.openai_compatible_backend": "ollama",
            }
            return values.get(key, default)

        terminal.session.config.get.side_effect = _cfg_get
        terminal.session.current_model = "gemma4:e2b-mlx"
        terminal._prompt_session = MagicMock()
        terminal._prompt_session.prompt.return_value = "x"  # cancel after header render

        terminal._switch_model()

        rendered = "\n".join(str(call.args[0]) for call in terminal.console.print.call_args_list if call.args)
        assert "Current model:" in rendered
        assert "gemma4:e2b-mlx (Ollama)" in rendered
        assert "Provider:" in rendered
        assert "OpenAI-compatible custom endpoint (Ollama)" in rendered

    def test_ollama_tags_url_from_openai_base_url(self, terminal):
        del terminal  # static method coverage only
        assert (
            InteractiveTerminal._ollama_tags_url_from_base("http://localhost:11434/v1")
            == "http://localhost:11434/api/tags"
        )
        assert (
            InteractiveTerminal._ollama_tags_url_from_base("http://example.com/custom/v1")
            == "http://example.com/custom/api/tags"
        )

    def test_openai_models_url_from_base_url(self, terminal):
        del terminal
        assert (
            InteractiveTerminal._openai_models_url_from_base("http://localhost:11434/v1")
            == "http://localhost:11434/v1/models"
        )
        assert (
            InteractiveTerminal._openai_models_url_from_base("http://example.com/custom")
            == "http://example.com/custom/v1/models"
        )

    def test_switch_model_can_change_provider(self, terminal):
        terminal.session.config.get.side_effect = (
            lambda key, default=None: "anthropic" if key == "llm.provider" else default
        )
        terminal._prompt_session = MagicMock()
        # 4th option in AVAILABLE_MODELS order is gpt-5.5 (openai)
        terminal._prompt_session.prompt.return_value = "4"

        terminal._switch_model()

        terminal.session.set_model.assert_called_once_with("gpt-5.5", provider="openai")
        terminal.session.config.unset.assert_any_call("llm.openai_base_url")
        terminal.session.config.unset.assert_any_call("llm.openai_compatible_backend")
        terminal.session.config.save.assert_called_once()

    def test_switch_model_no_change_when_same_model_and_provider(self, terminal):
        terminal.session.config.get.side_effect = (
            lambda key, default=None: "anthropic" if key == "llm.provider" else default
        )
        terminal._prompt_session = MagicMock()
        # 1st option is current model (claude-sonnet-4-5-20250929, anthropic)
        terminal._prompt_session.prompt.return_value = "1"

        terminal._switch_model()

        terminal.session.set_model.assert_not_called()
        terminal.session.config.save.assert_not_called()

    def test_configure_openai_compatible_model_custom_endpoint(self, terminal):
        def _cfg_get(key, default=None):
            values = {
                "llm.provider": "anthropic",
                "llm.openai_base_url": None,
                "llm.openai_compatible_api_key": None,
            }
            return values.get(key, default)

        terminal.session.config.get.side_effect = _cfg_get
        terminal._plain_prompt_session = MagicMock()
        terminal._secret_prompt_session = MagicMock()
        terminal._fetch_compatible_models = MagicMock(return_value=["qwen3.6:27b", "llama3.1"])
        terminal._plain_prompt_session.prompt.side_effect = [
            "1",  # backend type (Ollama)
            "http://localhost:11434/v1",  # endpoint
            "1",  # select discovered model
        ]
        terminal._secret_prompt_session.prompt.return_value = ""  # blank key accepted

        terminal._configure_openai_compatible_model()

        terminal.session.set_model.assert_called_once_with("qwen3.6:27b", provider="openai")
        terminal.session.config.set.assert_any_call("llm.openai_base_url", "http://localhost:11434/v1")
        terminal.session.config.set.assert_any_call("llm.openai_compatible_backend", "ollama")
        terminal.session.config.unset.assert_any_call("llm.openai_compatible_api_key")
        terminal.session.config.save.assert_called_once()

    def test_configure_openai_compatible_model_unsloth_defaults_to_8888_endpoint(self, terminal):
        def _cfg_get(key, default=None):
            values = {
                "llm.provider": "anthropic",
                "llm.openai_base_url": None,
                "llm.openai_compatible_api_key": None,
            }
            return values.get(key, default)

        terminal.session.config.get.side_effect = _cfg_get
        terminal._plain_prompt_session = MagicMock()
        terminal._secret_prompt_session = MagicMock()
        terminal._fetch_compatible_models = MagicMock(return_value=["gpt-oss:20b"])
        terminal._plain_prompt_session.prompt.side_effect = [
            "2",  # backend type (Unsloth)
            "",  # accept default endpoint (should use 8888)
            "1",  # pick discovered model
        ]
        terminal._secret_prompt_session.prompt.return_value = "sk-unsloth-test"  # custom key

        terminal._configure_openai_compatible_model()

        terminal.session.config.set.assert_any_call("llm.openai_compatible_backend", "unsloth")
        terminal._fetch_compatible_models.assert_called_once_with(
            "http://localhost:8888/v1",
            backend="unsloth",
            api_key="sk-unsloth-test",
        )

    def test_configure_openai_compatible_model_unsloth_replaces_ollama_default_endpoint(self, terminal):
        def _cfg_get(key, default=None):
            values = {
                "llm.provider": "openai",
                "llm.openai_base_url": "http://localhost:11434/v1",
                "llm.openai_compatible_api_key": None,
            }
            return values.get(key, default)

        terminal.session.config.get.side_effect = _cfg_get
        terminal._plain_prompt_session = MagicMock()
        terminal._secret_prompt_session = MagicMock()
        terminal._fetch_compatible_models = MagicMock(return_value=["gpt-oss:20b"])
        terminal._plain_prompt_session.prompt.side_effect = [
            "2",  # backend type (Unsloth)
            "",  # accept default endpoint (must be 8888, not prior 11434)
            "1",  # select model
        ]
        terminal._secret_prompt_session.prompt.return_value = "sk-unsloth-test"  # key

        terminal._configure_openai_compatible_model()

        terminal._fetch_compatible_models.assert_called_once_with(
            "http://localhost:8888/v1",
            backend="unsloth",
            api_key="sk-unsloth-test",
        )

    def test_ensure_llm_ready_prompts_and_saves_openai_key(self, terminal):
        terminal.session.config.llm_preflight_issue.side_effect = [
            "OpenAI API key not configured",
            None,
        ]
        terminal.session.config.get.side_effect = (
            lambda key, default=None: "openai" if key == "llm.provider" else default
        )
        terminal._secret_prompt_session = MagicMock()
        terminal._secret_prompt_session.prompt.return_value = "sk-openai-123"
        assert terminal._ensure_llm_ready_for_query() is True
        terminal.session.config.set.assert_called_once_with("llm.openai_api_key", "sk-openai-123")
        terminal.session.config.save.assert_called_once()

    def test_ensure_llm_ready_uses_openai_compatible_key_for_custom_endpoint(self, terminal):
        terminal.session.config.llm_preflight_issue.side_effect = [
            "OpenAI-compatible API key not configured",
            None,
        ]

        def _cfg_get(key, default=None):
            values = {
                "llm.provider": "openai",
                "llm.openai_base_url": "http://localhost:11434/v1",
            }
            return values.get(key, default)

        terminal.session.config.get.side_effect = _cfg_get
        terminal._secret_prompt_session = MagicMock()
        terminal._secret_prompt_session.prompt.return_value = "ollama"
        assert terminal._ensure_llm_ready_for_query() is True
        terminal.session.config.set.assert_called_once_with("llm.openai_compatible_api_key", "ollama")
        terminal.session.config.save.assert_called_once()

    def test_ensure_llm_ready_cancelled_returns_false(self, terminal):
        terminal.session.config.llm_preflight_issue.return_value = "OpenAI API key not configured"
        terminal.session.config.get.side_effect = (
            lambda key, default=None: "openai" if key == "llm.provider" else default
        )
        terminal._secret_prompt_session = MagicMock()
        terminal._secret_prompt_session.prompt.return_value = ""
        assert terminal._ensure_llm_ready_for_query() is False

    def test_ensure_llm_ready_prompts_and_saves_anthropic_key(self, terminal):
        terminal.session.config.llm_preflight_issue.side_effect = [
            "Anthropic API key not configured",
            None,
        ]
        terminal.session.config.get.side_effect = (
            lambda key, default=None: "anthropic" if key == "llm.provider" else default
        )
        terminal._secret_prompt_session = MagicMock()
        terminal._secret_prompt_session.prompt.return_value = "sk-ant-api03-test"
        assert terminal._ensure_llm_ready_for_query() is True
        terminal.session.config.set.assert_called_once_with(
            "llm.anthropic_api_key", "sk-ant-api03-test"
        )
        terminal.session.config.save.assert_called_once()

    def test_ensure_llm_ready_invalid_key_returns_false(self, terminal):
        terminal.session.config.llm_preflight_issue.return_value = "OpenAI API key not configured"
        terminal.session.config.get.side_effect = (
            lambda key, default=None: "openai" if key == "llm.provider" else default
        )
        terminal.session.config.set.side_effect = ValueError("Invalid OpenAI API key format")
        terminal._secret_prompt_session = MagicMock()
        terminal._secret_prompt_session.prompt.return_value = "bad-key"
        assert terminal._ensure_llm_ready_for_query() is False

    def test_copy_no_response(self, terminal):
        terminal._copy_last_response()
        terminal.console.print.assert_called_once()
        assert "No response" in str(terminal.console.print.call_args)

    def test_copy_with_response(self, terminal):
        terminal._last_response = "GSPT1 is a promising target."
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            terminal._copy_last_response()
            mock_run.assert_called_once()
            assert mock_run.call_args[1]["input"] == b"GSPT1 is a promising target."

    def test_copy_clipboard_unavailable(self, terminal):
        terminal._last_response = "Some text"
        with patch("subprocess.run", side_effect=FileNotFoundError):
            terminal._copy_last_response()
            assert "not available" in str(terminal.console.print.call_args).lower()

    def test_export_no_session(self, terminal):
        terminal._export_session()
        terminal.console.print.assert_called_once()
        assert "No session" in str(terminal.console.print.call_args)

    def test_export_with_trajectory(self, terminal, tmp_path):
        """Export should write a markdown file."""
        from agent.trajectory import Turn, Trajectory  # type: ignore[import-untyped]
        terminal.agent = MagicMock()
        terminal.agent.trajectory = Trajectory()
        terminal.agent.trajectory.turns = [
            Turn(query="test query", answer="test answer",
                 entities=["TP53"], tools_used=["target.coessentiality"],
                 timestamp=0),
        ]
        with patch("pathlib.Path.home", return_value=tmp_path), patch(
            "ui.terminal.Path.cwd", return_value=tmp_path
        ):
            terminal._export_session()
            exports = list((tmp_path / "exports").glob("*.md"))
            assert len(exports) == 1
            content = exports[0].read_text()
            assert "test query" in content
            assert "test answer" in content
            assert "TP53" in content
            exports[0].unlink(missing_ok=True)

    def test_run_shell_basic(self, terminal):
        terminal._run_shell("echo hello")
        # Should have printed the output
        terminal.console.print.assert_called()
        output = str(terminal.console.print.call_args_list[0])
        assert "hello" in output

    def test_run_shell_empty(self, terminal):
        terminal._run_shell("")
        terminal.console.print.assert_called_once()
        assert "Usage" in str(terminal.console.print.call_args)

    def test_run_shell_timeout(self, terminal):
        with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("cmd", 30)):
            terminal._run_shell("sleep 100")
            assert "timed out" in str(terminal.console.print.call_args).lower()

    def test_run_shell_blocked(self, terminal):
        terminal._run_shell("rm -rf /tmp/x")
        terminal.console.print.assert_called_once()
        assert "blocked" in str(terminal.console.print.call_args).lower()

    def test_advance_suggestion(self, terminal):
        assert terminal._suggestion_idx == 0
        terminal._advance_suggestion()
        assert terminal._suggestion_idx == 1

    def test_update_suggestions_with_llm_result(self, terminal):
        """_update_suggestions extracts LLM suggestions from result.summary."""
        result = MagicMock()
        result.summary = (
            "## Suggested Next Steps\n"
            "- **\"Check co-essential partners of BRCA1\"**\n"
            "- **\"Run pathway enrichment on BRCA1 signature\"**\n"
        )
        terminal._update_suggestions("analyze BRCA1", result=result)
        assert len(terminal._suggestions) == 2
        assert any("BRCA1" in s for s in terminal._suggestions)

    def test_compact_context_calls_llm_chat_with_messages(self, terminal):
        from agent.trajectory import Trajectory, Turn

        terminal.agent = MagicMock()
        trajectory = Trajectory()
        trajectory.turns = [
            Turn(query="q1", answer="a1"),
            Turn(query="q2", answer="a2"),
            Turn(query="q3", answer="a3"),
        ]
        terminal.agent.trajectory = trajectory

        mock_llm = MagicMock()
        mock_llm.chat.return_value = MagicMock(content="session summary text")
        terminal.session.get_llm.return_value = mock_llm

        terminal._compact_context("focus on actionable outcomes")

        kwargs = mock_llm.chat.call_args.kwargs
        assert kwargs["system"].startswith("You are a research session summarizer")
        assert kwargs["messages"][0]["role"] == "user"
        assert "focus on actionable outcomes" in kwargs["messages"][0]["content"]

        assert len(terminal.agent.trajectory.turns) == 2
        assert terminal.agent.trajectory.turns[0].query == "[session summary]"
        assert terminal.agent.trajectory.turns[0].answer == "session summary text"

    def test_run_orchestrated_updates_suggestions_from_result(self, terminal):
        terminal.agent = MagicMock()
        terminal._update_suggestions = MagicMock()

        result = MagicMock()
        result.summary = "summary"
        result.merged_plan = MagicMock()

        with patch("agent.orchestrator.ResearchOrchestrator") as mock_orchestrator:
            mock_orchestrator.return_value.run.return_value = result
            terminal._run_orchestrated("query", {}, 2)

        terminal._update_suggestions.assert_called_once_with("query", result.merged_plan, result)

    def test_case_study_updates_suggestions_from_result(self, terminal):
        terminal._update_suggestions = MagicMock()

        result = MagicMock()
        result.summary = "summary"
        result.merged_plan = MagicMock()

        case = MagicMock()
        case.name = "Demo Case"
        case.description = "desc"
        case.compound = "lenalidomide"

        with patch("agent.case_studies.CASE_STUDIES", {"demo": case}), patch(
            "agent.case_studies.run_case_study",
            return_value=result,
        ):
            terminal._handle_case_study_command("/case-study demo", {})

        terminal._update_suggestions.assert_called_once_with(case.compound, result.merged_plan, result)

    def test_list_sessions_renders_threads_style_table(self, terminal):
        terminal.agent = MagicMock()
        terminal.agent.trajectory.session_id = "ab123456"
        sessions = [
            {
                "session_id": "ab123456",
                "title": "Current session title",
                "n_turns": 4,
                "model": "gpt-5.5",
                "created_at": 1000,
                "updated_at": 2000,
            },
            {
                "session_id": "cd789012",
                "title": "Other session title",
                "n_turns": 2,
                "model": "claude-sonnet-4-5-20250929",
                "created_at": 900,
                "updated_at": 1500,
            },
        ]
        with patch("agent.trajectory.Trajectory.list_sessions", return_value=sessions), patch(
            "time.time", return_value=2002
        ):
            terminal._list_sessions()
        table_calls = [
            c for c in terminal.console.print.call_args_list if c.args and isinstance(c.args[0], Table)
        ]
        assert table_calls
        table = table_calls[-1].args[0]
        headers = [col.header for col in table.columns]
        assert headers == ["", "ID", "Preview", "Messages", "Model", "Last Used"]

    def test_list_sessions_preview_collapses_multiline_titles(self, terminal):
        terminal.agent = MagicMock()
        terminal.agent.trajectory.session_id = "ab123456"
        sessions = [
            {
                "session_id": "ab123456",
                "title": "Use esm1b in Fastfold to run a fold job.\n\nUse these sequences:\nSequence 1",
                "n_turns": 3,
                "model": "claude-sonnet-4-5-20250929",
                "created_at": 1000,
                "updated_at": 2000,
            },
        ]
        with patch("agent.trajectory.Trajectory.list_sessions", return_value=sessions), patch(
            "time.time", return_value=2002
        ):
            terminal._list_sessions()

        table_calls = [
            c for c in terminal.console.print.call_args_list if c.args and isinstance(c.args[0], Table)
        ]
        table = table_calls[-1].args[0]
        previews = list(getattr(table.columns[2], "_cells", []))
        assert previews
        assert "\n" not in previews[0]
        assert "Use these sequences:" in previews[0]

    def test_resume_session_accepts_session_prefix(self, terminal):
        sessions = [
            {"session_id": "abc12345"},
            {"session_id": "xyz98765"},
        ]
        with patch("agent.trajectory.Trajectory.list_sessions", return_value=sessions), patch(
            "agent.loop.AgentLoop.resume"
        ) as mock_resume:
            terminal._resume_session("abc")
        mock_resume.assert_called_once()
        assert mock_resume.call_args.args[1] == "abc12345"

    def test_delete_session_accepts_prefix(self, terminal):
        sessions = [
            {"session_id": "abc12345"},
            {"session_id": "xyz98765"},
        ]
        terminal.agent = MagicMock()
        terminal.agent.trajectory.session_id = "other999"
        with patch("agent.trajectory.Trajectory.list_sessions", return_value=sessions), patch(
            "agent.trajectory.Trajectory.delete_session",
            return_value={"session_id": "abc12345", "session_deleted": True, "trace_deleted": True},
        ) as mock_delete:
            terminal._delete_session("abc")
        mock_delete.assert_called_once_with("abc12345")

    def test_delete_current_session_switches_to_new_loop(self, terminal):
        sessions = [{"session_id": "abc12345"}]
        terminal.agent = MagicMock()
        terminal.agent.trajectory.session_id = "abc12345"
        new_loop = MagicMock()
        new_loop.trajectory.session_id = "new11111"
        with patch("agent.trajectory.Trajectory.list_sessions", return_value=sessions), patch(
            "agent.trajectory.Trajectory.delete_session",
            return_value={"session_id": "abc12345", "session_deleted": True, "trace_deleted": False},
        ), patch("agent.loop.AgentLoop", return_value=new_loop):
            terminal._delete_session("abc12345")
        assert terminal.agent is new_loop

    def test_new_session_creates_fresh_loop_and_resets_usage(self, terminal):
        terminal.agent = MagicMock()
        terminal._last_response = "old response"
        terminal._session_sdk_calls = 5
        terminal._session_sdk_input_tokens = 100
        terminal._session_sdk_output_tokens = 50
        terminal._session_sdk_cache_read_tokens = 10
        terminal._session_sdk_cache_creation_tokens = 2
        terminal._session_sdk_cost_usd = 1.2
        terminal._session_sdk_total_cost_usd = 1.3
        terminal._session_sdk_extra_server_tool_cost_usd = 0.1
        terminal._session_sdk_models = {"gpt-5.5"}
        terminal._session_sdk_turn_rows = [{"turn": 1}]

        new_loop = MagicMock()
        new_loop.trajectory.session_id = "new12345"
        with patch("agent.loop.AgentLoop", return_value=new_loop), patch(
            "cli.print_banner"
        ) as mock_print_banner:
            terminal._new_session()

        terminal.console.clear.assert_called_once()
        mock_print_banner.assert_called_once()
        assert terminal.agent is new_loop
        assert terminal._last_response is None
        assert terminal._session_sdk_calls == 0
        assert terminal._session_sdk_input_tokens == 0
        assert terminal._session_sdk_output_tokens == 0
        assert terminal._session_sdk_cache_read_tokens == 0
        assert terminal._session_sdk_cache_creation_tokens == 0
        assert terminal._session_sdk_cost_usd == 0.0
        assert terminal._session_sdk_total_cost_usd == 0.0
        assert terminal._session_sdk_extra_server_tool_cost_usd == 0.0
        assert terminal._session_sdk_models == set()
        assert terminal._session_sdk_turn_rows == []

    def test_print_exit_with_resume_hint(self, terminal):
        terminal.agent = MagicMock()
        terminal.agent.trajectory.session_id = "d0b0571d"
        terminal.agent.trajectory.turns = [MagicMock()]
        terminal._print_exit_with_resume_hint()
        printed = " ".join(str(c) for c in terminal.console.print.call_args_list)
        assert "Resume this session with:" in printed
        assert "fastfold --resume d0b0571d" in printed

    def test_print_exit_without_messages_hides_resume_hint(self, terminal):
        terminal.agent = MagicMock()
        terminal.agent.trajectory.session_id = "d0b0571d"
        terminal.agent.trajectory.turns = []
        terminal._print_exit_with_resume_hint()
        printed = " ".join(str(c) for c in terminal.console.print.call_args_list)
        assert "Goodbye!" in printed
        assert "Resume this session with:" not in printed

    def test_render_resumed_history_shows_query_and_answer(self, terminal):
        turn = MagicMock()
        turn.query = "what can you do?"
        turn.answer = "I can help with target discovery."
        terminal._render_resumed_history(40, [turn])
        printed = " ".join(str(c) for c in terminal.console.print.call_args_list)
        assert "Session History" in printed
        assert "what can you do?" in printed
        markdown_calls = [
            c.args[0]
            for c in terminal.console.print.call_args_list
            if c.args and isinstance(c.args[0], Markdown)
        ]
        assert markdown_calls
        assert markdown_calls[0].markup == "I can help with target discovery."

    def test_render_resumed_history_prefers_trace_replay(self, terminal):
        turn = MagicMock()
        turn.query = "run fold"
        turn.answer = "I can run fold."
        with patch.object(terminal, "_load_trace_blocks", return_value=[{"events": [{"type": "text", "content": "Trace text"}]}]), patch.object(
            terminal, "_replay_trace_events", return_value=True
        ) as mock_replay:
            terminal._render_resumed_history(40, [turn])
        mock_replay.assert_called_once()
        markdown_calls = [
            c.args[0]
            for c in terminal.console.print.call_args_list
            if c.args and isinstance(c.args[0], Markdown)
        ]
        assert not markdown_calls

    def test_render_resumed_history_trace_without_text_falls_back_to_answer(self, terminal):
        turn = MagicMock()
        turn.query = "run fold"
        turn.answer = "I can run fold."
        with patch.object(terminal, "_load_trace_blocks", return_value=[{"events": [{"type": "tool_start", "tool": "x"}]}]), patch.object(
            terminal, "_replay_trace_events", return_value=False
        ) as mock_replay:
            terminal._render_resumed_history(40, [turn])
        mock_replay.assert_called_once()
        markdown_calls = [
            c.args[0]
            for c in terminal.console.print.call_args_list
            if c.args and isinstance(c.args[0], Markdown)
        ]
        assert markdown_calls
        assert markdown_calls[0].markup == "I can run fold."

    def test_render_resumed_history_shows_generated_duration_from_trace_end(self, terminal):
        turn = MagicMock()
        turn.query = "run fold"
        turn.answer = "done"
        terminal._run_lock = MagicMock()
        terminal._run_lock.__enter__ = MagicMock(return_value=None)
        terminal._run_lock.__exit__ = MagicMock(return_value=False)
        terminal._session_sdk_turn_rows = [{"input_tokens": 49652, "output_tokens": 524}]
        with patch.object(
            terminal,
            "_load_trace_blocks",
            return_value=[{"events": [{"type": "text", "content": "ok"}], "end": {"duration_s": 24.0}}],
        ), patch.object(terminal, "_replay_trace_events", return_value=True):
            terminal._render_resumed_history(40, [turn])
        printed = " ".join(str(c) for c in terminal.console.print.call_args_list)
        assert "Generated for 24s" in printed
        assert "↑ 49,652 ↓ 524" in printed

    def test_restore_usage_from_trajectory(self, terminal):
        terminal.agent = MagicMock()
        terminal.agent.trajectory.get_usage_data.return_value = {
            "sdk_calls": 3,
            "sdk_input_tokens": 1000,
            "sdk_output_tokens": 400,
            "sdk_cache_read_tokens": 20,
            "sdk_cache_creation_tokens": 10,
            "sdk_cost_usd": 0.12,
            "sdk_total_cost_usd": 0.15,
            "sdk_extra_server_tool_cost_usd": 0.03,
            "sdk_models": ["gpt-5.5"],
            "sdk_turn_rows": [{"turn": 1, "input_tokens": 200}],
        }
        terminal._run_lock = MagicMock()
        terminal._run_lock.__enter__ = MagicMock(return_value=None)
        terminal._run_lock.__exit__ = MagicMock(return_value=False)
        terminal._restore_usage_from_trajectory()
        assert terminal._session_sdk_calls == 3
        assert terminal._session_sdk_input_tokens == 1000
        assert terminal._session_sdk_output_tokens == 400
        assert terminal._session_sdk_models == {"gpt-5.5"}

    def test_run_upgrade_uses_shared_cli_upgrade_flow(self, terminal):
        with patch("cli.execute_upgrade", return_value=True) as mock_exec:
            terminal._run_upgrade()
        mock_exec.assert_called_once_with(console_obj=terminal.console, cfg=terminal.session.config)

    def test_run_routes_commands_and_queries(self, terminal):
        terminal.console.width = 80
        terminal._prompt_session = MagicMock()
        terminal._prompt_session.prompt.side_effect = [
            "/ help",
            "/interrupt --force",
            "/skills-add owner/repo@skills/x",
            "/skills-find kinase",
            "/skills-remove x",
            "/skills",
            "/model",
            "/settings",
            "/plan",
            "/usage",
            "/tasks refresh",
            "/upgrade",
            "/copy",
            "/export out.md",
            "/notebook out.ipynb",
            "/compact concise summary",
            "/new",
            "/sessions",
            "/resume abc",
            "/agents 2 profile crbn",
            "/case-study list",
            "!echo hello",
            "continue",
            "find degraders",
            "/quit",
        ]
        terminal._current_placeholder = MagicMock(return_value="placeholder")
        terminal._has_active_query = MagicMock(return_value=False)
        terminal._advance_suggestion = MagicMock()
        terminal._request_interrupt = MagicMock(return_value=True)
        terminal._print_exit_with_resume_hint = MagicMock()
        terminal._show_help = MagicMock()
        terminal._add_skill = MagicMock()
        terminal._find_skills = MagicMock()
        terminal._remove_skill = MagicMock()
        terminal._show_skills = MagicMock()
        terminal._switch_model = MagicMock()
        terminal._change_settings = MagicMock()
        terminal._toggle_plan_mode = MagicMock()
        terminal._show_usage = MagicMock()
        terminal._show_tasks = MagicMock()
        terminal._run_upgrade = MagicMock()
        terminal._copy_last_response = MagicMock()
        terminal._export_session = MagicMock()
        terminal._export_notebook = MagicMock()
        terminal._compact_context = MagicMock()
        terminal._new_session = MagicMock()
        terminal._list_sessions = MagicMock()
        terminal._resume_session = MagicMock()
        terminal._handle_agents_command = MagicMock()
        terminal._handle_case_study_command = MagicMock()
        terminal._run_shell = MagicMock()
        terminal._submit_query = MagicMock()
        terminal.agent = MagicMock()
        terminal.agent._last_plan = None
        terminal.session.config.get.side_effect = lambda key, default=None: default

        fake_loop = MagicMock()
        with patch("ui.terminal.patch_stdout"), patch("agent.loop.AgentLoop", return_value=fake_loop):
            terminal.run(initial_context={"source": "test"})

        terminal._show_help.assert_called_once()
        terminal._request_interrupt.assert_called_once_with(force=True)
        terminal._add_skill.assert_called_once_with("owner/repo@skills/x")
        terminal._find_skills.assert_called_once_with("kinase")
        terminal._remove_skill.assert_called_once_with("x")
        terminal._show_skills.assert_called_once()
        terminal._switch_model.assert_called_once()
        terminal._change_settings.assert_called_once()
        terminal._toggle_plan_mode.assert_called_once()
        terminal._show_usage.assert_called_once()
        terminal._show_tasks.assert_called_once_with(force_refresh=True)
        terminal._run_upgrade.assert_called_once()
        terminal._copy_last_response.assert_called_once()
        terminal._export_session.assert_called_once_with("out.md")
        terminal._export_notebook.assert_called_once_with("out.ipynb")
        terminal._compact_context.assert_called_once_with("concise summary")
        terminal._new_session.assert_called_once()
        terminal._list_sessions.assert_called_once()
        terminal._resume_session.assert_called_once_with("abc")
        terminal._handle_agents_command.assert_called_once_with("/agents 2 profile crbn", {"source": "test"})
        terminal._handle_case_study_command.assert_called_once_with("/case-study list", {"source": "test"})
        terminal._run_shell.assert_called_once_with("echo hello")
        assert terminal._submit_query.call_count == 1
        terminal._print_exit_with_resume_hint.assert_called_once()

    def test_run_blocks_settings_commands_when_busy(self, terminal):
        terminal.console.width = 80
        terminal._prompt_session = MagicMock()
        terminal._prompt_session.prompt.side_effect = ["/model", "/quit"]
        terminal._current_placeholder = MagicMock(return_value="placeholder")
        terminal._has_active_query = MagicMock(return_value=True)
        terminal._advance_suggestion = MagicMock()
        terminal._request_interrupt = MagicMock(return_value=True)
        terminal._print_exit_with_resume_hint = MagicMock()
        terminal._switch_model = MagicMock()
        terminal.session.config.get.side_effect = lambda key, default=None: default

        fake_loop = MagicMock()
        with patch("ui.terminal.patch_stdout"), patch("agent.loop.AgentLoop", return_value=fake_loop):
            terminal.run()

        terminal._switch_model.assert_not_called()
        terminal._request_interrupt.assert_called_once_with(force=True)
        terminal._print_exit_with_resume_hint.assert_called_once()

    def test_handle_keys_command_set_boltz_updates_key(self, terminal, monkeypatch):
        cfg = MagicMock()
        cfg.get.return_value = None
        cfg.keys_table.return_value = Table(title="API Keys")
        terminal.session.config = cfg
        terminal._secret_prompt_session = MagicMock()
        terminal._plain_prompt_session = MagicMock()
        terminal._secret_prompt_session.prompt.return_value = "sk_bc_local_test_key"
        terminal._plain_prompt_session.prompt.side_effect = ["n", "n"]
        terminal._install_boltz_skill = MagicMock()
        terminal._ensure_boltz_cli_ready = MagicMock()
        monkeypatch.delenv("BOLTZ_API_KEY", raising=False)

        terminal._handle_keys_command("/keys set-boltz")

        cfg.set.assert_called_once_with("api.boltz_api_key", "sk_bc_local_test_key")
        cfg.save.assert_called_once()
        terminal._install_boltz_skill.assert_not_called()
        terminal._ensure_boltz_cli_ready.assert_not_called()

    def test_handle_keys_command_set_boltz_can_clear_key(self, terminal, monkeypatch):
        cfg = MagicMock()
        cfg.get.return_value = "sk_bc_existing"
        cfg.keys_table.return_value = Table(title="API Keys")
        terminal.session.config = cfg
        terminal._secret_prompt_session = MagicMock()
        terminal._plain_prompt_session = MagicMock()
        terminal._secret_prompt_session.prompt.return_value = ""
        terminal._install_boltz_skill = MagicMock()
        terminal._ensure_boltz_cli_ready = MagicMock()
        monkeypatch.setenv("BOLTZ_API_KEY", "sk_bc_existing")

        terminal._handle_keys_command("/keys set-boltz")

        cfg.unset.assert_called_once_with("api.boltz_api_key")
        cfg.save.assert_called_once()
        terminal._install_boltz_skill.assert_not_called()
        terminal._ensure_boltz_cli_ready.assert_not_called()

    def test_run_resume_last_renders_history(self, terminal):
        terminal.console.width = 80
        terminal._prompt_session = MagicMock()
        terminal._prompt_session.prompt.side_effect = ["/quit"]
        terminal._current_placeholder = MagicMock(return_value="placeholder")
        terminal._has_active_query = MagicMock(return_value=False)
        terminal._print_exit_with_resume_hint = MagicMock()
        terminal._restore_usage_from_trajectory = MagicMock()
        terminal._render_resumed_history = MagicMock()
        terminal.session.config.get.side_effect = lambda key, default=None: default

        resumed = MagicMock()
        resumed.trajectory.turns = [MagicMock()]
        resumed.trajectory.title = "Session title"
        resumed.trajectory.session_id = "abc12345"
        with patch("ui.terminal.patch_stdout"), patch("agent.loop.AgentLoop.resume_latest", return_value=resumed):
            terminal.run(resume_id="last")

        terminal._restore_usage_from_trajectory.assert_called_once()
        terminal._render_resumed_history.assert_called_once()
        terminal._print_exit_with_resume_hint.assert_called_once()

    def test_run_with_clarification_collects_answer_and_retries(self, terminal):
        from agent.loop import Clarification, ClarificationNeeded

        terminal._ensure_llm_ready_for_query = MagicMock(return_value=True)
        terminal._prompt_session = MagicMock()
        terminal._prompt_session.prompt.return_value = "CRBN"
        result = MagicMock()
        clar = Clarification(question="Which target?", missing=["target"], suggestions=["CRBN"])
        terminal.agent = MagicMock()
        terminal.agent.run.side_effect = [ClarificationNeeded(clar), result]

        output = terminal._run_with_clarification("study @depmap signals", {"foo": "bar"})

        assert output is result
        assert terminal.agent.run.call_count == 2
        _, second_kwargs = terminal.agent.run.call_args_list[1]
        assert second_kwargs["progress_callback"] is None
        assert "target" in terminal.agent.run.call_args_list[1].args[1]

    def test_run_with_clarification_cancelled_returns_none(self, terminal):
        from agent.loop import Clarification, ClarificationNeeded

        terminal._ensure_llm_ready_for_query = MagicMock(return_value=True)
        terminal._prompt_session = MagicMock()
        terminal._prompt_session.prompt.return_value = ""
        clar = Clarification(question="Need more details", missing=["target"])
        terminal.agent = MagicMock()
        terminal.agent.run.side_effect = ClarificationNeeded(clar)

        assert terminal._run_with_clarification("study target", {}) is None


class TestExtractMentions:
    """Tests for extract_mentions() — parsing @ tokens from query text."""

    def test_tool_mention(self):
        query, tools, datasets, workflows = extract_mentions("analyze CRBN with @target.coessentiality")
        assert "target.coessentiality" in tools
        assert datasets == []
        assert workflows == []
        assert "@" not in query

    def test_dataset_mention(self):
        query, tools, datasets, workflows = extract_mentions("check sensitivity in @depmap @prism")
        assert set(datasets) == {"depmap", "prism"}
        assert "@" not in query

    def test_mixed_mentions(self):
        query, tools, datasets, workflows = extract_mentions(
            "@depmap find @target.coessentiality for CRBN"
        )
        assert "target.coessentiality" in tools
        assert "depmap" in datasets
        assert "CRBN" in query

    def test_no_mentions(self):
        query, tools, datasets, workflows = extract_mentions("analyze CRBN degradation")
        assert query == "analyze CRBN degradation"
        assert tools == []
        assert datasets == []
        assert workflows == []

    def test_workflow_mention(self):
        query, tools, datasets, workflows = extract_mentions("run @target_validation on KRAS")
        assert "target_validation" in workflows
        assert tools == []
        assert datasets == []
        assert "KRAS" in query

    def test_mixed_with_workflow(self):
        query, tools, datasets, workflows = extract_mentions(
            "@depmap @target_validation check CRBN"
        )
        assert "depmap" in datasets
        assert "target_validation" in workflows
        assert "CRBN" in query


class TestBuildMentionContext:
    """Tests for build_mention_context() — formatting planner instructions."""

    def test_tools_only(self):
        ctx = build_mention_context(["target.coessentiality"], [])
        assert "target.coessentiality" in ctx
        assert "tool" in ctx.lower()

    def test_datasets_only(self):
        ctx = build_mention_context([], ["depmap", "prism"])
        assert "depmap" in ctx
        assert "prism" in ctx

    def test_empty(self):
        ctx = build_mention_context([], [])
        assert ctx == ""

    def test_workflow(self):
        ctx = build_mention_context([], [], ["target_validation"])
        assert "target_validation" in ctx
        assert "workflow" in ctx.lower()

    def test_mixed_with_workflow(self):
        ctx = build_mention_context(["target.coessentiality"], ["depmap"], ["compound_safety"])
        assert "target.coessentiality" in ctx
        assert "depmap" in ctx
        assert "compound_safety" in ctx


class TestMentionCompleterTabs:
    """Tests for MentionCompleter tabbed filtering."""

    @pytest.fixture
    def candidates(self):
        return [
            ("target.coessentiality", "target", "Co-essential gene networks", "tool"),
            ("expression.pathway_enrichment", "expression", "Pathway enrichment analysis", "tool"),
            ("depmap", "dataset", "DepMap CRISPR/model data", "dataset"),
            ("prism", "dataset", "PRISM drug sensitivity", "dataset"),
            ("CRISPRGeneEffect.csv", "file", "depmap/CRISPRGeneEffect.csv", "file"),
            ("target_validation", "workflow", "Validate a potential drug target (5 steps)", "workflow"),
        ]

    @pytest.fixture
    def completer(self, candidates):
        return MentionCompleter(candidates)

    def _get_completions(self, completer, text):
        doc = Document(text, len(text))
        return list(completer.get_completions(doc, CompleteEvent()))

    def test_all_tab_shows_everything(self, completer):
        completer._active_tab = 0
        completions = self._get_completions(completer, "@")
        assert len(completions) == 6

    def test_tools_tab_filters(self, completer):
        completer._active_tab = 1
        completions = self._get_completions(completer, "@")
        assert len(completions) == 2
        assert all("tool" in c.style for c in completions)

    def test_db_tab_filters(self, completer):
        completer._active_tab = 2
        completions = self._get_completions(completer, "@")
        assert len(completions) == 2
        names = {c.text for c in completions}
        assert names == {"@depmap", "@prism"}

    def test_files_tab_filters(self, completer):
        completer._active_tab = 3
        completions = self._get_completions(completer, "@")
        assert len(completions) == 1
        assert completions[0].text == "@CRISPRGeneEffect.csv"

    def test_flows_tab_filters(self, completer):
        completer._active_tab = 4  # Flows
        completions = self._get_completions(completer, "@")
        assert len(completions) == 1
        assert completions[0].text == "@target_validation"
        assert "workflow" in completions[0].style

    def test_substring_match(self, completer):
        completions = self._get_completions(completer, "@coess")
        assert len(completions) == 1
        assert completions[0].text == "@target.coessentiality"

    def test_no_at_returns_nothing(self, completer):
        completions = self._get_completions(completer, "hello world")
        assert len(completions) == 0


class TestMergedCompleterDispatch:
    """Tests for MergedCompleter dispatch logic."""

    @pytest.fixture
    def merged(self):
        candidates = [("depmap", "dataset", "DepMap data", "dataset")]
        return MergedCompleter(SlashCompleter(), MentionCompleter(candidates))

    def _get_completions(self, completer, text):
        doc = Document(text, len(text))
        return list(completer.get_completions(doc, CompleteEvent()))

    def test_slash_routes_to_slash(self, merged):
        completions = self._get_completions(merged, "/he")
        assert any(c.text == "/help" for c in completions)

    def test_at_routes_to_mention(self, merged):
        completions = self._get_completions(merged, "query @dep")
        assert any("depmap" in c.display_text for c in completions)

    def test_no_trigger_yields_nothing(self, merged):
        completions = self._get_completions(merged, "analyze compound")
        assert len(completions) == 0


class TestSkillsUpgradeTerminalPaths:
    def _make_terminal(self):
        with patch("ui.terminal.InteractiveTerminal.__init__", return_value=None):
            terminal = InteractiveTerminal.__new__(InteractiveTerminal)
        terminal.session = MagicMock()
        terminal.session.verbose = False
        terminal.session.current_model = "claude-sonnet-4-5-20250929"
        terminal.session.config = MagicMock()
        terminal.session.config.get.side_effect = lambda key, default=None: default
        terminal.console = MagicMock()
        terminal.console.width = 80
        terminal._current_placeholder = MagicMock(return_value="placeholder")
        terminal._has_active_query = MagicMock(return_value=False)
        terminal._advance_suggestion = MagicMock()
        terminal._request_interrupt = MagicMock(return_value=True)
        terminal._print_exit_with_resume_hint = MagicMock()
        return terminal

    def test_run_routes_skills_upgrade_command(self):
        terminal = self._make_terminal()
        terminal._prompt_session = MagicMock()
        terminal._prompt_session.prompt.side_effect = ["/skills-upgrade", "/quit"]
        terminal._upgrade_skills = MagicMock()

        fake_loop = MagicMock()
        with patch("ui.terminal.patch_stdout"), patch(
            "agent.loop.AgentLoop", return_value=fake_loop
        ):
            terminal.run()

        terminal._upgrade_skills.assert_called_once()

    def test_send_export_to_slack_success_payload(self, monkeypatch):
        terminal = self._make_terminal()
        status_cm = MagicMock()
        status_cm.__enter__.return_value = None
        status_cm.__exit__.return_value = False
        terminal.console.status.return_value = status_cm

        cfg = MagicMock()
        cfg.get.return_value = "cfg-key"
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
        monkeypatch.delenv("FASTFOLD_API_KEY", raising=False)

        response = MagicMock()
        response.read.return_value = b'{"ok": true, "channel_id": "C123"}'
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        with patch("urllib.request.urlopen", return_value=response) as mock_urlopen:
            result = terminal._send_export_to_slack("# report", "report.md")

        assert result["ok"] is True
        assert result["channel_id"] == "C123"
        mock_urlopen.assert_called_once()

    def test_upgrade_skills_prints_updated_npx_and_failed_sections(self):
        terminal = self._make_terminal()
        status_cm = MagicMock()
        status_cm.__enter__.return_value = status_cm
        status_cm.__exit__.return_value = False
        terminal.console.status.return_value = status_cm

        result = {
            "added": ["fold"],
            "updated": ["md_openmmdl"],
            "npx_synced": 2,
            "failed": [("bad/source", "network error")],
            "summary": "Sync complete",
        }
        with patch("agent.skills.upgrade_skills", return_value=result), patch(
            "agent.skills.GLOBAL_SKILLS_DIR", Path("/tmp/skills")
        ):
            terminal._upgrade_skills()

        rendered = "\n".join(
            str(call.args[0]) for call in terminal.console.print.call_args_list if call.args
        )
        assert "Updated:" in rendered
        assert "npx-synced:" in rendered
        assert "Failed:" in rendered
        assert "Available on your next message" in rendered
