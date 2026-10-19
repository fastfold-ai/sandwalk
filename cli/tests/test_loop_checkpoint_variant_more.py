"""Coverage for AgentLoop resume, bench checkpoints, and VEP annotation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.loop import AgentLoop
from agent_server.bench_service import checkpoint as checkpoint_mod
from tools.genomics import variant_annotate


class _Traj:
    def __init__(self, session_id: str = "", title: str = "") -> None:
        self.session_id = session_id
        self.title = title
        self.model = None
        self.turns: list[tuple[str, str]] = []

    def add_turn(self, user: str, assistant: str) -> None:
        self.turns.append((user, assistant))


class _Store:
    def __init__(self, session=None, sessions=None, messages=None) -> None:
        self.session = session
        self.sessions = sessions or []
        self.messages = messages or []

    def get_session(self, _session_id):
        return self.session

    def list_sessions(self):
        return self.sessions

    def list_messages(self, _session_id):
        return self.messages


def _session():
    return SimpleNamespace(current_model="gpt")


def _patch_loop(monkeypatch, traj_cls) -> None:
    monkeypatch.setattr("agent.loop.AgentRunner", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr("agent.loop.TraceStore", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr("agent.loop.Trajectory", traj_cls)
    monkeypatch.setattr(AgentLoop, "_ensure_shared_session", lambda self: None)
    monkeypatch.setattr("agent.loop.export_store_to_trajectory", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("agent.loop.import_trajectory", lambda *_args, **_kwargs: None)


def test_agent_loop_resume_paths(monkeypatch) -> None:
    _patch_loop(monkeypatch, _Traj)
    store = _Store()
    loop = AgentLoop(_session(), store=store, session_id="fixed")
    assert loop.trajectory.session_id == "fixed"
    assert loop.trajectory.model == "gpt"

    with pytest.raises(FileNotFoundError, match="No session id"):
        AgentLoop.resume(_session(), "  ", store=store)

    class Loaded(_Traj):
        @staticmethod
        def resolve_session_path(_session_id):
            return "saved.jsonl"

        @staticmethod
        def load(_path):
            return _Traj(session_id="")

    _patch_loop(monkeypatch, Loaded)
    resumed = AgentLoop.resume(_session(), "abc", store=store)
    assert resumed.trajectory.session_id == "abc"

    shared = SimpleNamespace(id="abcdef", title="Chat")
    messages = [
        SimpleNamespace(role="user", content="hi"),
        SimpleNamespace(role="note", content="skip"),
        SimpleNamespace(role="assistant", content="hello"),
    ]

    class Missing(_Traj):
        @staticmethod
        def resolve_session_path(_session_id):
            raise FileNotFoundError("gone")

    _patch_loop(monkeypatch, Missing)
    sqlite_store = _Store(session=shared, messages=messages)
    from_store = AgentLoop.resume(_session(), "abcdef", store=sqlite_store)
    assert from_store.trajectory.turns == [("hi", "hello")]

    prefix_store = _Store(session=None, sessions=[shared])
    prefixed = AgentLoop.resume(_session(), "abc", store=prefix_store)
    assert prefixed.trajectory.session_id == "abcdef"

    ambiguous = _Store(
        session=None,
        sessions=[SimpleNamespace(id="abc1", title=""), SimpleNamespace(id="abc2", title="")],
    )
    with pytest.raises(FileNotFoundError, match="ambiguous"):
        AgentLoop.resume(_session(), "abc", store=ambiguous)

    with pytest.raises(FileNotFoundError, match="not found"):
        AgentLoop.resume(_session(), "zzz", store=_Store())

    def explode(*_args, **_kwargs):
        raise RuntimeError("sync")

    monkeypatch.setattr("agent.loop.export_store_to_trajectory", explode)
    monkeypatch.setattr("agent.loop.import_trajectory", explode)
    still = AgentLoop.resume(_session(), "abcdef", store=sqlite_store)
    assert still.trajectory.session_id == "abcdef"

    class Listed(_Traj):
        @staticmethod
        def list_sessions():
            return [{"session_id": "latest"}]

        @staticmethod
        def resolve_session_path(_session_id):
            return "latest.jsonl"

        @staticmethod
        def load(_path):
            return _Traj(session_id="latest")

    _patch_loop(monkeypatch, Listed)
    latest = AgentLoop.resume_latest(_session(), store=store)
    assert latest.trajectory.session_id == "latest"

    class EmptyList(_Traj):
        @staticmethod
        def list_sessions():
            return []

        @staticmethod
        def resolve_session_path(_session_id):
            raise FileNotFoundError("gone")

    _patch_loop(monkeypatch, EmptyList)
    with pytest.raises(FileNotFoundError, match="No saved sessions"):
        AgentLoop.resume_latest(_session(), store=_Store())
    from_shared = AgentLoop.resume_latest(_session(), store=_Store(sessions=[shared]))
    assert from_shared.trajectory.session_id == "abcdef"


def test_checkpoints_round_trip_and_resume_rules(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(checkpoint_mod, "results_dir", lambda: tmp_path)
    with pytest.raises(ValueError, match="run_id"):
        checkpoint_mod.save_checkpoint({})

    path = checkpoint_mod.save_checkpoint({"run_id": "run-1", "status": "running"})
    assert path.is_file()
    assert checkpoint_mod.load_checkpoint("run-1")["status"] == "running"
    assert checkpoint_mod.load_checkpoint("missing") is None
    assert checkpoint_mod.delete_checkpoint("missing") is False
    assert checkpoint_mod.delete_checkpoint("run-1") is True

    (tmp_path / "bad.checkpoint.json").write_text("{", encoding="utf-8")
    assert checkpoint_mod.load_checkpoint("bad") is None
    checkpoint_mod.save_checkpoint({"run_id": "done", "status": "cancelled"})
    checkpoint_mod.save_checkpoint(
        {"run_id": "left", "status": "complete", "remaining_question_ids": ["q1"]}
    )
    assert checkpoint_mod.is_resumable_checkpoint(None) is False
    assert checkpoint_mod.is_resumable_checkpoint({"status": "cancelled", "run_id": "done"}) is False
    assert checkpoint_mod.checkpoint_resume_status({"run_id": "p", "status": "paused"}) == "paused"
    assert checkpoint_mod.checkpoint_resume_status({"run_id": "r", "status": "running"}) == "interrupted"
    found = checkpoint_mod.find_resumable_checkpoint()
    assert found["run_id"] == "left"
    assert any(row["run_id"] == "done" for row in checkpoint_mod.list_checkpoints())

    real_replace = checkpoint_mod.os.replace

    def boom(_src, _dst):
        raise OSError("replace")

    monkeypatch.setattr(checkpoint_mod.os, "replace", boom)
    with pytest.raises(OSError, match="replace"):
        checkpoint_mod.save_checkpoint({"run_id": "broken"})
    monkeypatch.setattr(checkpoint_mod.os, "replace", real_replace)


def test_variant_annotate_shapes_vep_results(monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        return None, "down"

    monkeypatch.setattr("tools.genomics.request", fail)
    assert "failed" in variant_annotate("rs1")["error"]

    def status(code, payload):
        def _request(*_args, **_kwargs):
            return SimpleNamespace(status_code=code, json=lambda: payload), None

        return _request

    monkeypatch.setattr("tools.genomics.request", status(400, []))
    assert "Invalid variant" in variant_annotate("17:g.1A>T")["error"]
    monkeypatch.setattr("tools.genomics.request", status(500, []))
    assert "HTTP 500" in variant_annotate("rs1")["error"]

    def bad_json(*_args, **_kwargs):
        def _json():
            raise ValueError("nope")

        return SimpleNamespace(status_code=200, json=_json), None

    monkeypatch.setattr("tools.genomics.request", bad_json)
    assert "invalid JSON" in variant_annotate("rs1")["error"]
    monkeypatch.setattr("tools.genomics.request", status(200, {}))
    assert "No VEP results" in variant_annotate("rs1")["error"]

    payload = [
        {
            "id": "rs1",
            "most_severe_consequence": "missense",
            "seq_region_name": "17",
            "start": 10,
            "end": 10,
            "colocated_variants": [
                {
                    "id": "rs1",
                    "frequencies": {"A": {"gnomAD": 0.01}},
                    "minor_allele": "A",
                    "minor_allele_freq": 0.01,
                    "clin_sig": ["pathogenic"],
                }
            ],
            "transcript_consequences": [
                {
                    "gene_symbol": "TP53",
                    "impact": "MODERATE",
                    "amino_acids": "R/H",
                    "protein_position": "100",
                    "canonical": 1,
                },
                {"gene_symbol": "WRAP", "impact": "HIGH", "canonical": 0},
            ],
        }
    ]
    monkeypatch.setattr("tools.genomics.request", status(200, payload))
    result = variant_annotate(" rs1 ")
    assert result["variant_id"] == "rs1"
    assert result["location"] == "17:10-10"
    assert "p.R100H" in result["summary"]
    assert "MAF=" in result["summary"]
    assert "pathogenic" in result["summary"]
    assert result["transcript_consequences"][0]["canonical"] is True
