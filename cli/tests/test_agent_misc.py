"""Tests for agent support modules: evidence board, loop, runtime adapters."""

from unittest.mock import MagicMock, patch

import pytest

from agent.evidence_board import EvidenceBoard, EvidenceEntry
from agent.loop import AgentLoop, Clarification, ClarificationNeeded
from agent.runtime_adapters import RuntimeEvent, RuntimeExecutionOutput
from agent.types import ExecutionResult, Plan, Step


class TestEvidenceBoard:
    def test_post_and_retrieve(self):
        board = EvidenceBoard()
        board.post(1, 1, "target.druggability", "TP53 is druggable", {"score": 0.9})
        board.post(2, 1, "chemistry.descriptors", "MW=440", {})

        assert len(board) == 2
        all_entries = board.get_all()
        assert all_entries[0].tool == "target.druggability"
        assert board.get_by_thread(2)[0].summary == "MW=440"

    def test_to_context_str(self):
        board = EvidenceBoard()
        assert board.to_context_str() == ""
        board.post(1, 1, "t.a", "Finding A")
        text = board.to_context_str()
        assert "Cross-thread evidence board" in text
        assert "Finding A" in text

    def test_repr(self):
        board = EvidenceBoard()
        board.post(1, 1, "t.a", "x")
        assert "EvidenceBoard(1 entries)" in repr(board)


class TestRuntimeAdapters:
    def test_dataclasses(self):
        event = RuntimeEvent(type="text", payload={"content": "hi"})
        assert event.type == "text"
        output = RuntimeExecutionOutput(
            full_text=["answer"],
            tool_calls=[{"name": "run_python"}],
            usage={"input_tokens": 10},
        )
        assert output.full_text == ["answer"]


class TestAgentLoop:
    def _session(self):
        session = MagicMock()
        session.current_model = "test-model"
        session.config.get.return_value = None
        return session

    def test_clarification_needed_exception(self):
        clar = Clarification(question="Which gene?", missing=["gene"])
        exc = ClarificationNeeded(clar)
        assert exc.clarification.question == "Which gene?"

    def test_run_raises_clarification_when_needed(self, tmp_path):
        from agent_server.store import AgentStore

        session = self._session()
        loop = AgentLoop(session, headless=True, store=AgentStore(tmp_path / "agent.db"))

        plan = Plan(query="q", steps=[])
        result = ExecutionResult(
            plan=plan,
            raw_results={
                "clarification": {
                    "clarification_needed": True,
                    "question": "Which indication?",
                    "missing": ["indication"],
                    "suggestions": ["NSCLC"],
                }
            },
        )

        with patch.object(loop._runner, "run", return_value=result):
            with pytest.raises(ClarificationNeeded) as excinfo:
                loop.run("Analyze target")
        assert excinfo.value.clarification.question == "Which indication?"

    def test_run_records_trajectory(self, tmp_path):
        from agent_server.store import AgentStore

        session = self._session()
        store = AgentStore(tmp_path / "agent.db")
        loop = AgentLoop(session, headless=True, store=store)
        plan = Plan(query="Analyze TP53", steps=[])
        result = ExecutionResult(plan=plan, summary="TP53 summary.")

        with patch.object(loop._runner, "run", return_value=result), patch.object(
            loop.trajectory, "save"
        ), patch.object(
            loop, "_generate_title", return_value="Analyze TP53"
        ):
            out = loop.run("Analyze TP53")

        assert out.summary == "TP53 summary."
        assert len(loop.trajectory.turns) == 1
        assert loop.trajectory.title == "Analyze TP53"
        messages = store.list_messages(loop.trajectory.session_id)
        assert [message.role for message in messages] == ["user", "assistant"]
