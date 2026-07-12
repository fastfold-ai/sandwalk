"""Additional CLI command and helper tests."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.request

import pytest
from typer.testing import CliRunner

from agent.config import Config
from cli import (
    _format_plan_label,
    _latest_report_path,
    _latest_trace_path,
    _normalize_upgrade_flavor,
    _parse_semver_triplet,
    _print_trace_diagnostics_table,
    _random_command_tip_markup,
    _random_news_item_markup,
    _resolve_trace_path,
    _trace_has_issues,
    app,
    fetch_pypi_latest_version,
    is_newer_version,
)

runner = CliRunner()


class TestSemverHelpers:
    def test_parse_semver_triplet(self):
        assert _parse_semver_triplet("1.2.3") == (1, 2, 3)
        assert _parse_semver_triplet("bad") is None

    def test_is_newer_version(self):
        assert is_newer_version("0.0.52", "0.0.51") is True
        assert is_newer_version("0.0.51", "0.0.51") is False
        assert is_newer_version("0.0.50", "0.0.51") is False


class TestUpgradeFlavor:
    def test_normalize_upgrade_flavor(self):
        assert _normalize_upgrade_flavor("all") == "all"
        assert _normalize_upgrade_flavor("invalid") is None

    def test_format_plan_label(self):
        assert "Pro" in _format_plan_label("pro") or "pro" in _format_plan_label("pro").lower()


class TestMarkupHelpers:
    def test_random_tip_and_news(self):
        assert _random_command_tip_markup()
        assert _random_news_item_markup()


class TestTraceHelpers:
    def test_latest_trace_path_empty(self, tmp_path, monkeypatch):
        traces = tmp_path / "traces"
        traces.mkdir()
        monkeypatch.setattr("agent.trace.TraceLogger.traces_dir", staticmethod(lambda: traces))
        assert _latest_trace_path() is None

    def test_resolve_trace_path_by_session(self, tmp_path, monkeypatch):
        traces = tmp_path / "traces"
        traces.mkdir()
        trace_file = traces / "abc123.trace.jsonl"
        trace_file.write_text("{}")
        monkeypatch.setattr("agent.trace.TraceLogger.traces_dir", staticmethod(lambda: traces))
        resolved = _resolve_trace_path(None, "abc123")
        assert resolved == trace_file

    def test_trace_has_issues(self):
        assert _trace_has_issues({"unclosed_queries": ["q1"]}) is True
        assert _trace_has_issues({}) is False

    def test_print_trace_diagnostics_table(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        diag = {
            "session_id": "sess1",
            "event_count": 5,
            "query_count": 1,
            "query_start_count": 1,
            "query_end_count": 1,
            "total_step_start_count": 2,
            "total_step_complete_count": 2,
            "total_step_fail_count": 0,
            "total_step_retry_count": 0,
            "unclosed_queries": [],
            "queries_with_failures": [],
            "queries_with_no_plan": [],
            "queries_with_no_completion": [],
            "queries_with_synthesis_mismatch": [],
        }
        _print_trace_diagnostics_table(diag, "Diagnostics")
        output = buf.getvalue()
        assert "sess1" in output or "Diagnostics" in output


class TestReportHelpers:
    def test_latest_report_path(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        older = reports / "old_report.md"
        newer = reports / "new_report.md"
        older.write_text("old")
        newer.write_text("new")
        found = _latest_report_path(str(tmp_path))
        assert found == newer


class TestConfigCommands:
    def test_config_show_and_get(self, monkeypatch, tmp_path):
        cfg = Config(data={"llm": {"provider": "anthropic"}})
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)

        show_result = runner.invoke(app, ["config", "show"])
        assert show_result.exit_code == 0

        get_result = runner.invoke(app, ["config", "get", "llm.provider"])
        assert get_result.exit_code == 0
        assert "anthropic" in get_result.stdout

    def test_config_validate(self, monkeypatch):
        cfg = MagicMock()
        cfg.validate.return_value = []
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
        result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code == 0


class TestToolList:
    def test_tool_list_command(self):
        result = runner.invoke(app, ["tool", "list"])
        assert result.exit_code == 0
        assert "target." in result.stdout or "tools" in result.stdout.lower()


class TestFetchPypi:
    def test_fetch_pypi_latest_version_mocked(self):
        fake_response = MagicMock()
        fake_response.read.return_value = b'{"info": {"version": "9.9.9"}}'
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("cli.urllib.request.urlopen", return_value=fake_response):
            version = fetch_pypi_latest_version(timeout_s=1.0)
        assert version == "9.9.9"
