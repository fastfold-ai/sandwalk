"""Tests for multi-agent ResearchOrchestrator."""

from unittest.mock import MagicMock, patch

import pytest

from agent.orchestrator import (
    OrchestratorResult,
    ResearchOrchestrator,
    ThreadGoal,
    ThreadResult,
)
from agent.types import Plan, Step


def _mock_session(tmp_path):
    session = MagicMock()
    session.config.get.side_effect = lambda key, default=None: {
        "agent.parallel_max_threads": 5,
        "sandbox.output_dir": str(tmp_path),
        "llm.provider": "anthropic",
        "llm.model": "test-model",
    }.get(key, default)
    session.console = MagicMock()
    return session


class TestOrchestratorResult:
    def test_to_markdown_includes_threads_and_metadata(self):
        plan = Plan(
            query="Test query",
            steps=[
                Step(
                    id=1,
                    description="Step one",
                    tool="target.druggability",
                    status="completed",
                    result={"summary": "Druggable"},
                )
            ],
        )
        result = OrchestratorResult(
            threads=[
                ThreadResult(
                    thread_id=1,
                    goal="Target biology",
                    completed_steps=1,
                    failed_steps=0,
                    duration_s=1.5,
                )
            ],
            merged_plan=plan,
            summary="Synthesis text.",
            duration_s=3.0,
            n_threads=1,
            metadata={
                "query": "Test query",
                "timestamp": "2026-01-01",
                "model": "claude-test",
                "execution_time_s": 3.0,
                "ct_version": "0.0.51",
            },
        )
        md = result.to_markdown()
        assert "Multi-Agent Research Report" in md
        assert "Target biology" in md
        assert "Synthesis text." in md
        assert "target.druggability" in md


class TestMergeResults:
    def test_renumbers_steps_across_threads(self, tmp_path):
        session = _mock_session(tmp_path)
        orch = ResearchOrchestrator(session, n_threads=2)

        tr1 = ThreadResult(
            thread_id=1,
            goal="Target angle",
            plan=Plan(
                query="q",
                steps=[
                    Step(id=1, description="Step A", tool="t.a", status="completed"),
                    Step(id=2, description="Step B", tool="t.b", status="completed"),
                ],
            ),
            raw_results={1: {"summary": "a"}, 2: {"summary": "b"}},
        )
        tr2 = ThreadResult(
            thread_id=2,
            goal="Chemistry angle",
            plan=Plan(
                query="q",
                steps=[
                    Step(id=1, description="Step C", tool="t.c", status="failed"),
                ],
            ),
            raw_results={1: {"summary": "c"}},
        )

        merged_plan, merged_raw = orch._merge_results("Combined query", [tr1, tr2])
        assert len(merged_plan.steps) == 3
        assert merged_plan.steps[0].id == 1
        assert merged_plan.steps[1].id == 2
        assert merged_plan.steps[2].id == 3
        assert "[Thread 1:" in merged_plan.steps[0].description
        assert "[Thread 2:" in merged_plan.steps[2].description
        assert merged_raw[1]["summary"] == "a"
        assert merged_raw[3]["summary"] == "c"

    def test_skips_failed_threads(self, tmp_path):
        session = _mock_session(tmp_path)
        orch = ResearchOrchestrator(session)
        tr = ThreadResult(thread_id=1, goal="Failed", error="boom", plan=None)
        plan, raw = orch._merge_results("q", [tr])
        assert plan.steps == []
        assert raw == {}


class TestOrchestratorRun:
    def test_run_with_preset_goals(self, tmp_path):
        session = _mock_session(tmp_path)
        orch = ResearchOrchestrator(session, n_threads=2)

        goals = [
            ThreadGoal(thread_id=1, angle="Biology", goal="Study TP53"),
            ThreadGoal(thread_id=2, angle="Chemistry", goal="Study lenalidomide"),
        ]

        fake_thread = ThreadResult(
            thread_id=1,
            goal="Study TP53",
            plan=Plan(query="q", steps=[]),
            completed_steps=0,
            failed_steps=0,
            duration_s=0.5,
        )

        with patch.object(orch, "_execute_threads", return_value=[fake_thread, fake_thread]):
            with patch.object(orch, "_synthesize", return_value="Merged summary"):
                with patch.object(orch, "_auto_save_report"):
                    result = orch.run("Test query", preset_goals=goals)

        assert result.n_threads == 2
        assert result.summary == "Merged summary"

    def test_decompose_parses_json(self, tmp_path):
        session = _mock_session(tmp_path)
        llm = MagicMock()
        llm.chat.return_value = MagicMock(
            content='[{"angle": "Safety", "goal": "Assess risk", "suggested_tools": ["safety.classify"]}]'
        )
        session.get_llm.return_value = llm
        orch = ResearchOrchestrator(session, n_threads=1)

        with patch("agent.orchestrator.ThinkingStatus"):
            goals = orch._decompose("Assess lenalidomide safety", {})

        assert len(goals) == 1
        assert goals[0].angle == "Safety"
        assert "safety.classify" in goals[0].suggested_tools

    def test_decompose_fallback_on_bad_json(self, tmp_path):
        session = _mock_session(tmp_path)
        llm = MagicMock()
        llm.chat.return_value = MagicMock(content="not json at all")
        session.get_llm.return_value = llm
        orch = ResearchOrchestrator(session, n_threads=1)

        with patch("agent.orchestrator.ThinkingStatus"):
            goals = orch._decompose("Fallback query", {})

        assert len(goals) == 1
        assert goals[0].goal == "Fallback query"
