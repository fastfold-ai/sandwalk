"""Extended Typer CliRunner tests for cli.py subcommands with mocks."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from agent.config import Config
from agent.trace import TraceLogger
from cli import app

runner = CliRunner()


class TestDoctorCommand:
    def test_doctor_success(self):
        cfg = Config(data={"llm.api_key": "sk-test"})
        with patch("agent.config.Config.load", return_value=cfg), patch(
            "agent.doctor.run_checks", return_value=[]
        ), patch("agent.doctor.has_errors", return_value=False), patch(
            "agent.doctor.to_table", return_value="All checks passed"
        ):
            result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "No blocking issues" in result.stdout

    def test_doctor_exits_on_errors(self):
        cfg = Config(data={})
        with patch("agent.config.Config.load", return_value=cfg), patch(
            "agent.doctor.run_checks", return_value=[{"level": "error"}]
        ), patch("agent.doctor.has_errors", return_value=True), patch(
            "agent.doctor.to_table", return_value="Errors found"
        ):
            result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1
        assert "Blocking issues" in result.stdout


class TestKeysCommand:
    def test_keys_shows_table(self):
        cfg = Config(data={"llm.provider": "anthropic"})
        with patch("agent.config.Config.load", return_value=cfg), patch.object(
            cfg, "keys_table", return_value="[table] API Keys"
        ):
            result = runner.invoke(app, ["keys"])
        assert result.exit_code == 0
        assert "API Keys" in result.stdout


class TestDataStatusCommand:
    def test_data_status_prints_report(self):
        with patch("data.downloader.dataset_status", return_value="depmap: ready"):
            result = runner.invoke(app, ["data", "status"])
        assert result.exit_code == 0
        assert "depmap" in result.stdout


class TestToolListCommand:
    def test_tool_list_shows_registry(self):
        result = runner.invoke(app, ["tool", "list"])
        assert result.exit_code == 0
        assert "target." in result.stdout or "Tool" in result.stdout

    def test_tool_list_warns_on_load_errors(self):
        with patch("tools.tool_load_errors", return_value={"broken_mod": "ImportError"}):
            result = runner.invoke(app, ["tool", "list"])
        assert result.exit_code == 0
        assert "failed to load" in result.stdout.lower() or "Warning" in result.stdout


class TestSkillsListCommand:
    def test_skills_list_empty_exits(self):
        with patch("agent.skills.list_skills", return_value=[]):
            result = runner.invoke(app, ["skills", "list"])
        assert result.exit_code != 0 or "No skills" in result.stdout

    def test_skills_list_shows_installed(self):
        skill = MagicMock()
        skill.name = "fold"
        skill.source = "bundled"
        skill.description = "Protein folding jobs"
        skill.author = "fastfold-ai"
        skill.updated_at = ""
        skill.version = None
        with patch("agent.skills.list_skills", return_value=[skill]):
            result = runner.invoke(app, ["skills", "list"])
        assert result.exit_code == 0
        assert "fold" in result.stdout
        assert "Protein folding" in result.stdout


class TestTraceDiagnoseCommand:
    def test_trace_diagnose_with_path(self, tmp_path):
        trace = TraceLogger("ext-trace")
        trace.query_start("analyze TP53")
        trace.plan([], query="analyze TP53")
        trace.step_start(1, "target.druggability", {"target": "TP53"})
        trace.step_complete(1, "target.druggability", {"summary": "druggable"}, duration_s=0.2)
        trace.synthesize_start()
        trace.synthesize_end(token_count=50, duration_s=0.3)
        trace.query_end(iterations=1, total_steps=1, completed_steps=1, failed_steps=0)

        path = tmp_path / "ext-trace.trace.jsonl"
        trace.save(path)

        result = runner.invoke(app, ["trace", "diagnose", "--path", str(path)])
        assert result.exit_code == 0
        assert "Trace Diagnostics" in result.stdout


class TestReportListCommand:
    def test_report_list_no_directory(self, tmp_path, monkeypatch):
        cfg = Config(data={"sandbox.output_dir": str(tmp_path / "missing")})
        with patch("agent.config.Config.load", return_value=cfg):
            result = runner.invoke(app, ["report", "list"])
        assert "No reports" in result.stdout

    def test_report_list_shows_files(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        (reports / "brief_one.md").write_text("# Report 1")
        (reports / "brief_two.md").write_text("# Report 2")

        cfg = Config(data={"sandbox.output_dir": str(tmp_path)})
        with patch("agent.config.Config.load", return_value=cfg):
            result = runner.invoke(app, ["report", "list"])
        assert result.exit_code == 0
        assert "brief_one.md" in result.stdout or "Reports" in result.stdout


class TestKnowledgeStatusCommand:
    def test_knowledge_status(self):
        summary = {
            "path": "/tmp/substrate.json",
            "schema_version": 1,
            "n_entities": 10,
            "n_relations": 5,
            "n_evidence": 20,
            "entity_types": {"gene": 7, "disease": 3},
        }
        with patch("kb.substrate.KnowledgeSubstrate") as mock_cls:
            mock_cls.return_value.summary.return_value = summary
            result = runner.invoke(app, ["knowledge", "status"])
        assert result.exit_code == 0
        assert "Knowledge Substrate" in result.stdout
        assert "Entities" in result.stdout


class TestReleaseCheckCommand:
    def test_release_check_passes_minimal(self):
        cfg = Config(data={"llm.api_key": "x"})

        class FakeSuite:
            def run(self):
                return {"total_cases": 1, "expected_behavior_matches": 1, "pass_rate": 1.0}

            def gate(self, summary, min_pass_rate=0.9):
                return {"ok": True, "message": "ok"}

        with patch("agent.config.Config.load", return_value=cfg), patch(
            "agent.doctor.run_checks", return_value=[]
        ), patch("agent.doctor.has_errors", return_value=False), patch(
            "agent.doctor.to_table", return_value="ok"
        ), patch("kb.benchmarks.BenchmarkSuite.load", return_value=FakeSuite()):
            result = runner.invoke(app, ["release-check", "--no-tests", "--no-trace"])
        assert result.exit_code == 0
        assert "Release check passed" in result.stdout

    def test_release_check_fails_pytest(self):
        cfg = Config(data={"llm.api_key": "x"})

        class FakeSuite:
            def run(self):
                return {"total_cases": 1, "expected_behavior_matches": 1, "pass_rate": 1.0}

            def gate(self, summary, min_pass_rate=0.9):
                return {"ok": True, "message": "ok"}

        fail_proc = subprocess.CompletedProcess(args=["pytest"], returncode=1, stdout="fail", stderr="")
        with patch("agent.config.Config.load", return_value=cfg), patch(
            "agent.doctor.run_checks", return_value=[]
        ), patch("agent.doctor.has_errors", return_value=False), patch(
            "agent.doctor.to_table", return_value="ok"
        ), patch("kb.benchmarks.BenchmarkSuite.load", return_value=FakeSuite()), patch(
            "cli.subprocess.run", return_value=fail_proc
        ):
            result = runner.invoke(app, ["release-check", "--no-trace"])
        assert result.exit_code == 2
        assert "Release check failed" in result.stdout


class TestConfigUnsetCommand:
    def test_config_unset_removes_key(self):
        cfg = Config(data={"llm.openai_api_key": "sk-proj-AbCdEf1234567890xyz"})
        with patch("agent.config.Config.load", return_value=cfg), patch.object(cfg, "save") as mock_save:
            result = runner.invoke(app, ["config", "unset", "llm.openai_api_key"])
        assert result.exit_code == 0
        assert cfg.get("llm.openai_api_key") is None
        assert "Unset" in result.stdout
        mock_save.assert_called_once()
