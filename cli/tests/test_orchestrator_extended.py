"""Extended ResearchOrchestrator coverage for synthesis, threads, and auto-save."""

from unittest.mock import MagicMock, patch

import pytest

from agent.orchestrator import ResearchOrchestrator, ThreadGoal, ThreadResult
from agent.types import Plan, Step


def _mock_session(tmp_path, verbose=False):
    session = MagicMock()
    session.verbose = verbose
    session.mode = "batch"
    session.config.get.side_effect = lambda key, default=None: {
        "agent.parallel_max_threads": 5,
        "sandbox.output_dir": str(tmp_path),
        "llm.provider": "anthropic",
        "llm.model": "test-model",
        "agent.profile": "research",
        "output.auto_publish_html_batch": False,
    }.get(key, default)
    session.console = MagicMock()
    return session


class TestSynthesize:
    def test_synthesize_merges_thread_findings(self, tmp_path):
        session = _mock_session(tmp_path)
        llm = MagicMock()
        llm.chat.return_value = MagicMock(content="  Integrated report  ")
        session.get_llm.return_value = llm

        plan = Plan(
            query="q",
            steps=[
                Step(
                    id=1,
                    description="Druggability",
                    tool="target.druggability",
                    status="completed",
                    result={"summary": "Druggable pocket"},
                )
            ],
        )
        thread = ThreadResult(
            thread_id=1,
            goal="Target biology for TP53",
            plan=plan,
            completed_steps=1,
            failed_steps=0,
        )
        orch = ResearchOrchestrator(session, n_threads=1)

        with patch("agent.orchestrator.ThinkingStatus"):
            summary = orch._synthesize("Analyze TP53", plan, {}, [thread])

        assert summary == "Integrated report"
        llm.chat.assert_called_once()
        user_msg = llm.chat.call_args.kwargs["messages"][0]["content"]
        assert "TP53" in user_msg
        assert "Druggable pocket" in user_msg

    def test_synthesize_includes_failed_thread_note(self, tmp_path):
        session = _mock_session(tmp_path)
        llm = MagicMock()
        llm.chat.return_value = MagicMock(content="Partial synthesis")
        session.get_llm.return_value = llm
        orch = ResearchOrchestrator(session)
        failed = ThreadResult(thread_id=2, goal="Chemistry angle", error="timeout")

        with patch("agent.orchestrator.ThinkingStatus"):
            summary = orch._synthesize("q", Plan(query="q", steps=[]), {}, [failed])

        assert summary == "Partial synthesis"
        user_msg = llm.chat.call_args.kwargs["messages"][0]["content"]
        assert "FAILED" in user_msg


class TestExecuteThreads:
    def test_execute_threads_runs_workers(self, tmp_path):
        session = _mock_session(tmp_path)
        orch = ResearchOrchestrator(session, n_threads=2)
        goals = [
            ThreadGoal(thread_id=1, angle="Biology", goal="Study gene A"),
            ThreadGoal(thread_id=2, angle="Safety", goal="Assess risk"),
        ]
        fake_results = [
            ThreadResult(thread_id=1, goal="Study gene A", completed_steps=1, duration_s=0.2),
            ThreadResult(thread_id=2, goal="Assess risk", completed_steps=2, duration_s=0.3),
        ]

        with patch.object(orch, "_execute_single_thread", side_effect=fake_results):
            with patch("agent.orchestrator.Live") as mock_live:
                mock_live.return_value.__enter__ = MagicMock(return_value=MagicMock())
                mock_live.return_value.__exit__ = MagicMock(return_value=False)
                results = orch._execute_threads("Combined query", goals, {})

        assert len(results) == 2
        assert results[0].thread_id == 1
        assert results[1].thread_id == 2

    def test_execute_threads_captures_worker_exception(self, tmp_path):
        session = _mock_session(tmp_path)
        orch = ResearchOrchestrator(session, n_threads=1)
        goals = [ThreadGoal(thread_id=1, angle="Biology", goal="Boom")]

        def boom(*args, **kwargs):
            raise RuntimeError("worker exploded")

        with patch.object(orch, "_execute_single_thread", side_effect=boom):
            with patch("agent.orchestrator.Live") as mock_live:
                mock_live.return_value.__enter__ = MagicMock(return_value=MagicMock())
                mock_live.return_value.__exit__ = MagicMock(return_value=False)
                results = orch._execute_threads("q", goals, {})

        assert len(results) == 1
        assert results[0].error == "worker exploded"


class TestAutoSaveReport:
    def test_auto_save_report_writes_markdown(self, tmp_path):
        session = _mock_session(tmp_path)
        orch = ResearchOrchestrator(session)
        result = ThreadResult(
            thread_id=1,
            goal="Angle",
            plan=Plan(query="q", steps=[]),
            completed_steps=1,
            failed_steps=0,
            duration_s=1.0,
        )
        from agent.orchestrator import OrchestratorResult

        merged = OrchestratorResult(
            threads=[result],
            merged_plan=Plan(query="Analyze CRBN", steps=[]),
            summary="Final synthesis",
            duration_s=2.5,
            n_threads=1,
            total_steps=1,
            completed_steps=1,
            failed_steps=0,
        )

        orch._auto_save_report("Analyze CRBN", merged)

        reports_dir = tmp_path / "reports"
        saved = list(reports_dir.glob("*_multi_*.md"))
        assert saved, "expected auto-saved report file"
        text = saved[0].read_text(encoding="utf-8")
        assert "Final synthesis" in text
        assert merged.metadata.get("query") == "Analyze CRBN"
        assert merged.metadata.get("ct_version")

    def test_auto_save_report_swallows_errors_when_not_verbose(self, tmp_path):
        session = _mock_session(tmp_path, verbose=False)
        orch = ResearchOrchestrator(session)
        from agent.orchestrator import OrchestratorResult

        merged = OrchestratorResult(summary="x", n_threads=1)

        with patch("pathlib.Path.mkdir", side_effect=OSError("disk full")):
            orch._auto_save_report("q", merged)  # should not raise


class TestRunFullPath:
    def test_run_full_pipeline_with_mocks(self, tmp_path):
        session = _mock_session(tmp_path)
        orch = ResearchOrchestrator(session, n_threads=2)

        goals = [
            ThreadGoal(thread_id=1, angle="Biology", goal="Study TP53"),
            ThreadGoal(thread_id=2, angle="Clinical", goal="Trial landscape"),
        ]
        thread_a = ThreadResult(
            thread_id=1,
            goal="Study TP53",
            plan=Plan(
                query="q",
                steps=[
                    Step(id=1, description="Step A", tool="t.a", status="completed", result={"summary": "A"}),
                ],
            ),
            raw_results={1: {"summary": "A"}},
            completed_steps=1,
            duration_s=0.4,
        )
        thread_b = ThreadResult(
            thread_id=2,
            goal="Trial landscape",
            plan=Plan(query="q", steps=[]),
            completed_steps=0,
            duration_s=0.2,
        )

        with patch.object(orch, "_execute_threads", return_value=[thread_b, thread_a]):
            with patch.object(orch, "_synthesize", return_value="Merged narrative"):
                result = orch.run("Full query", preset_goals=goals)

        assert result.summary == "Merged narrative"
        assert result.n_threads == 2
        assert result.merged_plan is not None
        assert len(result.merged_plan.steps) == 1
        assert result.completed_steps == 1
