"""Tests for Trajectory: session memory across queries."""

import json
import pytest
from pathlib import Path
from agent.trajectory import Trajectory, Turn  # type: ignore[import-untyped]
from agent.types import Step, Plan  # type: ignore[import-untyped]


class TestTrajectory:
    def test_add_turn(self):
        traj = Trajectory()
        traj.add_turn("What about TP53?", "TP53 is a tumor suppressor.")
        assert len(traj.turns) == 1
        assert traj.turns[0].query == "What about TP53?"
        assert traj.turns[0].answer == "TP53 is a tumor suppressor."
        assert traj.turns[0].entities == []

    def test_add_turn_with_plan(self):
        traj = Trajectory()
        steps = [
            Step(id=1, description="Search", tool="literature.pubmed_search",
                 status="completed"),
            Step(id=2, description="Classify", tool="safety.classify",
                 status="failed"),
        ]
        plan = Plan(query="test", steps=steps)

        traj.add_turn("Test query", "Test answer", plan=plan)
        assert "literature.pubmed_search" in traj.turns[0].tools_used
        # Failed steps should not be in tools_used
        assert "safety.classify" not in traj.turns[0].tools_used

    def test_max_turns_limit(self):
        traj = Trajectory(max_turns=3)
        for i in range(5):
            traj.add_turn(f"Query {i}", f"Answer {i}")

        assert len(traj.turns) == 3
        # Should keep the most recent 3
        assert traj.turns[0].query == "Query 2"
        assert traj.turns[-1].query == "Query 4"

    def test_context_for_planner_empty(self):
        traj = Trajectory()
        assert traj.context_for_planner() == ""

    def test_context_for_planner_with_turns(self):
        traj = Trajectory()
        traj.add_turn("What about TP53?", "TP53 is essential in many cancers.")
        traj.add_turn("Find drugs for BRCA1", "Found 3 compounds targeting BRCA1.")

        ctx = traj.context_for_planner()
        assert "Session Context" in ctx
        assert "TP53" in ctx
        assert "BRCA1" in ctx
        assert "Turn 1" in ctx
        assert "Turn 2" in ctx

    def test_context_limits_to_5_turns(self):
        genes = ["TP53", "BRCA1", "KRAS", "MYC", "EGFR", "BRAF", "PIK3CA", "PTEN"]
        traj = Trajectory()
        for i in range(8):
            traj.add_turn(f"Query about {genes[i]}", f"Answer {i}")

        ctx = traj.context_for_planner()
        # Should only include last 5 turns
        assert "Turn 1" in ctx
        assert "Turn 5" in ctx

    def test_entities_across_session(self):
        traj = Trajectory()
        traj.add_turn("What about TP53?", "It's important.")
        traj.add_turn("And BRCA1?", "Also important.")

        entities = traj.entities()
        assert entities == []

    def test_entities_deduplication(self):
        traj = Trajectory()
        traj.add_turn("TP53 analysis", "Found TP53 data.")
        traj.add_turn("More on TP53", "More TP53 data.")

        entities = traj.entities()
        assert entities == []

    def test_extracts_uuid_entities_from_turns(self):
        traj = Trajectory()
        job_id = "0390dc98-ad2c-409a-bd11-f0ed280beef9"
        traj.add_turn("Run fold", f"Completed. job_id: {job_id}")
        assert traj.turns[0].entities == [job_id]
        assert traj.entities() == [job_id]

    def test_entities_fallback_extracts_uuid_for_legacy_turns(self):
        traj = Trajectory()
        job_id = "0390dc98-ad2c-409a-bd11-f0ed280beef9"
        # Simulate legacy turn where entities were not persisted.
        traj.turns.append(Turn(query="Analyze structure", answer=f"use job {job_id}", entities=[]))
        assert traj.entities() == [job_id]


class TestPersistence:
    """Test saving and loading trajectories to/from JSONL."""

    def test_save_and_load(self, tmp_path):
        traj = Trajectory(session_id="test-123", title="Test session")
        traj.model = "gpt-5.5"
        traj.add_turn("What about TP53?", "TP53 is important.")
        traj.add_turn("And BRCA1?", "BRCA1 is also important.")

        path = tmp_path / "session.jsonl"
        traj.save(path)

        loaded = Trajectory.load(path)
        assert loaded.session_id == "test-123"
        assert loaded.title == "Test session"
        assert loaded.model == "gpt-5.5"
        assert len(loaded.turns) == 2
        assert loaded.turns[0].query == "What about TP53?"
        assert loaded.turns[1].answer == "BRCA1 is also important."
        assert loaded.turns[0].entities == []

    def test_save_creates_jsonl(self, tmp_path):
        traj = Trajectory(session_id="abc")
        traj.add_turn("Q1", "A1")
        path = tmp_path / "test.jsonl"
        traj.save(path)

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2  # meta + 1 turn
        meta = json.loads(lines[0])
        assert meta["type"] == "meta"
        assert meta["session_id"] == "abc"
        turn = json.loads(lines[1])
        assert turn["type"] == "turn"
        assert turn["query"] == "Q1"

    def test_load_empty_trajectory(self, tmp_path):
        traj = Trajectory(session_id="empty")
        path = tmp_path / "empty.jsonl"
        traj.save(path)

        loaded = Trajectory.load(path)
        assert loaded.session_id == "empty"
        assert len(loaded.turns) == 0

    def test_save_creates_parent_dirs(self, tmp_path):
        traj = Trajectory(session_id="nested")
        path = tmp_path / "deep" / "nested" / "session.jsonl"
        traj.save(path)
        assert path.exists()

    def test_list_sessions(self, tmp_path, monkeypatch):
        """List sessions should return saved sessions sorted by recency."""
        monkeypatch.setattr(Trajectory, "sessions_dir", staticmethod(lambda: tmp_path))

        # Create two sessions
        t1 = Trajectory(session_id="old")
        t1.created_at = 1000
        t1.title = "Old session"
        t1.add_turn("Q1", "A1")
        t1.save(tmp_path / "old.jsonl")

        t2 = Trajectory(session_id="new")
        t2.created_at = 2000
        t2.title = "New session"
        t2.add_turn("Q2", "A2")
        t2.save(tmp_path / "new.jsonl")

        sessions = Trajectory.list_sessions()
        assert len(sessions) == 2
        # Most recent first
        assert sessions[0]["session_id"] == "new"
        assert sessions[1]["session_id"] == "old"
        assert sessions[0]["title"] == "New session"
        assert sessions[0]["n_turns"] == 1

    def test_list_sessions_empty_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Trajectory, "sessions_dir", staticmethod(lambda: tmp_path))
        assert Trajectory.list_sessions() == []

    def test_load_by_session_id_and_prefix(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Trajectory, "sessions_dir", staticmethod(lambda: tmp_path))
        traj = Trajectory(session_id="abc12345", title="Prefix test")
        traj.add_turn("Q", "A")
        traj.save()

        exact = Trajectory.load("abc12345")
        assert exact.session_id == "abc12345"

        prefix = Trajectory.load("abc12")
        assert prefix.session_id == "abc12345"

    def test_load_prefix_ambiguous_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Trajectory, "sessions_dir", staticmethod(lambda: tmp_path))
        t1 = Trajectory(session_id="abc11111")
        t1.add_turn("Q1", "A1")
        t1.save()
        t2 = Trajectory(session_id="abc22222")
        t2.add_turn("Q2", "A2")
        t2.save()

        with pytest.raises(FileNotFoundError):
            Trajectory.load("abc")

    def test_roundtrip_preserves_entities_and_tools(self, tmp_path):
        traj = Trajectory(session_id="rt")
        steps = [
            Step(id=1, description="Search", tool="literature.pubmed_search",
                 status="completed"),
        ]
        plan = Plan(query="test", steps=steps)
        traj.add_turn("Search for TP53 papers", "Found 10 papers.", plan=plan)

        path = tmp_path / "rt.jsonl"
        traj.save(path)
        loaded = Trajectory.load(path)

        assert loaded.turns[0].entities == []
        assert "literature.pubmed_search" in loaded.turns[0].tools_used

    def test_roundtrip_preserves_usage_data(self, tmp_path):
        traj = Trajectory(session_id="usage")
        traj.set_usage_data(
            {
                "sdk_calls": 2,
                "sdk_input_tokens": 120,
                "sdk_output_tokens": 45,
                "sdk_models": ["gpt-5.5"],
                "sdk_turn_rows": [{"turn": 1, "input_tokens": 60, "output_tokens": 20}],
            }
        )
        path = tmp_path / "usage.jsonl"
        traj.save(path)

        loaded = Trajectory.load(path)
        usage = loaded.get_usage_data()
        assert usage["sdk_calls"] == 2
        assert usage["sdk_input_tokens"] == 120
        assert usage["sdk_output_tokens"] == 45
        assert usage["sdk_models"] == ["gpt-5.5"]

    def test_delete_session_removes_jsonl_and_trace(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Trajectory, "sessions_dir", staticmethod(lambda: tmp_path))
        traj = Trajectory(session_id="del12345")
        traj.add_turn("Q", "A")
        traj.save()
        trace_path = tmp_path / "del12345.trace.jsonl"
        trace_path.write_text('{"type":"query_start"}\n')

        result = Trajectory.delete_session("del12")

        assert result["session_id"] == "del12345"
        assert result["session_deleted"] is True
        assert result["trace_deleted"] is True
        assert not (tmp_path / "del12345.jsonl").exists()
        assert not trace_path.exists()
