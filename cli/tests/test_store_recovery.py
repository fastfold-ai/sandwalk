"""AgentStore auto-repairs a malformed SQLite database on open."""

from __future__ import annotations

from pathlib import Path

from agent_server.store import AgentStore


def test_store_recovers_malformed_database(tmp_path: Path) -> None:
    path = tmp_path / "agent-server.db"
    path.write_bytes(b"not a sqlite database at all")

    store = AgentStore(path)
    session = store.create_session(title="Recovered", workspace_path=None)
    assert store.get_session(session.id) is not None
    assert any(path.parent.glob("agent-server.db.corrupt-*"))


def test_store_prefers_recovered_sibling(tmp_path: Path) -> None:
    path = tmp_path / "agent-server.db"
    good = AgentStore(path)
    session = good.create_session(title="Keep me", workspace_path=None)
    recovered = Path(f"{path}.recovered")
    recovered.write_bytes(path.read_bytes())

    path.write_bytes(b"CORRUPT")
    store = AgentStore(path)
    persisted = store.get_session(session.id)
    assert persisted is not None
    assert persisted.title == "Keep me"
