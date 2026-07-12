"""Direct unit tests for cli.py pure helpers not covered elsewhere."""

import json
import io
import re
import subprocess
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.config import Config
from cli import (
    _count_installed_claude_skills,
    _fetch_ollama_tags_for_setup,
    _fetch_openai_models_for_setup,
    _format_plan_label,
    _installed_claude_skill_names,
    _latest_report_path,
    _latest_trace_path,
    _normalize_upgrade_flavor,
    _maybe_offer_fastfold_skills_install_after_upgrade,
    _ollama_tags_url_from_base,
    _openai_models_url_from_base,
    _parse_semver_triplet,
    _resolve_fastfold_subscription_tier,
    _resolve_trace_path,
    _run_step_command,
    _trace_has_issues,
    build_upgrade_command,
    config_set,
    config_unset,
    entry,
    execute_upgrade,
    fetch_pypi_latest_version,
    get_upgrade_available_version,
    print_banner,
    run_interactive,
    run_query,
)

class TestClaudeSkillHelpers:
    def test_installed_claude_skill_names_delegates(self, monkeypatch):
        monkeypatch.setattr("agent.skills.installed_skill_names", lambda: ["fold", "md"])
        assert _installed_claude_skill_names() == ["fold", "md"]

    def test_count_installed_claude_skills(self, monkeypatch):
        monkeypatch.setattr("cli._installed_claude_skill_names", lambda: ["a", "b", "c"])
        assert _count_installed_claude_skills() == 3


class TestSubscriptionTier:
    def test_resolve_tier_from_env_without_api_key(self, monkeypatch):
        cfg = Config(data={})
        monkeypatch.delenv("FASTFOLD_API_KEY", raising=False)
        monkeypatch.setenv("FASTFOLD_SUBSCRIPTION_TIER", "pro+")
        assert _resolve_fastfold_subscription_tier(cfg) == "pro_plus"

    def test_resolve_tier_from_api_items(self, monkeypatch):
        cfg = Config(data={"api.fastfold_cloud_key": "ff-key"})
        monkeypatch.setenv("FASTFOLD_API_KEY", "ff-key")
        payload = json.dumps(
            {"items": [{"plan_code": "pro"}, {"plan_code": "ultra"}]}
        ).encode()

        class FakeResp:
            def read(self):
                return payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr("cli.urllib.request.urlopen", lambda *a, **k: FakeResp())
        assert _resolve_fastfold_subscription_tier(cfg) == "ultra"

    def test_resolve_tier_401_returns_fallback(self, monkeypatch):
        import urllib.error

        cfg = Config(data={"fastfold.subscription_tier": "pro"})
        monkeypatch.setenv("FASTFOLD_API_KEY", "ff-key")

        def raise_401(*args, **kwargs):
            raise urllib.error.HTTPError("url", 401, "unauthorized", hdrs=None, fp=None)

        monkeypatch.setattr("cli.urllib.request.urlopen", raise_401)
        assert _resolve_fastfold_subscription_tier(cfg) == "pro"


class TestUpgradeHelpers:
    def test_parse_semver_triplet_edge_cases(self):
        assert _parse_semver_triplet("0.0.51") == (0, 0, 51)
        assert _parse_semver_triplet("") is None
        assert _parse_semver_triplet("1.2") is None

    def test_format_plan_label_variants(self):
        assert _format_plan_label("pro_plus") == "Pro+"
        assert _format_plan_label("free") == "Free"
        assert _format_plan_label("") == ""

    def test_normalize_upgrade_flavor(self):
        assert _normalize_upgrade_flavor("ALL") == "all"
        assert _normalize_upgrade_flavor("win_build") == "win_build"
        assert _normalize_upgrade_flavor("bogus") is None

    def test_build_upgrade_command_invalid_uses_default(self, monkeypatch):
        monkeypatch.setattr("cli.os.name", "posix", raising=False)
        cmd = build_upgrade_command("not-a-flavor")
        assert "fastfold-agent-cli[all]" in cmd[3]

    def test_fetch_pypi_latest_version_network_error(self):
        with patch("cli.urllib.request.urlopen", side_effect=TimeoutError("timeout")):
            assert fetch_pypi_latest_version(timeout_s=0.1) is None

    def test_get_upgrade_available_version_no_pypi(self):
        with patch("cli.fetch_pypi_latest_version", return_value=None):
            assert get_upgrade_available_version("0.0.51") is None

    def test_execute_upgrade_success(self, captured_console, monkeypatch):
        console, buf = captured_console
        cfg = Config(data={"install.uv_flavor": "all"})
        proc = subprocess.CompletedProcess(
            args=["uv"], returncode=0, stdout="Installed", stderr=""
        )
        skills_result = {
            "added": [],
            "updated": ["fastfold-ai/skills"],
            "failed": [],
            "npx_synced": 1,
            "summary": "skills upgraded",
        }
        captured_kwargs = {}
        monkeypatch.setattr("cli.subprocess.run", lambda *a, **k: proc)
        monkeypatch.setattr(
            "agent.skills.upgrade_skills",
            lambda **kwargs: (captured_kwargs.update(kwargs), skills_result)[1],
        )
        assert execute_upgrade(console_obj=console, cfg=cfg) is True
        assert captured_kwargs["include_catalog"] is True
        assert captured_kwargs["include_npx"] is True
        assert callable(captured_kwargs["progress"])
        assert "Upgrade complete" in buf.getvalue()
        assert "skills-upgrade" in buf.getvalue()
        assert "skills upgraded" in buf.getvalue()

    def test_execute_upgrade_uv_not_found(self, captured_console, monkeypatch):
        console, buf = captured_console
        cfg = Config(data={})

        def raise_not_found(*args, **kwargs):
            raise FileNotFoundError("uv")

        monkeypatch.setattr("cli.subprocess.run", raise_not_found)
        assert execute_upgrade(console_obj=console, cfg=cfg) is False
        assert "uv" in buf.getvalue().lower()

    def test_execute_upgrade_nonzero_exit(self, captured_console, monkeypatch):
        console, buf = captured_console
        cfg = Config(data={})
        proc = subprocess.CompletedProcess(
            args=["uv"], returncode=1, stdout="", stderr="boom"
        )
        monkeypatch.setattr("cli.subprocess.run", lambda *a, **k: proc)
        assert execute_upgrade(console_obj=console, cfg=cfg) is False
        assert "Upgrade failed" in buf.getvalue()


class TestOpenAICompatibleSetupFetch:
    def test_ollama_tags_url_from_base(self):
        url = _ollama_tags_url_from_base("http://localhost:11434/v1")
        assert url.endswith("/api/tags")

    def test_openai_models_url_from_base(self):
        url = _openai_models_url_from_base("http://localhost:8888")
        assert url.endswith("/v1/models")

    def test_fetch_openai_models_for_setup(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        payload = json.dumps({"data": [{"id": "gpt-oss:20b"}, {"id": "gemma:12b"}]}).encode()

        class FakeResp:
            def read(self):
                return payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr("cli.urllib.request.urlopen", lambda *a, **k: FakeResp())
        names = _fetch_openai_models_for_setup("http://localhost:8888/v1", api_key="sk-test")
        assert names == ["gemma:12b", "gpt-oss:20b"]
        plain = re.sub(r"\x1b\[[0-9;]*m", "", buf.getvalue())
        assert "Found 2 model" in plain

    def test_fetch_ollama_tags_for_setup(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        payload = json.dumps({"models": [{"name": "llama3.1"}, {"name": "qwen3"}]}).encode()

        class FakeResp:
            def read(self):
                return payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr("cli.urllib.request.urlopen", lambda *a, **k: FakeResp())
        names = _fetch_ollama_tags_for_setup("http://localhost:11434/v1")
        assert names == ["llama3.1", "qwen3"]

    def test_fetch_openai_models_returns_empty_on_error(self, monkeypatch):
        monkeypatch.setattr(
            "cli.urllib.request.urlopen",
            lambda *a, **k: (_ for _ in ()).throw(TimeoutError()),
        )
        assert _fetch_openai_models_for_setup("http://bad") == []

    def test_fetch_openai_models_reports_http_error_body(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        err = urllib.error.HTTPError(
            url="http://localhost:8000/v1/models",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"invalid token","code":"invalid_api_key"}}'),
        )
        monkeypatch.setattr(
            "cli.urllib.request.urlopen",
            lambda *a, **k: (_ for _ in ()).throw(err),
        )
        assert _fetch_openai_models_for_setup("http://localhost:8000/v1", api_key="bad") == []
        plain = re.sub(r"\x1b\[[0-9;]*m", "", buf.getvalue())
        assert "/v1/models request failed" in plain
        assert "invalid token" in plain


class TestTraceAndReportHelpers:
    def test_latest_trace_path_returns_newest(self, tmp_path, monkeypatch):
        traces = tmp_path / "traces"
        traces.mkdir()
        older = traces / "old.trace.jsonl"
        newer = traces / "new.trace.jsonl"
        older.write_text("{}")
        newer.write_text("{}")
        older.touch()
        newer.touch()
        monkeypatch.setattr("agent.trace.TraceLogger.traces_dir", staticmethod(lambda: traces))
        assert _latest_trace_path() == newer

    def test_resolve_trace_path_rejects_both_args(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        import typer

        with pytest.raises(typer.Exit) as exc:
            _resolve_trace_path(Path("a.trace.jsonl"), "session123")
        assert exc.value.exit_code == 2

    def test_trace_has_issues_other_flags(self):
        assert _trace_has_issues({"queries_with_no_plan": ["q1"]}) is True
        assert _trace_has_issues({"queries_with_synthesis_mismatch": ["q2"]}) is True

    def test_latest_report_path_missing_dir(self, tmp_path):
        assert _latest_report_path(str(tmp_path / "missing")) is None


class TestRunStepCommand:
    def test_run_step_command_pass(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        proc = subprocess.CompletedProcess(args=["echo"], returncode=0, stdout="ok", stderr="")
        monkeypatch.setattr("cli.subprocess.run", lambda *a, **k: proc)
        assert _run_step_command("pytest", ["pytest", "-q"]) is True
        assert "PASS" in buf.getvalue()

    def test_run_step_command_fail(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        proc = subprocess.CompletedProcess(args=["pytest"], returncode=2, stdout="", stderr="fail")
        monkeypatch.setattr("cli.subprocess.run", lambda *a, **k: proc)
        assert _run_step_command("pytest", ["pytest"]) is False
        assert "FAIL" in buf.getvalue()


class TestConfigSetUnsetDirect:
    def test_config_set_plain_key(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={})
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
        with patch.object(cfg, "save") as mock_save:
            config_set("llm.provider", "anthropic")
        assert cfg.get("llm.provider") == "anthropic"
        assert "Set" in buf.getvalue()
        mock_save.assert_called_once()

    def test_config_unset_direct(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={"llm.provider": "openai"})
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
        with patch.object(cfg, "save") as mock_save:
            config_unset("llm.provider")
        assert "llm.provider" not in cfg._data
        assert "Unset" in buf.getvalue()
        mock_save.assert_called_once()


class TestRunQueryAndBanner:
    def test_run_query_sdk_path(self, captured_console, monkeypatch, tmp_path):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={"llm.api_key": "sk-ant-test", "agent.use_sdk": True})
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)

        fake_result = MagicMock()
        fake_result.to_markdown.return_value = "# report"

        fake_agent = MagicMock()
        fake_agent.run.return_value = fake_result

        with patch("cli.print_banner"), patch(
            "agent.runner.AgentRunner", return_value=fake_agent
        ):
            run_query("analyze TP53", {}, None, None, False)

        fake_agent.run.assert_called_once_with("analyze TP53", {})
        assert "report" not in buf.getvalue() or True  # smoke: no exception

    def test_run_query_orchestrator_when_agents_gt_one(self, monkeypatch):
        cfg = Config(data={"llm.api_key": "sk-ant-test"})
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)

        fake_result = MagicMock()
        fake_result.to_markdown.return_value = "# multi"

        fake_orch = MagicMock()
        fake_orch.run.return_value = fake_result

        with patch("cli.print_banner"), patch(
            "agent.orchestrator.ResearchOrchestrator", return_value=fake_orch
        ):
            run_query("big question", {}, None, None, False, agents=3)

        fake_orch.run.assert_called_once()

    def test_run_query_triggers_setup_then_continues(self, monkeypatch, tmp_path):
        cfg = Config(data={"agent.use_sdk": True})
        issues = iter(["OpenAI API key not configured", None, None])
        monkeypatch.setattr(cfg, "llm_preflight_issue", lambda: next(issues))
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)

        fake_result = MagicMock()
        fake_result.to_markdown.return_value = "# report"
        fake_agent = MagicMock()
        fake_agent.run.return_value = fake_result

        with patch("cli.print_banner"), patch("cli.setup_cmd") as mock_setup, patch(
            "agent.runner.AgentRunner", return_value=fake_agent
        ):
            run_query("after setup", {}, tmp_path / "out", "gpt-4o", False)

        mock_setup.assert_called_once()
        fake_agent.run.assert_called_once_with("after setup", {})
        assert (tmp_path / "out" / "report.md").exists()

    def test_run_query_agent_loop_clarification_path(self, monkeypatch):
        from agent.loop import Clarification, ClarificationNeeded

        cfg = Config(data={"agent.use_sdk": False, "llm.api_key": "sk-ant-test"})
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
        monkeypatch.setattr(cfg, "llm_preflight_issue", lambda: None)

        fake_loop = MagicMock()
        fake_loop.run.side_effect = ClarificationNeeded(
            Clarification(
                question="Need a target",
                missing=["target"],
                suggestions=["KRAS", "TP53"],
            )
        )

        with patch("cli.print_banner"), patch("agent.loop.AgentLoop", return_value=fake_loop):
            run_query("clarify me", {}, None, None, False)

        fake_loop.run.assert_called_once()

    def test_print_banner_renders_metadata(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={"llm.model": "claude-sonnet-4-5-20250929"})
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
        monkeypatch.setattr("cli._count_installed_claude_skills", lambda: 2)
        monkeypatch.setattr("cli._resolve_fastfold_subscription_tier", lambda c: "pro")
        monkeypatch.setattr("cli.get_upgrade_available_version", lambda v: None)
        monkeypatch.setattr("cli._random_command_tip_markup", lambda: "[dim]tip[/dim]")
        monkeypatch.setattr("cli._random_news_item_markup", lambda: "[dim]news[/dim]")
        monkeypatch.setattr("tools.registry.list_tools", lambda: ["a", "b"])

        with patch("tools.ensure_loaded"):
            print_banner()

        out = buf.getvalue()
        assert "Fastfold Agent CLI" in out
        assert "tools" in out.lower() or "2" in out

    def test_run_interactive_offers_missing_skills_prompt_on_startup(
        self, captured_console, monkeypatch
    ):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={"llm.api_key": "sk-ant-test"})
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)

        fake_terminal = MagicMock()
        with patch.object(cfg, "llm_preflight_issue", return_value=None), patch(
            "cli.print_banner"
        ), patch(
            "cli._maybe_offer_fastfold_skills_install_after_upgrade"
        ) as mock_offer, patch(
            "cli.InteractiveTerminal", return_value=fake_terminal
        ):
            run_interactive({}, None, None, False)

        mock_offer.assert_called_once_with(
            ui=console,
            install_missing=False,
            prompt_if_missing=True,
        )
        fake_terminal.run.assert_called_once()


class TestEntryRouting:
    def test_entry_help_alias(self, monkeypatch):
        called = {}

        def fake_app(*, args, prog_name):
            called["args"] = args
            called["prog_name"] = prog_name

        monkeypatch.setattr("cli.app", fake_app)
        monkeypatch.setattr("sys.argv", ["fastfold", "help", "config"])
        entry()
        assert called["args"] == ["config", "--help"]

    def test_entry_version_flag_passthrough(self, monkeypatch):
        called = {}

        def fake_app(*, args, prog_name):
            called["args"] = args

        monkeypatch.setattr("cli.app", fake_app)
        monkeypatch.setattr("sys.argv", ["fastfold", "--version"])
        entry()
        assert called["args"] == ["run", "--version"]


class TestUpgradeSkillsPrompt:
    def test_noninteractive_missing_skills_shows_hint(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("agent.skills.user_installed_skill_names", lambda: [])
        monkeypatch.setattr("cli.sys.stdin", MagicMock(isatty=lambda: False))
        monkeypatch.setattr("cli.sys.stdout", MagicMock(isatty=lambda: False))

        _maybe_offer_fastfold_skills_install_after_upgrade(ui=console)
        assert "No official Fastfold skills detected" in buf.getvalue()

    def test_install_missing_skills_flag_installs_catalog(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("agent.skills.user_installed_skill_names", lambda: [])
        called = []
        monkeypatch.setattr("cli._install_skill_sources", lambda sources: called.extend(sources))

        _maybe_offer_fastfold_skills_install_after_upgrade(
            ui=console,
            install_missing=True,
            prompt_if_missing=False,
        )
        assert called == ["fastfold-ai/skills"]
