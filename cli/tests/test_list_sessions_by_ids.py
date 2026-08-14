"""Tests for the bulk `list_sessions_by_ids` fetch used by cross-project
split groups on the frontend."""

from __future__ import annotations

from pathlib import Path

from agent_server.service import AgentService
from agent_server.store import AgentStore


def _mk_session(svc: AgentService, title: str, project_id: str | None = None) -> str:
    session = svc.create_session(
        title=title, workspace_path=None, project_id=project_id
    )
    return session.id


def test_returns_empty_for_empty_input(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    assert store.list_sessions_by_ids([]) == []


def test_returns_only_requested_ids(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    a = _mk_session(svc, "A")
    b = _mk_session(svc, "B")
    _mk_session(svc, "C")  # not requested
    got = store.list_sessions_by_ids([a, b])
    got_ids = {s.id for s in got}
    assert got_ids == {a, b}


def test_silently_skips_unknown_ids(tmp_path: Path, monkeypatch):
    """A stale localStorage group can reference a deleted chat — return
    the ids that resolve, ignore the rest, never raise."""
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    a = _mk_session(svc, "A")
    got = store.list_sessions_by_ids([a, "does-not-exist"])
    assert len(got) == 1
    assert got[0].id == a


def test_deduplicates_repeated_ids(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    a = _mk_session(svc, "A")
    got = store.list_sessions_by_ids([a, a, a])
    # SQL IN semantic: one row per matching id even if repeated.
    assert len([s for s in got if s.id == a]) == 1


def test_orders_by_updated_at_desc(tmp_path: Path, monkeypatch):
    """Matches `list_sessions` ordering so consumers can iterate
    consistently regardless of which path they used."""
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    a = _mk_session(svc, "A")
    b = _mk_session(svc, "B")
    # Force an update on `a` so its updated_at moves to now (after b).
    svc.update_session(
        session_id=a,
        title="A2",
        organize_label=None,
        update_organize_label=False,
    )
    got = store.list_sessions_by_ids([a, b])
    # `a` was updated last → should come first.
    assert got[0].id == a
    assert got[1].id == b


def test_ignores_blank_ids(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    a = _mk_session(svc, "A")
    got = store.list_sessions_by_ids(["", a, ""])
    assert [s.id for s in got] == [a]
