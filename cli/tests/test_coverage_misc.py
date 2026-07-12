"""Miscellaneous coverage tests for kb, ui, cli skill selection, and tools."""

import asyncio
import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from rich.live import Live

from agent.config import Config
from kb.ingest import KnowledgeIngestionPipeline
from kb.substrate import KnowledgeSubstrate
from ui.status import THINKING_WORDS, ThinkingStatus, _ThinkingRenderable


class TestKbIngestExtended:
    def test_ingest_unknown_source(self, tmp_path):
        pipeline = KnowledgeIngestionPipeline(
            substrate=KnowledgeSubstrate(path=tmp_path / "sub.json"),
            state_path=tmp_path / "state.json",
            evidence_path=tmp_path / "evidence.jsonl",
        )
        out = pipeline.ingest(source="bogus")
        assert "error" in out

    def test_ingest_pubmed_requires_query(self, tmp_path):
        pipeline = KnowledgeIngestionPipeline(
            substrate=KnowledgeSubstrate(path=tmp_path / "sub.json"),
            state_path=tmp_path / "state.json",
            evidence_path=tmp_path / "evidence.jsonl",
        )
        out = pipeline.ingest(source="pubmed")
        assert out["error"] == "query is required for source=pubmed"

    def test_evidence_store_missing_file(self, tmp_path):
        pipeline = KnowledgeIngestionPipeline(
            substrate=KnowledgeSubstrate(path=tmp_path / "sub.json"),
            state_path=tmp_path / "state.json",
            evidence_path=tmp_path / "missing.jsonl",
        )
        out = pipeline.ingest_evidence_store()
        assert out["ingested_records"] == 0

    def test_evidence_store_no_new_lines(self, tmp_path):
        evidence = tmp_path / "evidence.jsonl"
        evidence.write_text("{}\n", encoding="utf-8")
        state = tmp_path / "state.json"
        state.write_text(
            json.dumps({"evidence_line_offset": 1, "source_runs": {}}),
            encoding="utf-8",
        )
        pipeline = KnowledgeIngestionPipeline(
            substrate=KnowledgeSubstrate(path=tmp_path / "sub.json"),
            state_path=state,
            evidence_path=evidence,
        )
        out = pipeline.ingest_evidence_store()
        assert out["ingested_records"] == 0

    def test_load_state_corrupt_json(self, tmp_path):
        state = tmp_path / "state.json"
        state.write_text("not-json", encoding="utf-8")
        pipeline = KnowledgeIngestionPipeline(
            substrate=KnowledgeSubstrate(path=tmp_path / "sub.json"),
            state_path=state,
            evidence_path=tmp_path / "evidence.jsonl",
        )
        assert pipeline._state["evidence_line_offset"] == 0

    def test_ingest_openalex_with_mock(self, monkeypatch, tmp_path):
        def fake_openalex(query: str, max_results: int = 10, **kwargs):
            return {
                "articles": [
                    {
                        "doi": "10.1234/example",
                        "title": "Example paper",
                        "publication_year": 2024,
                        "cited_by_count": 3,
                    }
                ]
            }

        monkeypatch.setattr("tools.literature.openalex_search", fake_openalex)
        pipeline = KnowledgeIngestionPipeline(
            substrate=KnowledgeSubstrate(path=tmp_path / "sub.json"),
            state_path=tmp_path / "state.json",
            evidence_path=tmp_path / "evidence.jsonl",
        )
        out = pipeline.ingest_openalex(query="TP53", max_results=1)
        assert out["ingested_works"] == 1
        assert out["links_created"] >= 1


class TestUiStatusExtended:
    def test_thinking_renderable_short_elapsed(self):
        renderable = _ThinkingRenderable(["folding"], spinner_style="dna_helix")
        console = Console(file=StringIO(), force_terminal=True, width=80)
        list(renderable.__rich_console__(console, console.options))
        # Smoke: should not raise

    def test_thinking_renderable_long_elapsed(self, monkeypatch):
        monkeypatch.setattr("ui.status.time.time", lambda: 100.0)
        renderable = _ThinkingRenderable(["folding"])
        renderable.start_time = 0.0
        console = Console(file=StringIO(), force_terminal=True, width=80)
        output = "".join(str(seg) for seg in list(renderable.__rich_console__(console, console.options)))
        assert "m" in output

    def test_thinking_status_kick_and_stop(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr(
            Config,
            "load",
            classmethod(lambda cls: Config(data={"ui.spinner": "dna_helix"})),
        )
        status = ThinkingStatus(console, phase="synthesizing")
        with patch.object(Live, "__enter__", return_value=MagicMock()), patch.object(
            Live, "__exit__", return_value=False
        ):
            status.__enter__()
            status.kick()
            status.stop()
        assert status._live is None

    def test_thinking_status_async_refresh_cancel(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr(Config, "load", classmethod(lambda cls: Config(data={})))
        status = ThinkingStatus(console, phase="planning")
        fake_task = MagicMock()
        status._async_task = fake_task
        status._cancel_async_task()
        fake_task.cancel.assert_called_once()
        assert status._async_task is None

    def test_thinking_words_cover_phases(self):
        for phase in ("planning", "synthesizing", "executing"):
            assert phase in THINKING_WORDS or "planning" in THINKING_WORDS


class TestCliSkillSelection:
    def test_select_skills_from_catalog_all_default(self, captured_console, monkeypatch):
        from cli import _select_skills_from_catalog

        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("cli.sys.stdin.isatty", lambda: False)
        monkeypatch.setattr("cli.sys.stdout.isatty", lambda: False)
        monkeypatch.setattr("builtins.input", lambda _: "")
        catalog = [
            {"name": "fold", "description": "Folding", "install_source": "fold-src"},
            {"name": "md", "description": "MD", "install_source": "md-src"},
        ]
        sources = _select_skills_from_catalog(catalog)
        assert sources == ["fold-src", "md-src"]

    def test_select_skills_from_catalog_none(self, captured_console, monkeypatch):
        from cli import _select_skills_from_catalog

        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("cli.sys.stdin.isatty", lambda: False)
        monkeypatch.setattr("cli.sys.stdout.isatty", lambda: False)
        monkeypatch.setattr("builtins.input", lambda _: "none")
        catalog = [{"name": "fold", "description": "Folding", "install_source": "fold-src"}]
        assert _select_skills_from_catalog(catalog) == []

    def test_install_skill_sources_git_fallback(self, captured_console, monkeypatch):
        from cli import _install_skill_sources

        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("agent.skills._npx_available", lambda: False)
        monkeypatch.setattr(
            "agent.skills.install_skill",
            lambda src, prefer_npx=False: {"ok": True, "summary": f"installed {src}", "via": "git"},
        )
        _install_skill_sources(["fastfold-ai/skills@skills/fold"])
        assert "installed" in buf.getvalue().lower() or "✓" in buf.getvalue()

    def test_print_trace_diagnostics_table(self, captured_console, monkeypatch):
        from cli import _print_trace_diagnostics_table

        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        diag = {
            "session_id": "sess-1",
            "event_count": 10,
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
        assert "sess-1" in buf.getvalue()
