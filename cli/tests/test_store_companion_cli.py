"""UI and CLI are meant to be used together against one database.

The server holds an exclusive flock, but `sandwalk --resume` and every tool
that builds ``AgentStore()`` open the same file read-write alongside it. Those
shared opens must be safe both for concurrency and, more importantly, against
a mismatched ``-wal``: a read-write open in that state replays foreign frames
into the main file and destroys it.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from agent_server.store import AgentStore
from agent_server.store.errors import AgentStoreCorruptedError

from test_store_orphan_wal import make_db, plant_stale_wal, sessions


def test_shared_open_never_replays_a_mismatched_wal(tmp_path: Path) -> None:
    """A CLI start must not destroy the database it found in a bad pairing."""
    db = tmp_path / "agent.db"
    make_db(db, ["keep-1", "keep-2"])
    plant_stale_wal(db)
    assert sessions(db) == 2, "precondition: main file is intact"

    # However this turns out, the CLI must not have eaten the data.
    try:
        store = AgentStore(db)
        store.close()
    except AgentStoreCorruptedError:
        pass

    assert sessions(db) == 2, "a shared open destroyed the main database"


def test_cli_and_server_write_the_same_database(tmp_path: Path) -> None:
    """The companion case: server (exclusive) and CLI (shared) both writing."""
    db = tmp_path / "agent.db"
    server = AgentStore(db, exclusive=True)
    cli = AgentStore(db)
    try:
        for index in range(25):
            server.create_session(title=f"ui-{index}", workspace_path=None)
            cli.create_session(title=f"cli-{index}", workspace_path=None)
        titles = {session.title for session in server.list_sessions()}
        assert "ui-24" in titles and "cli-24" in titles
        # Each side sees the other's writes; there is one shared database.
        assert titles == {f"ui-{i}" for i in range(25)} | {
            f"cli-{i}" for i in range(25)
        }
        assert {s.title for s in cli.list_sessions()} == titles
    finally:
        cli.close()
        server.close()


def test_concurrent_writers_do_not_error_on_lock(tmp_path: Path) -> None:
    """busy_timeout must absorb contention rather than surfacing 'locked'."""
    db = tmp_path / "agent.db"
    server = AgentStore(db, exclusive=True)
    cli = AgentStore(db)
    errors: list[Exception] = []

    def hammer(store: AgentStore, tag: str) -> None:
        try:
            for index in range(40):
                store.create_session(title=f"{tag}-{index}", workspace_path=None)
        except Exception as exc:  # noqa: BLE001 - recorded for the assertion
            errors.append(exc)

    threads = [
        threading.Thread(target=hammer, args=(server, "ui")),
        threading.Thread(target=hammer, args=(cli, "cli")),
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
        assert not errors, f"concurrent writes failed: {errors[:3]}"
        assert len(server.list_sessions()) == 80
    finally:
        cli.close()
        server.close()


def test_shared_close_leaves_the_servers_journal_alone(tmp_path: Path) -> None:
    """A CLI exiting must not checkpoint or unlink the running server's WAL."""
    db = tmp_path / "agent.db"
    server = AgentStore(db, exclusive=True)
    try:
        server.create_session(title="before", workspace_path=None)
        cli = AgentStore(db)
        cli.create_session(title="from-cli", workspace_path=None)
        cli.close()

        # The server keeps working and still sees everything.
        server.create_session(title="after", workspace_path=None)
        titles = {session.title for session in server.list_sessions()}
        assert titles == {"before", "from-cli", "after"}
    finally:
        server.close()
    assert sessions(db) == 3


def test_second_server_is_refused_not_corrupted(tmp_path: Path) -> None:
    """Two exclusive owners would be a real hazard; the flock must refuse."""
    from agent_server.store.errors import AgentStoreLockError

    db = tmp_path / "agent.db"
    first = AgentStore(db, exclusive=True)
    try:
        first.create_session(title="owner", workspace_path=None)
        with pytest.raises(AgentStoreLockError):
            AgentStore(db, exclusive=True)
    finally:
        first.close()
    assert sessions(db) == 1
    # Once released, a new server may take over.
    second = AgentStore(db, exclusive=True)
    try:
        assert len(second.list_sessions()) == 1
    finally:
        second.close()


def test_server_recovers_when_a_bad_wal_appears_at_runtime(tmp_path: Path) -> None:
    """A stale WAL landing beside a live server must not take it down."""
    db = tmp_path / "agent.db"
    server = AgentStore(db, exclusive=True)
    try:
        server.create_session(title="before", workspace_path=None)
        # Something drops a foreign WAL next to the database mid-run.
        plant_stale_wal(db)

        # The next operation heals rather than failing or losing rows.
        titles = {session.title for session in server.list_sessions()}
        assert "before" in titles
        server.create_session(title="after", workspace_path=None)
        assert {"before", "after"} <= {s.title for s in server.list_sessions()}
    finally:
        server.close()

    assert not list(tmp_path.glob("agent.db.corrupt-*")), "fell back to a backup"
    assert sessions(db) == 2


def test_shared_open_survives_a_healthy_wal(tmp_path: Path) -> None:
    """The guard must not trip on the ordinary case of a live WAL."""
    db = tmp_path / "agent.db"
    server = AgentStore(db, exclusive=True)
    try:
        server.create_session(title="live", workspace_path=None)
        holder = sqlite3.connect(db)
        holder.execute("PRAGMA journal_mode=WAL")
        holder.execute("PRAGMA wal_autocheckpoint=0")
        holder.execute(
            "INSERT INTO sessions (id, title, status, created_at, updated_at)"
            " VALUES ('x1', 'uncheckpointed', 'idle', datetime('now'), datetime('now'))"
        )
        holder.commit()
        assert Path(f"{db}-wal").exists()
        try:
            cli = AgentStore(db)
            titles = {s.title for s in cli.list_sessions()}
            cli.close()
        finally:
            holder.close()
        assert {"live", "uncheckpointed"} <= titles
    finally:
        server.close()
