"""Tests for CLI argument parsing and subcommand dispatch."""

import subprocess
from unittest.mock import ANY, patch

import pytest
from typer.testing import CliRunner

from agent.config import Config
from agent.trace import TraceLogger
from cli import (
    app,
    _parse_provider_list,
    _prompt_setup_providers,
    _is_openai_managed_base_url,
    _prompt_openai_endpoint_mode,
    _prompt_openai_compatible_backend,
    _prompt_compatible_model_for_setup,
    _resolve_openai_base_url,
    _resolve_openai_compatible_endpoint,
    _resolve_provider_key,
    _setup_provider_runtime_id,
    setup_cmd,
    resolve_upgrade_flavor,
    build_upgrade_command,
    is_newer_version,
    get_upgrade_available_version,
)


runner = CliRunner()


def test_parse_provider_list_single():
    assert _parse_provider_list("openai") == ["openai"]


def test_parse_provider_list_multiple_preserves_order():
    assert _parse_provider_list("openai,anthropic") == ["anthropic", "openai"]


def test_parse_provider_list_openai_compatible_alias():
    assert _parse_provider_list("compatible,openai") == ["openai", "openai_compatible"]


def test_parse_provider_list_invalid_raises():
    with pytest.raises(Exception):
        _parse_provider_list("bogus")


def test_prompt_setup_providers_inline_accepts_aliases(monkeypatch):
    monkeypatch.setattr("cli.sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("cli.sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("builtins.input", lambda _: "o a")
    selected = _prompt_setup_providers("openai")
    assert selected == ["anthropic", "openai"]


def test_prompt_setup_providers_inline_requires_explicit_selection(monkeypatch):
    monkeypatch.setattr("cli.sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("cli.sys.stdout.isatty", lambda: False)
    answers = iter(["", "o"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    selected = _prompt_setup_providers("openai")
    assert selected == ["openai"]


def test_prompt_setup_providers_interactive_arrow_space_mode(monkeypatch):
    captured = {}

    class _FakePrompt:
        def ask(self):
            return ["openai", "anthropic"]

    def _fake_checkbox(*args, **kwargs):
        captured["kwargs"] = kwargs
        return _FakePrompt()

    monkeypatch.setattr("cli.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("cli.sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("questionary.checkbox", _fake_checkbox)

    selected = _prompt_setup_providers("openai")
    assert selected == ["anthropic", "openai"]
    assert captured["kwargs"]["qmark"] == "❯"
    assert captured["kwargs"]["pointer"] == "▸"
    assert "space toggle" in captured["kwargs"]["instruction"]
    assert captured["kwargs"]["style"] is not None


def test_setup_cmd_direct_call_handles_typer_option_defaults(monkeypatch):
    cfg = Config(data={})
    monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
    monkeypatch.setattr("cli._prompt_setup_providers", lambda default: ["anthropic"])
    monkeypatch.setattr(
        "cli._resolve_provider_key",
        lambda cfg, provider, cli_key=None, openai_base_url=None, compatible_backend=None: "sk-ant-api03-test",
    )
    monkeypatch.setattr("cli._prompt_fastfold_cloud_api_key", lambda cfg, cli_key: None)
    monkeypatch.setattr("cli._prompt_boltz_api_key", lambda cfg, cli_key: None)

    setup_cmd()
    assert cfg.get("llm.provider") == "anthropic"
    assert cfg.get("llm.anthropic_api_key") == "sk-ant-api03-test"


def test_setup_cmd_openai_compatible_persists_backend(monkeypatch):
    cfg = Config(data={})
    monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
    monkeypatch.setattr("cli._prompt_setup_providers", lambda default: ["openai_compatible"])
    monkeypatch.setattr(
        "cli._resolve_openai_compatible_endpoint",
        lambda cfg, cli_base_url=None, cli_backend=None: ("http://localhost:8888/v1", "unsloth"),
    )
    monkeypatch.setattr(
        "cli._resolve_provider_key",
        lambda cfg, provider, cli_key=None, openai_base_url=None, compatible_backend=None: "sk-unsloth-test",
    )
    monkeypatch.setattr(
        "cli._prompt_compatible_model_for_setup",
        lambda cfg, base_url, backend, api_key=None: "gpt-oss:20b",
    )
    monkeypatch.setattr("cli._prompt_fastfold_cloud_api_key", lambda cfg, cli_key: None)
    monkeypatch.setattr("cli._prompt_boltz_api_key", lambda cfg, cli_key: None)
    monkeypatch.setattr("agent.doctor.run_checks", lambda cfg: [])
    monkeypatch.setattr("agent.doctor.to_table", lambda checks: "")
    monkeypatch.setattr("agent.doctor.has_errors", lambda checks: False)

    setup_cmd(provider="openai_compatible")
    assert cfg.get("llm.provider") == "openai"
    assert cfg.get("llm.openai_base_url") == "http://localhost:8888/v1"
    assert cfg.get("llm.openai_compatible_backend") == "unsloth"
    assert cfg.get("llm.openai_compatible_api_key") == "sk-unsloth-test"
    assert cfg.get("llm.model") == "gpt-oss:20b"


def test_setup_cmd_openai_compatible_model_prompt_can_override_key(monkeypatch):
    cfg = Config(data={})
    monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
    monkeypatch.setattr("cli._prompt_setup_providers", lambda default: ["openai_compatible"])
    monkeypatch.setattr(
        "cli._resolve_openai_compatible_endpoint",
        lambda cfg, cli_base_url=None, cli_backend=None: ("http://localhost:8000/v1", "omlx"),
    )
    monkeypatch.setattr(
        "cli._resolve_provider_key",
        lambda cfg, provider, cli_key=None, openai_base_url=None, compatible_backend=None: "stale-key",
    )
    monkeypatch.setattr(
        "cli._prompt_compatible_model_for_setup",
        lambda cfg, base_url, backend, api_key=None: ("omlx-model", "fresh-key"),
    )
    monkeypatch.setattr("cli._prompt_fastfold_cloud_api_key", lambda cfg, cli_key: None)
    monkeypatch.setattr("cli._prompt_boltz_api_key", lambda cfg, cli_key: None)
    monkeypatch.setattr("agent.doctor.run_checks", lambda cfg: [])
    monkeypatch.setattr("agent.doctor.to_table", lambda checks: "")
    monkeypatch.setattr("agent.doctor.has_errors", lambda checks: False)

    setup_cmd(provider="openai_compatible")

    assert cfg.get("llm.openai_compatible_backend") == "omlx"
    assert cfg.get("llm.openai_compatible_api_key") == "fresh-key"
    assert cfg.get("llm.model") == "omlx-model"


def test_is_openai_managed_base_url_detects_hosts():
    assert _is_openai_managed_base_url("https://api.openai.com/v1") is True
    assert _is_openai_managed_base_url("https://gateway.openai.com/v1") is True
    assert _is_openai_managed_base_url("http://localhost:11434/v1") is False
    assert _is_openai_managed_base_url("http://ai-server.tailnet:11434/v1") is False


def test_resolve_openai_base_url_cli_custom():
    cfg = Config(data={})
    assert _resolve_openai_base_url(cfg, cli_base_url="http://localhost:11434/v1") == "http://localhost:11434/v1"


def test_resolve_openai_base_url_cli_openai_default_returns_none():
    cfg = Config(data={})
    assert _resolve_openai_base_url(cfg, cli_base_url="https://api.openai.com/v1") is None


def test_prompt_openai_endpoint_mode_fallback_compatible(monkeypatch):
    monkeypatch.setattr("cli.sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("cli.sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("builtins.input", lambda _: "k")
    assert _prompt_openai_endpoint_mode(default_mode="cloud") == "compatible"


def test_prompt_openai_compatible_backend_unsloth(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "u")
    assert _prompt_openai_compatible_backend(default_backend="ollama") == "unsloth"


def test_prompt_openai_compatible_backend_numeric_selection(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "2")
    assert _prompt_openai_compatible_backend(default_backend="ollama") == "unsloth"


def test_resolve_openai_base_url_interactive_cloud_mode_returns_none(monkeypatch):
    cfg = Config(data={})
    monkeypatch.setattr("cli._prompt_openai_endpoint_mode", lambda default_mode="cloud": "cloud")
    assert _resolve_openai_base_url(cfg, cli_base_url=None) is None


def test_resolve_openai_compatible_endpoint_unsloth_default(monkeypatch):
    cfg = Config(data={})
    monkeypatch.setattr("cli._prompt_openai_compatible_backend", lambda default_backend="ollama": "unsloth")
    monkeypatch.setattr("builtins.input", lambda _: "")
    base_url, backend = _resolve_openai_compatible_endpoint(cfg, cli_base_url=None, cli_backend=None)
    assert backend == "unsloth"
    assert base_url == "http://localhost:8888/v1"


def test_prompt_compatible_model_for_setup_uses_discovered_selection(monkeypatch):
    cfg = Config(data={"llm.model": "llama3.1"})
    monkeypatch.setattr(
        "cli._fetch_compatible_models_for_setup",
        lambda base_url, backend, api_key=None: ["gemma4:12b", "gpt-oss:20b"],
    )
    monkeypatch.setattr("builtins.input", lambda _: "2")
    model = _prompt_compatible_model_for_setup(
        cfg,
        base_url="http://localhost:11434/v1",
        backend="ollama",
        api_key="ollama",
    )
    assert model == "gpt-oss:20b"


def test_prompt_compatible_model_for_setup_allows_manual_entry(monkeypatch):
    cfg = Config(data={"llm.model": "llama3.1"})
    monkeypatch.setattr(
        "cli._fetch_compatible_models_for_setup",
        lambda base_url, backend, api_key=None: ["gemma4:12b"],
    )
    answers = iter(["2", "qwen3.6:27b"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    model = _prompt_compatible_model_for_setup(
        cfg,
        base_url="http://localhost:11434/v1",
        backend="ollama",
        api_key="ollama",
    )
    assert model == "qwen3.6:27b"


def test_resolve_provider_key_openai_compatible_defaults_to_ollama(monkeypatch):
    cfg = Config(data={})
    monkeypatch.setattr("cli._prompt_openai_api_key_with_default", lambda default_key="ollama": default_key)
    key = _resolve_provider_key(
        cfg,
        provider="openai",
        cli_key=None,
        openai_base_url="http://localhost:11434/v1",
        compatible_backend="ollama",
    )
    assert key == "ollama"


def test_resolve_provider_key_openai_compatible_unsloth_uses_compatible_prompt(monkeypatch):
    cfg = Config(data={})
    monkeypatch.setattr("cli._prompt_openai_compatible_api_key", lambda backend="other": "sk-unsloth-new")
    monkeypatch.setattr("cli._prompt_openai_api_key", lambda: "sk-openai-should-not-be-used")
    key = _resolve_provider_key(
        cfg,
        provider="openai_compatible",
        cli_key=None,
        openai_base_url="http://localhost:8888/v1",
        compatible_backend="unsloth",
    )
    assert key == "sk-unsloth-new"


def test_setup_provider_runtime_id_maps_compatible_to_openai():
    assert _setup_provider_runtime_id("openai_compatible") == "openai"
    assert _setup_provider_runtime_id("anthropic") == "anthropic"


def test_keys_subcommand_not_treated_as_query():
    with patch("cli.run_query") as mock_run_query, patch(
        "agent.config.Config.load", return_value=Config(data={})
    ):
        result = runner.invoke(app, ["keys"])

    assert result.exit_code == 0
    assert "API Keys" in result.stdout
    mock_run_query.assert_not_called()


def test_doctor_subcommand_not_treated_as_query():
    with patch("cli.run_query") as mock_run_query, patch(
        "agent.config.Config.load", return_value=Config(data={"llm.api_key": "x"})
    ):
        result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Fastfold Doctor" in result.stdout
    mock_run_query.assert_not_called()


def test_query_mode_uses_remaining_args_as_query():
    with patch("cli.run_query") as mock_run_query, patch(
        "cli.run_interactive"
    ) as mock_run_interactive:
        result = runner.invoke(app, ["run", "profile", "TP53", "in", "AML"])

    assert result.exit_code == 0
    mock_run_interactive.assert_not_called()
    mock_run_query.assert_called_once()
    called_query = mock_run_query.call_args[0][0]
    assert called_query == "profile TP53 in AML"


def test_no_args_enters_interactive_mode():
    with patch("cli.run_query") as mock_run_query, patch(
        "cli.run_interactive"
    ) as mock_run_interactive:
        result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    mock_run_query.assert_not_called()
    mock_run_interactive.assert_called_once()


def test_entry_routes_plain_invocation_to_hidden_run(monkeypatch):
    called = {}

    def fake_app(*, args, prog_name):
        called["args"] = args
        called["prog_name"] = prog_name

    monkeypatch.setattr("cli.app", fake_app)
    monkeypatch.setattr("sys.argv", ["ct", "profile", "TP53"])

    from cli import entry

    entry()

    assert called["prog_name"] == "fastfold"
    assert called["args"] == ["run", "profile", "TP53"]


def test_entry_preserves_explicit_subcommand(monkeypatch):
    called = {}

    def fake_app(*, args, prog_name):
        called["args"] = args
        called["prog_name"] = prog_name

    monkeypatch.setattr("cli.app", fake_app)
    monkeypatch.setattr("sys.argv", ["ct", "config", "show"])

    from cli import entry

    entry()

    assert called["prog_name"] == "fastfold"
    assert called["args"] == ["config", "show"]


def test_entry_preserves_trace_subcommand(monkeypatch):
    called = {}

    def fake_app(*, args, prog_name):
        called["args"] = args
        called["prog_name"] = prog_name

    monkeypatch.setattr("cli.app", fake_app)
    monkeypatch.setattr("sys.argv", ["ct", "trace", "diagnose"])

    from cli import entry

    entry()

    assert called["prog_name"] == "fastfold"
    assert called["args"] == ["trace", "diagnose"]


def test_entry_preserves_upgrade_subcommand(monkeypatch):
    called = {}

    def fake_app(*, args, prog_name):
        called["args"] = args
        called["prog_name"] = prog_name

    monkeypatch.setattr("cli.app", fake_app)
    monkeypatch.setattr("sys.argv", ["ct", "upgrade"])

    from cli import entry

    entry()

    assert called["prog_name"] == "fastfold"
    assert called["args"] == ["upgrade"]


def test_entry_routes_top_level_resume_flag_to_hidden_run(monkeypatch):
    called = {}

    def fake_app(*, args, prog_name):
        called["args"] = args
        called["prog_name"] = prog_name

    monkeypatch.setattr("cli.app", fake_app)
    monkeypatch.setattr("sys.argv", ["ct", "--resume", "d0b0571d"])

    from cli import entry

    entry()

    assert called["prog_name"] == "fastfold"
    assert called["args"] == ["run", "--resume", "d0b0571d"]


def test_resolve_upgrade_flavor_uses_persisted_value():
    cfg = Config(data={"install.uv_flavor": "win_build"})
    with patch.object(cfg, "save") as mock_save:
        flavor = resolve_upgrade_flavor(cfg=cfg, persist=True)
    assert flavor == "win_build"
    mock_save.assert_not_called()


def test_resolve_upgrade_flavor_falls_back_to_os_and_persists(monkeypatch):
    cfg = Config(data={})
    monkeypatch.setattr("cli.os.name", "posix", raising=False)
    with patch.object(cfg, "save") as mock_save:
        flavor = resolve_upgrade_flavor(cfg=cfg, persist=True)
    assert flavor == "all"
    assert cfg.get("install.uv_flavor") == "all"
    mock_save.assert_called_once()


def test_build_upgrade_command_for_win_build():
    cmd = build_upgrade_command("win_build")
    assert cmd == [
        "uv",
        "tool",
        "install",
        "fastfold-agent-cli[win_build]",
        "--python",
        "3.11",
        "--upgrade",
    ]


def test_is_newer_version_semver():
    assert is_newer_version("0.0.44", "0.0.43") is True
    assert is_newer_version("0.0.43", "0.0.43") is False
    assert is_newer_version("0.0.42", "0.0.43") is False


def test_get_upgrade_available_version_returns_latest_when_newer():
    with patch("cli.fetch_pypi_latest_version", return_value="0.0.99"):
        assert get_upgrade_available_version("0.0.43") == "0.0.99"


def test_get_upgrade_available_version_returns_none_when_not_newer():
    with patch("cli.fetch_pypi_latest_version", return_value="0.0.43"):
        assert get_upgrade_available_version("0.0.43") is None


def test_upgrade_subcommand_invokes_execute_upgrade():
    cfg = Config(data={})
    with patch("agent.config.Config.load", return_value=cfg), patch(
        "cli.execute_upgrade", return_value=True
    ) as mock_exec:
        result = runner.invoke(app, ["upgrade"])
    assert result.exit_code == 0
    mock_exec.assert_called_once_with(
        console_obj=ANY,
        cfg=cfg,
        install_missing_skills=False,
        prompt_missing_skills=True,
    )


def test_upgrade_subcommand_forwards_skill_flags():
    cfg = Config(data={})
    with patch("agent.config.Config.load", return_value=cfg), patch(
        "cli.execute_upgrade", return_value=True
    ) as mock_exec:
        result = runner.invoke(app, ["upgrade", "--install-skills", "--skip-skills-prompt"])
    assert result.exit_code == 0
    mock_exec.assert_called_once_with(
        console_obj=ANY,
        cfg=cfg,
        install_missing_skills=True,
        prompt_missing_skills=False,
    )


def test_config_set_agent_profile_applies_preset():
    cfg = Config(data={})
    with patch("agent.config.Config.load", return_value=cfg), patch.object(
        cfg, "save"
    ) as mock_save:
        result = runner.invoke(app, ["config", "set", "agent.profile", "enterprise"])

    assert result.exit_code == 0
    assert "applied preset settings" in result.stdout
    assert cfg.get("agent.profile") == "enterprise"
    assert cfg.get("agent.quality_gate_strict") is True
    mock_save.assert_called_once()


def test_config_set_agent_profile_rejects_invalid_value():
    cfg = Config(data={})
    with patch("agent.config.Config.load", return_value=cfg), patch.object(
        cfg, "save"
    ) as mock_save:
        result = runner.invoke(app, ["config", "set", "agent.profile", "invalid"])

    assert result.exit_code == 2
    assert "Invalid agent.profile" in result.stdout
    mock_save.assert_not_called()


def test_config_set_openai_key_rejects_invalid_format():
    cfg = Config(data={})
    with patch("agent.config.Config.load", return_value=cfg), patch.object(
        cfg, "save"
    ) as mock_save:
        result = runner.invoke(app, ["config", "set", "llm.openai_api_key", "bad-key"])

    assert result.exit_code == 2
    assert "Invalid OpenAI API key format" in result.stdout
    mock_save.assert_not_called()


def test_config_unset_removes_value():
    cfg = Config(data={"llm.openai_api_key": "sk-proj-AbCdEf1234567890xyz"})
    with patch("agent.config.Config.load", return_value=cfg), patch.object(
        cfg, "save"
    ) as mock_save:
        result = runner.invoke(app, ["config", "unset", "llm.openai_api_key"])

    assert result.exit_code == 0
    assert cfg.get("llm.openai_api_key") is None
    mock_save.assert_called_once()


def test_knowledge_status_command():
    fake_summary = {
        "path": "/tmp/substrate.json",
        "schema_version": 1,
        "n_entities": 3,
        "n_relations": 2,
        "n_evidence": 5,
        "entity_types": {"gene": 2, "disease": 1},
    }
    with patch("kb.substrate.KnowledgeSubstrate") as mock_cls:
        mock_cls.return_value.summary.return_value = fake_summary
        result = runner.invoke(app, ["knowledge", "status"])
    assert result.exit_code == 0
    assert "Knowledge Substrate" in result.stdout
    assert "Entities" in result.stdout


def test_knowledge_ingest_error_exits_nonzero():
    with patch("kb.ingest.KnowledgeIngestionPipeline") as mock_pipeline:
        mock_pipeline.return_value.ingest.return_value = {"error": "boom"}
        result = runner.invoke(app, ["knowledge", "ingest", "evidence_store"])
    assert result.exit_code == 2
    assert "boom" in result.stdout


def test_knowledge_benchmark_strict_failure_exits_nonzero():
    class FakeSuite:
        def run(self):
            return {
                "total_cases": 2,
                "expected_behavior_matches": 1,
                "pass_rate": 0.5,
            }

        def gate(self, summary, min_pass_rate=0.9):
            return {
                "ok": False,
                "message": "failed",
            }

    with patch("kb.benchmarks.BenchmarkSuite.load", return_value=FakeSuite()):
        result = runner.invoke(app, ["knowledge", "benchmark", "--strict"])
    assert result.exit_code == 2


def test_trace_diagnose_command_outputs_summary(tmp_path):
    trace = TraceLogger("cli-trace-ok")
    trace.query_start("q1")
    trace.plan([], query="q1")
    trace.step_start(1, "files.create_file", {"path": "a.txt"})
    trace.step_complete(1, "files.create_file", {"summary": "ok"}, duration_s=0.1)
    trace.synthesize_start()
    trace.synthesize_end(token_count=10, duration_s=0.1)
    trace.query_end(iterations=1, total_steps=1, completed_steps=1, failed_steps=0)

    path = tmp_path / "cli-trace-ok.trace.jsonl"
    trace.save(path)

    result = runner.invoke(app, ["trace", "diagnose", "--path", str(path)])
    assert result.exit_code == 0
    assert "Trace Diagnostics" in result.stdout
    assert "Queries" in result.stdout
    assert "Step fails" in result.stdout


def test_trace_diagnose_strict_exits_on_unclosed_query(tmp_path):
    trace = TraceLogger("cli-trace-bad")
    trace.query_start("unfinished")
    trace.plan([], query="unfinished")
    # Intentionally omit query_end

    path = tmp_path / "cli-trace-bad.trace.jsonl"
    trace.save(path)

    result = runner.invoke(app, ["trace", "diagnose", "--path", str(path), "--strict"])
    assert result.exit_code == 2


def test_trace_export_creates_bundle(tmp_path):
    trace = TraceLogger("cli-export")
    trace.query_start("q1")
    trace.plan([], query="q1")
    trace.step_start(1, "files.create_file", {"path": "a.txt"})
    trace.step_complete(1, "files.create_file", {"summary": "ok"}, duration_s=0.1)
    trace.synthesize_start()
    trace.synthesize_end(token_count=10, duration_s=0.1)
    trace.query_end(iterations=1, total_steps=1, completed_steps=1, failed_steps=0)

    trace_path = tmp_path / "cli-export.trace.jsonl"
    trace.save(trace_path)
    report_path = tmp_path / "report.md"
    report_path.write_text("# report", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "trace",
            "export",
            "--path",
            str(trace_path),
            "--report",
            str(report_path),
            "--out-dir",
            str(tmp_path / "exports"),
            "--no-zip",
        ],
    )
    assert result.exit_code == 0
    assert "Bundle exported:" in result.stdout

    bundles = sorted((tmp_path / "exports").glob("ct_run_bundle_*"))
    assert bundles
    bundle = bundles[-1]
    assert (bundle / "trace.jsonl").exists()
    assert (bundle / "trace_diagnostics.json").exists()
    assert (bundle / "query_summaries.json").exists()
    assert (bundle / "manifest.json").exists()
    assert (bundle / "report.md").exists()


def test_release_check_passes_with_no_tests_no_trace():
    cfg = Config(data={"llm.api_key": "x"})

    class FakeSuite:
        def run(self):
            return {
                "total_cases": 2,
                "expected_behavior_matches": 2,
                "pass_rate": 1.0,
            }

        def gate(self, summary, min_pass_rate=0.9):
            del summary, min_pass_rate
            return {
                "ok": True,
                "message": "passed",
            }

    with patch("agent.config.Config.load", return_value=cfg), patch(
        "agent.doctor.run_checks", return_value=[]
    ), patch("agent.doctor.has_errors", return_value=False), patch(
        "agent.doctor.to_table", return_value="doctor ok"
    ), patch("kb.benchmarks.BenchmarkSuite.load", return_value=FakeSuite()):
        result = runner.invoke(app, ["release-check", "--no-tests", "--no-trace"])

    assert result.exit_code == 0
    assert "Release check passed" in result.stdout


def test_release_check_fails_when_pytest_step_fails():
    cfg = Config(data={"llm.api_key": "x"})

    class FakeSuite:
        def run(self):
            return {
                "total_cases": 2,
                "expected_behavior_matches": 2,
                "pass_rate": 1.0,
            }

        def gate(self, summary, min_pass_rate=0.9):
            del summary, min_pass_rate
            return {
                "ok": True,
                "message": "passed",
            }

    fail_proc = subprocess.CompletedProcess(args=["pytest"], returncode=1, stdout="boom", stderr="")
    with patch("agent.config.Config.load", return_value=cfg), patch(
        "agent.doctor.run_checks", return_value=[]
    ), patch("agent.doctor.has_errors", return_value=False), patch(
        "agent.doctor.to_table", return_value="doctor ok"
    ), patch("kb.benchmarks.BenchmarkSuite.load", return_value=FakeSuite()), patch(
        "cli.subprocess.run", return_value=fail_proc
    ):
        result = runner.invoke(app, ["release-check", "--no-trace"])

    assert result.exit_code == 2
    assert "Release check failed" in result.stdout


def test_release_check_fails_on_trace_integrity_issues(tmp_path):
    cfg = Config(data={"llm.api_key": "x"})

    class FakeSuite:
        def run(self):
            return {
                "total_cases": 2,
                "expected_behavior_matches": 2,
                "pass_rate": 1.0,
            }

        def gate(self, summary, min_pass_rate=0.9):
            del summary, min_pass_rate
            return {
                "ok": True,
                "message": "passed",
            }

    trace = TraceLogger("bad-trace")
    trace.query_start("unfinished query")
    trace.plan([], query="unfinished query")
    trace_path = tmp_path / "bad-trace.trace.jsonl"
    trace.save(trace_path)

    with patch("agent.config.Config.load", return_value=cfg), patch(
        "agent.doctor.run_checks", return_value=[]
    ), patch("agent.doctor.has_errors", return_value=False), patch(
        "agent.doctor.to_table", return_value="doctor ok"
    ), patch("kb.benchmarks.BenchmarkSuite.load", return_value=FakeSuite()):
        result = runner.invoke(
            app,
            ["release-check", "--no-tests", "--trace-path", str(trace_path)],
        )

    assert result.exit_code == 2
    assert "Trace diagnostics detected integrity issues" in result.stdout


def test_release_check_pharma_policy_fails_without_profile():
    cfg = Config(data={"llm.api_key": "x", "agent.profile": "research"})
    with patch("agent.config.Config.load", return_value=cfg), patch(
        "agent.doctor.run_checks", return_value=[]
    ), patch("agent.doctor.has_errors", return_value=False), patch(
        "agent.doctor.to_table", return_value="doctor ok"
    ):
        result = runner.invoke(
            app,
            ["release-check", "--no-tests", "--no-benchmark", "--no-trace", "--pharma"],
        )

    assert result.exit_code == 2
    assert "Profile mismatch" in result.stdout


def test_release_check_pharma_policy_passes():
    cfg = Config(
        data={
            "llm.api_key": "x",
            "agent.profile": "pharma",
            "agent.synthesis_style": "pharma",
            "agent.quality_gate_strict": True,
            "agent.enable_experimental_tools": False,
            "agent.enable_claude_code_tool": False,
        }
    )
    with patch("agent.config.Config.load", return_value=cfg), patch(
        "agent.doctor.run_checks", return_value=[]
    ), patch("agent.doctor.has_errors", return_value=False), patch(
        "agent.doctor.to_table", return_value="doctor ok"
    ):
        result = runner.invoke(
            app,
            ["release-check", "--no-tests", "--no-benchmark", "--no-trace", "--pharma"],
        )

    assert result.exit_code == 0
    assert "Release check passed" in result.stdout
