"""Tests for agent/case_studies.py registry and runner helpers."""

from unittest.mock import MagicMock, patch

import pytest

from agent.case_studies import (  # type: ignore[import-untyped]
    CASE_STUDIES,
    CaseStudy,
    build_thread_goals,
    run_case_study,
)
from agent.orchestrator import OrchestratorResult, ThreadGoal


class TestCaseStudyRegistry:
    def test_expected_case_studies_registered(self):
        expected = {"revlimid", "gleevec", "keytruda", "ozempic", "xalkori"}
        assert expected.issubset(set(CASE_STUDIES.keys()))

    @pytest.mark.parametrize("case_id", ["revlimid", "gleevec", "keytruda"])
    def test_case_study_fields(self, case_id):
        case = CASE_STUDIES[case_id]
        assert isinstance(case, CaseStudy)
        assert case.id == case_id
        assert case.compound
        assert case.targets
        assert case.indication
        assert case.description
        assert len(case.thread_goals) >= 3

    def test_thread_goals_have_required_keys(self):
        for case in CASE_STUDIES.values():
            for goal in case.thread_goals:
                assert "angle" in goal
                assert "goal" in goal
                assert isinstance(goal.get("suggested_tools", []), list)


class TestBuildThreadGoals:
    def test_converts_dicts_to_thread_goal_objects(self):
        case = CASE_STUDIES["revlimid"]
        goals = build_thread_goals(case)
        assert len(goals) == len(case.thread_goals)
        assert all(isinstance(g, ThreadGoal) for g in goals)
        assert goals[0].thread_id == 1
        assert goals[0].angle == case.thread_goals[0]["angle"]
        assert goals[0].suggested_tools == case.thread_goals[0]["suggested_tools"]

    def test_sequential_thread_ids(self):
        case = CASE_STUDIES["gleevec"]
        goals = build_thread_goals(case)
        assert [g.thread_id for g in goals] == list(range(1, len(goals) + 1))


class TestRunCaseStudy:
    def test_unknown_case_raises(self):
        session = MagicMock()
        with pytest.raises(ValueError, match="Unknown case study"):
            run_case_study(session, "not_a_real_case")

    @patch("agent.case_studies.ResearchOrchestrator")
    def test_run_case_study_invokes_orchestrator(self, mock_orch_cls):
        session = MagicMock()
        fake_result = OrchestratorResult(
            threads=[],
            summary="merged report",
            duration_s=1.0,
        )
        mock_orch = MagicMock()
        mock_orch.run.return_value = fake_result
        mock_orch_cls.return_value = mock_orch

        result = run_case_study(session, "revlimid", n_threads=2)

        assert result is fake_result
        mock_orch_cls.assert_called_once_with(session, n_threads=2)
        call_args = mock_orch.run.call_args
        assert "lenalidomide" in call_args[0][0].lower()
        context = call_args[0][1]
        assert context["compound"] == "lenalidomide"
        assert context["case_study"] == "revlimid"
        preset_goals = call_args[1]["preset_goals"]
        assert len(preset_goals) == len(CASE_STUDIES["revlimid"].thread_goals)

    @patch("agent.case_studies.ResearchOrchestrator")
    def test_default_n_threads_matches_goals(self, mock_orch_cls):
        session = MagicMock()
        mock_orch = MagicMock()
        mock_orch.run.return_value = OrchestratorResult(threads=[], summary="", duration_s=0)
        mock_orch_cls.return_value = mock_orch

        run_case_study(session, "ozempic")

        n_threads = mock_orch_cls.call_args.kwargs.get("n_threads") or mock_orch_cls.call_args[1].get("n_threads")
        if n_threads is None:
            n_threads = mock_orch_cls.call_args[0][1] if len(mock_orch_cls.call_args[0]) > 1 else None
        # Called as ResearchOrchestrator(session, n_threads=n)
        assert mock_orch_cls.call_args.kwargs["n_threads"] == len(CASE_STUDIES["ozempic"].thread_goals)
