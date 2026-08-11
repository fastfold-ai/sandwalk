"""Shutdown must never discard committed data.

Regression for silent data loss on restart: ``close()`` used to delete the
``-wal`` sidecar even when the checkpoint had failed, throwing away committed
transactions and leaving the main file malformed — which the next startup
"healed" by restoring an older backup.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from agent_server.store import AgentStore


def wal_path(db: Path) -> Path:
    return db.with_name(f"{db.name}-wal")


def test_committed_data_survives_a_failed_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "agent.db"
    store = AgentStore(db, exclusive=True)
    store.upsert_slack_workspace(team_id="T1", mode="socket", team_name="Acme")

    # A second reader keeps the WAL from being auto-checkpointed, so committed
    # pages are still only in the sidecar when shutdown runs — the exact state
    # that used to lose data.
    reader = sqlite3.connect(db, timeout=5)
    reader.execute("SELECT COUNT(*) FROM slack_workspaces").fetchone()
    assert wal_path(db).exists()

    # ...and the checkpoint fails because of that reader.
    def boom() -> sqlite3.Connection:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(store, "_open_connection", boom)
    store.close()

    # The WAL must survive an unsuccessful checkpoint; SQLite replays it later.
    assert wal_path(db).exists(), "un-checkpointed WAL was deleted"
    reader.close()

    reopened = AgentStore(db, exclusive=True)
    try:
        workspace = reopened.get_slack_workspace("T1")
        assert workspace is not None, "committed workspace was lost on restart"
        assert workspace.team_name == "Acme"
    finally:
        reopened.close()


def test_clean_close_folds_the_wal_away(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    store = AgentStore(db, exclusive=True)
    store.create_session(title="Kept", workspace_path=None)
    store.close()

    # A successful checkpoint means the next process cannot inherit a stale WAL.
    assert not wal_path(db).exists()

    reopened = AgentStore(db, exclusive=True)
    try:
        assert [item.title for item in reopened.list_sessions()] == ["Kept"]
    finally:
        reopened.close()


def test_operations_do_not_leave_connections_open(tmp_path: Path) -> None:
    """A leaked reader is what made the shutdown checkpoint fail."""
    db = tmp_path / "agent.db"
    store = AgentStore(db, exclusive=True)
    try:
        for index in range(25):
            session = store.create_session(title=f"S{index}", workspace_path=None)
            store.add_message(session_id=session.id, role="user", content="hi")
            store.list_sessions()

        # With connections closed, an exclusive checkpoint succeeds. If any were
        # still open this raises "database is locked".
        connection = sqlite3.connect(db, timeout=1)
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            connection.close()
    finally:
        store.close()


def test_repeated_restarts_keep_data(tmp_path: Path) -> None:
    """Restarting the server is routine and must be lossless."""
    db = tmp_path / "agent.db"
    for index in range(5):
        store = AgentStore(db, exclusive=True)
        store.upsert_slack_workspace(team_id=f"T{index}", mode="socket")
        store.close()

    final = AgentStore(db, exclusive=True)
    try:
        teams = sorted(item.team_id for item in final.list_slack_workspaces())
        assert teams == ["T0", "T1", "T2", "T3", "T4"]
    finally:
        final.close()
