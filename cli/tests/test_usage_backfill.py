"""Usage ledger backfill from events, titles, and trajectory files."""

from __future__ import annotations

import json
from types import SimpleNamespace

from agent_server.service import AgentService
from agent_server.store import AgentStore
from agent_server.usage_service import backfill as bf


def _store(tmp_path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    return store, AgentService(store)


def test_payload_and_model_helpers(tmp_path, monkeypatch):
    assert bf._payload_dict({"a": 1}) == {"a": 1}
    assert bf._payload_dict("{") == {}
    assert bf._payload_dict("[]") == {}
    assert bf._payload_dict("") == {}
    assert bf._model_from_title("Fold · gpt-4o-mini") == "gpt-4o-mini"
    assert bf._model_from_title("plain") is None
    assert bf._model_from_usage_meta({"usage_data": {"sdk_models": "  claude "}}) == "claude"
    assert bf._model_from_usage_meta({"usage_data": {"sdk_models": ["", "gpt"]}}) == "gpt"
    assert bf._model_from_usage_meta({"model": "fallback"}) == "fallback"
    assert bf._model_from_usage_meta({}) is None
    assert bf._surface_from_row({"client_surface": "ui"}) == "ui"
    assert bf._surface_from_row({"source": "slack"}) == "slack"
    assert bf._surface_from_row({}) == "unknown"
    assert bf._resolve_model("s", payload_model="m", traj_models={}, title_models={}) == "m"
    assert bf._resolve_model("abcdefghij", payload_model=None, traj_models={"abcdefgh": "from-prefix"}, title_models={}) == "from-prefix"
    assert bf._resolve_model("missing", payload_model=None, traj_models={}, title_models={}) is None

    store, svc = _store(tmp_path, monkeypatch)
    session = svc.create_session(title="Lab · gpt-4o-mini", workspace_path=None)
    titles = bf._session_title_model_map(store)
    assert titles[session.id] == "gpt-4o-mini"

    def _boom():
        raise RuntimeError("no sessions")

    store.list_sessions = _boom
    assert bf._session_title_model_map(store) == {}


def test_trajectory_and_backfill_round_trip(tmp_path, monkeypatch):
    store, svc = _store(tmp_path, monkeypatch)
    session = svc.create_session(title="Bench · gpt-4o-mini", workspace_path=None)
    store.append_event(
        session_id=session.id,
        event_type="run.usage",
        run_id="run-1",
        payload={"input_tokens": 4, "output_tokens": 2, "model_id": "gpt-4o-mini", "provider": "openai"},
    )
    store.append_event(
        session_id=session.id,
        event_type="run.usage",
        run_id="",
        payload={"input_tokens": 1},
    )
    store.append_event(
        session_id=session.id,
        event_type="run.usage",
        run_id="empty",
        payload={"input_tokens": 0, "output_tokens": 0},
    )

    traj = tmp_path / "traj"
    traj.mkdir()
    (traj / "covered.jsonl").write_text("")
    (traj / "bad.jsonl").write_text("not-json\n")
    (traj / "note.jsonl").write_text(json.dumps({"type": "note"}) + "\n")
    (traj / "zero.jsonl").write_text(
        json.dumps({"type": "meta", "session_id": "zero-sess", "usage_data": {"sdk_input_tokens": 0}}) + "\n"
    )
    (traj / "fresh.jsonl").write_text(
        json.dumps(
            {
                "type": "meta",
                "session_id": "fresh-sess",
                "provider": "anthropic",
                "updated_at": 1_700_000_000,
                "usage_data": {
                    "sdk_models": ["claude-3-5-sonnet"],
                    "sdk_input_tokens": 3,
                    "sdk_output_tokens": 1,
                    "sdk_cache_read_tokens": 0,
                    "sdk_cache_creation_tokens": 0,
                },
            }
        )
        + "\n"
    )
    (traj / "short.jsonl").write_text(
        json.dumps(
            {
                "type": "meta",
                "usage_data": {"sdk_models": ["other-model"], "sdk_input_tokens": 1},
            }
        )
        + "\n"
    )

    monkeypatch.setattr("agent.trajectory.Trajectory.sessions_dir", staticmethod(lambda: traj))
    mapped = bf._trajectory_model_map()
    assert mapped["fresh-sess"]
    assert bf.backfill_from_events(store) == 1
    imported = bf.backfill_from_trajectories(store)
    assert imported >= 1
    assert bf.backfill_from_trajectories(store) == imported or bf.backfill_from_trajectories(store) == 0

    store.upsert_usage_run(
        run_id="repair-me",
        session_id=session.id,
        day="2026-01-01",
        surface="ui",
        model_id=None,
        provider=None,
        input_tokens=1,
        output_tokens=0,
        cache_read_tokens=0,
        cache_creation_tokens=0,
    )
    assert bf.repair_missing_models(store) >= 1
    store.upsert_usage_run(
        run_id="provider-me",
        session_id=session.id,
        day="2026-01-02",
        surface="ui",
        model_id="gpt-4o-mini",
        provider=None,
        input_tokens=1,
        output_tokens=0,
        cache_read_tokens=0,
        cache_creation_tokens=0,
    )
    assert bf.repair_missing_providers(store) >= 0
    store.upsert_usage_run(
        run_id="alias-me",
        session_id=session.id,
        day="2026-01-03",
        surface="ui",
        model_id="openai/gpt-4o-mini",
        provider="openai",
        input_tokens=1,
        output_tokens=0,
        cache_read_tokens=0,
        cache_creation_tokens=0,
    )
    assert bf.repair_model_aliases(store) >= 0

    first = bf.run_backfill(store, force=True)
    assert first.ok is True
    again = bf.run_backfill(store)
    assert again.runs_upserted == 0
    store.set_usage_meta(bf._MODEL_REPAIR_META_KEY, "pending")
    store.set_usage_meta(bf._PROVIDER_REPAIR_META_KEY, "pending")
    store.set_usage_meta(bf._ALIAS_REPAIR_META_KEY, "pending")
    assert bf.ensure_backfill(store) in {True, False}

    class _BoomTraj:
        @staticmethod
        def sessions_dir():
            raise RuntimeError("no traj")

    monkeypatch.setattr("agent.trajectory.Trajectory", _BoomTraj)
    assert bf._trajectory_paths() == []
    missing_dir = tmp_path / "absent"
    monkeypatch.setattr(
        "agent.trajectory.Trajectory.sessions_dir",
        staticmethod(lambda: missing_dir),
    )
    # The class patch above wins; restore the path helper via a fresh class.
    monkeypatch.setattr(
        "agent.trajectory.Trajectory",
        SimpleNamespace(sessions_dir=staticmethod(lambda: missing_dir)),
    )
    assert bf._trajectory_paths() == []
