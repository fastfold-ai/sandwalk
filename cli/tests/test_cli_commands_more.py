"""Additional Typer CliRunner tests for uncovered cli.py commands."""

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from agent.config import Config
from agent.trace import TraceLogger
from cli import app, execute_upgrade, get_upgrade_available_version

runner = CliRunner()


class TestReportNotebook:
    def test_report_notebook_exports_ipynb(self, tmp_path, monkeypatch):
        trace = TraceLogger("nb-trace")
        trace.query_start("analyze TP53")
        trace.plan([], query="analyze TP53")
        trace.query_end(iterations=1, total_steps=0, completed_steps=0, failed_steps=0)
        trace_path = tmp_path / "nb-trace.trace.jsonl"
        trace.save(trace_path)

        cfg = Config(data={"sandbox.output_dir": str(tmp_path)})
        fake_nb = MagicMock()
        fake_nb.cells = [MagicMock(cell_type="markdown", source="# Report")]

        with patch("agent.config.Config.load", return_value=cfg), patch(
            "agent.trace_store.TraceStore.find_trace", return_value=trace_path
        ), patch("reports.notebook.trace_to_notebook", return_value=fake_nb) as mock_convert, patch(
            "reports.notebook.save_notebook",
            return_value=tmp_path / "reports" / "nb-trace.ipynb",
        ) as mock_save:
            result = runner.invoke(app, ["report", "notebook"])

        assert result.exit_code == 0
        mock_convert.assert_called_once_with(trace_path)
        mock_save.assert_called_once()
        assert "Notebook:" in result.stdout

    def test_report_notebook_no_trace_exits(self):
        with patch("agent.trace_store.TraceStore.find_trace", return_value=None):
            result = runner.invoke(app, ["report", "notebook"])
        assert result.exit_code == 2
        assert "No trace files found" in result.stdout

    def test_report_notebook_html_fallback(self, tmp_path):
        trace_path = tmp_path / "t.trace.jsonl"
        trace_path.write_text("{}\n")
        cfg = Config(data={"sandbox.output_dir": str(tmp_path)})
        fake_nb = MagicMock()
        fake_nb.cells = [MagicMock(cell_type="markdown", source="# Title")]

        import builtins

        real_import = builtins.__import__

        def import_without_nbconvert(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "nbconvert":
                raise ImportError("no nbconvert")
            return real_import(name, globals, locals, fromlist, level)

        with patch("agent.config.Config.load", return_value=cfg), patch(
            "agent.trace_store.TraceStore.find_trace", return_value=trace_path
        ), patch("reports.notebook.trace_to_notebook", return_value=fake_nb), patch(
            "reports.notebook.save_notebook", return_value=tmp_path / "out.ipynb"
        ), patch("builtins.__import__", side_effect=import_without_nbconvert), patch(
            "reports.html.render_html_report", return_value="<html>ok</html>"
        ):
            result = runner.invoke(app, ["report", "notebook", "--html"])

        assert result.exit_code == 0
        assert (tmp_path / "out.html").exists()
        assert "markdown only" in result.stdout.lower()


class TestTraceDiagnoseJson:
    def test_trace_diagnose_json_output(self, tmp_path):
        trace = TraceLogger("json-trace")
        trace.query_start("query one")
        trace.query_end(iterations=1, total_steps=0, completed_steps=0, failed_steps=0)
        path = tmp_path / "json-trace.trace.jsonl"
        trace.save(path)

        result = runner.invoke(app, ["trace", "diagnose", "--path", str(path), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["query_count"] == 1


class TestUpgradeCommand:
    def test_get_upgrade_available_version_newer(self):
        with patch("cli.fetch_pypi_latest_version", return_value="9.9.9"):
            assert get_upgrade_available_version("0.0.52") == "9.9.9"

    def test_get_upgrade_available_version_none_when_same(self):
        with patch("cli.fetch_pypi_latest_version", return_value="0.0.52"):
            assert get_upgrade_available_version("0.0.52") is None

    def test_upgrade_cmd_success(self):
        cfg = Config(data={"install.uv_flavor": "all"})
        proc = MagicMock(returncode=0, stdout="installed", stderr="")
        skills_result = {"added": [], "updated": [], "failed": [], "npx_synced": 0, "summary": "ok"}
        with patch("agent.config.Config.load", return_value=cfg), patch(
            "cli.subprocess.run", return_value=proc
        ), patch(
            "agent.skills.upgrade_skills", return_value=skills_result
        ):
            result = runner.invoke(app, ["upgrade"])
        assert result.exit_code == 0
        assert "Upgrade complete" in result.stdout

    def test_upgrade_cmd_uv_missing(self):
        cfg = Config(data={})
        with patch("agent.config.Config.load", return_value=cfg), patch(
            "cli.subprocess.run", side_effect=FileNotFoundError()
        ):
            ok = execute_upgrade(cfg=cfg)
        assert ok is False


class TestKnowledgeIngest:
    def test_knowledge_ingest_success(self):
        with patch("kb.ingest.KnowledgeIngestionPipeline") as mock_cls:
            mock_cls.return_value.ingest.return_value = {"summary": "Ingested 3 records"}
            result = runner.invoke(app, ["knowledge", "ingest", "evidence_store"])
        assert result.exit_code == 0
        assert "Ingested 3 records" in result.stdout

    def test_knowledge_ingest_error_exits(self):
        with patch("kb.ingest.KnowledgeIngestionPipeline") as mock_cls:
            mock_cls.return_value.ingest.return_value = {"error": "bad source"}
            result = runner.invoke(app, ["knowledge", "ingest", "evidence_store"])
        assert result.exit_code == 2
        assert "bad source" in result.stdout


class TestCaseStudyList:
    def test_case_study_list_shows_registry(self):
        result = runner.invoke(app, ["case-study", "list"])
        assert result.exit_code == 0
        assert "revlimid" in result.stdout.lower() or "Case Studies" in result.stdout


class TestDataPull:
    def test_data_pull_invokes_downloader(self, tmp_path):
        with patch("data.downloader.download_dataset") as mock_download:
            result = runner.invoke(app, ["data", "pull", "depmap", "--output", str(tmp_path)])
        assert result.exit_code == 0
        mock_download.assert_called_once_with("depmap", tmp_path)


class TestConfigShow:
    def test_config_show_table(self):
        cfg = Config(data={"llm": {"provider": "anthropic", "model": "claude-sonnet"}})
        with patch("agent.config.Config.load", return_value=cfg), patch.object(
            cfg, "to_table", return_value="[table] llm.provider = anthropic"
        ):
            result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "llm.provider" in result.stdout


class TestReportPublish:
    def test_report_publish_converts_markdown(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        md = reports / "brief.md"
        md.write_text("# Report\n\nBody")
        cfg = Config(data={"sandbox.output_dir": str(tmp_path)})

        with patch("agent.config.Config.load", return_value=cfg), patch(
            "reports.html.publish_report", return_value=tmp_path / "reports" / "brief.html"
        ) as mock_publish:
            result = runner.invoke(app, ["report", "publish", "--path", str(md)])

        assert result.exit_code == 0
        mock_publish.assert_called_once()
        assert "brief.html" in result.stdout or "publish" in result.stdout.lower()


class TestReportShow:
    def test_report_show_auto_publishes_latest_markdown(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        md = reports / "latest.md"
        md.write_text("# Report\n\nBody")
        html = reports / "latest.html"
        cfg = Config(data={"sandbox.output_dir": str(tmp_path)})

        def _publish(_path):
            html.write_text("<html>ok</html>")
            return html

        with patch("agent.config.Config.load", return_value=cfg), patch(
            "cli._latest_report_path", return_value=md
        ), patch("reports.html.publish_report", side_effect=_publish) as mock_publish, patch(
            "webbrowser.open"
        ) as mock_open:
            result = runner.invoke(app, ["report", "show"])

        assert result.exit_code == 0
        mock_publish.assert_called_once_with(md)
        mock_open.assert_called_once()
        assert "Auto-published" in result.stdout

    def test_report_show_missing_path_exits(self, tmp_path):
        missing = tmp_path / "missing.html"
        result = runner.invoke(app, ["report", "show", "--path", str(missing)])
        assert result.exit_code == 2
        assert "File not found" in result.stdout


class TestBenchCommand:
    def test_bench_force_clears_outputs_then_dry_run(self, tmp_path):
        out_dir = tmp_path / "bench-out"
        (out_dir / "results").mkdir(parents=True)
        (out_dir / "evals").mkdir(parents=True)
        (out_dir / ".preview_cache").mkdir(parents=True)
        (out_dir / "all_results.json").write_text("{}")
        (out_dir / "llm_eval.json").write_text("{}")

        manifest = tmp_path / "manifest.json"
        manifest.write_text(
            json.dumps(
                [
                    {
                        "question_id": "q1",
                        "question": "What is TP53?",
                        "ideal": "tumor suppressor",
                        "data_dir": "",
                    }
                ]
            )
        )

        fake_runner_mod = types.SimpleNamespace(BenchRunner=MagicMock())
        with patch.dict(sys.modules, {"bench": types.SimpleNamespace(), "bench.runner": fake_runner_mod}):
            result = runner.invoke(
                app,
                [
                    "bench",
                    "--force",
                    "--dry-run",
                    "--manifest",
                    str(manifest),
                    "--output",
                    str(out_dir),
                ],
            )

        assert result.exit_code == 0
        assert "Cleared" in result.stdout
        assert not (out_dir / "results").exists()
        assert not (out_dir / "all_results.json").exists()


class TestTraceExport:
    def test_trace_export_bundle(self, tmp_path):
        trace = TraceLogger("export-trace")
        trace.query_start("export query")
        trace.query_end(iterations=1, total_steps=0, completed_steps=0, failed_steps=0)
        path = tmp_path / "export-trace.trace.jsonl"
        trace.save(path)

        out_dir = tmp_path / "exports"
        cfg = Config(data={"sandbox.output_dir": str(tmp_path)})

        with patch("agent.config.Config.load", return_value=cfg):
            result = runner.invoke(
                app,
                ["trace", "export", "--path", str(path), "--out-dir", str(out_dir), "--no-zip"],
            )

        assert result.exit_code == 0
        bundles = list(out_dir.iterdir())
        assert bundles
        bundle = bundles[0]
        assert (bundle / "trace.jsonl").exists()
        assert (bundle / "trace_diagnostics.json").exists()


class TestCaseStudyRun:
    def test_case_study_unknown_id_exits(self):
        result = runner.invoke(app, ["case-study", "run", "not-a-case"])
        assert result.exit_code == 2
        assert "Unknown case study" in result.stdout

    @patch("reports.html.publish_report")
    @patch("agent.case_studies.run_case_study")
    @patch("cli.Session")
    @patch("cli.setup_cmd")
    def test_case_study_run_success(self, mock_setup, mock_session_cls, mock_run, mock_publish, tmp_path):
        cfg = Config(data={"llm.api_key": "sk-test", "sandbox.output_dir": str(tmp_path)})
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_run.return_value = MagicMock(summary="done", duration_s=1.0)
        reports = tmp_path / "reports"
        reports.mkdir()
        (reports / "case.md").write_text("# Case")

        with patch("agent.config.Config.load", return_value=cfg), patch.object(
            cfg, "llm_preflight_issue", return_value=None
        ), patch("cli.print_banner"), patch("cli._latest_report_path", return_value=reports / "case.md"):
            mock_publish.return_value = reports / "case.html"
            result = runner.invoke(app, ["case-study", "run", "revlimid", "--threads", "2"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        mock_publish.assert_called_once()


class TestMiscCliCommands:
    def test_config_unset(self, monkeypatch):
        cfg = Config(data={"llm": {"provider": "anthropic"}})
        monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
        with patch.object(cfg, "unset") as mock_unset, patch.object(cfg, "save") as mock_save:
            result = runner.invoke(app, ["config", "unset", "llm.provider"])
        assert result.exit_code == 0
        mock_unset.assert_called_once_with("llm.provider")
        mock_save.assert_called_once()

    def test_skill_add_command(self):
        with patch("agent.skills.install_skill", return_value={"ok": True, "summary": "installed fold", "via": "git"}):
            result = runner.invoke(app, ["skills", "add", "fold"])
        assert result.exit_code == 0
        assert "installed fold" in result.stdout

    def test_trace_diagnose_strict_with_issues(self, tmp_path):
        trace = TraceLogger("strict-trace")
        trace.query_start("q")
        path = tmp_path / "strict-trace.trace.jsonl"
        trace.save(path)
        result = runner.invoke(app, ["trace", "diagnose", "--path", str(path), "--strict"])
        assert result.exit_code == 2
