"""A shared (non-exclusive) store must never disturb the exclusive owner.

Regression: ``close()`` used to checkpoint, switch the journal to DELETE and
delete the ``-wal``/``-shm`` sidecars regardless of ownership. Short-lived
shared opens — CLI helpers, tool calls, the HITL trust check — therefore
corrupted the database out from under a running server.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from agent_server.store import AgentStore


def journal_mode(db: Path) -> str:
    connection = sqlite3.connect(db)
    try:
        return str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    finally:
        connection.close()


def test_shared_close_leaves_the_journal_alone(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    server = AgentStore(db, exclusive=True)
    try:
        server.create_session(title="Live", workspace_path=None)
        assert journal_mode(db) == "wal"

        # A tool opens the store briefly, exactly like tools/slack.py does.
        shared = AgentStore(db)
        shared.get_session("nope")
        shared.close()

        # The owner's journal mode must be untouched. (The -wal file itself
        # comes and goes: SQLite auto-checkpoints when the last connection
        # closes, so its presence is not a useful signal.)
        assert journal_mode(db) == "wal"

        # ...and the server must still be able to read and write.
        server.create_session(title="After", workspace_path=None)
        assert {item.title for item in server.list_sessions()} == {"Live", "After"}
    finally:
        server.close()


def test_repeated_shared_opens_do_not_corrupt(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    server = AgentStore(db, exclusive=True)
    try:
        session = server.create_session(title="Live", workspace_path=None)

        # Every Slack tool call and approval check opens one of these.
        for index in range(20):
            shared = AgentStore(db)
            shared.get_session(session.id)
            shared.close()
            server.add_message(
                session_id=session.id, role="user", content=f"m{index}"
            )

        connection = sqlite3.connect(db)
        try:
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            connection.close()
        assert len(server.list_messages(session.id)) == 20
    finally:
        server.close()


def test_exclusive_close_still_folds_the_wal(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    store = AgentStore(db, exclusive=True)
    store.create_session(title="Kept", workspace_path=None)
    store.close()

    # The owner keeps its cleanup duty.
    assert not Path(f"{db}-wal").exists()
