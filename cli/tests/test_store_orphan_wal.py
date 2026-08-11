"""A foreign -wal beside a healthy main file must not cost the user any data.

Reproduces the failure seen in the wild: ``agent-server.db`` written today with
an ``agent-server.db-wal`` from twelve days earlier. Every open reported
"database disk image is malformed", the heal restored a backup from the last
boot, and the stale sidecar survived the restore — so the next start lost
another session's worth of work.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from agent_server.store import AgentStore
from agent_server.store_heal import repair_mismatched_sidecars


def sessions(db: Path) -> int:
    connection = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
    finally:
        connection.close()


def make_db(path: Path, titles: list[str]) -> None:
    store = AgentStore(path, exclusive=True)
    try:
        for title in titles:
            store.create_session(title=title, workspace_path=None)
    finally:
        store.close()


def plant_stale_wal(db: Path) -> None:
    """Pair the main file with a -wal from an earlier generation of itself.

    This is the shape seen in the wild: a main file written today next to a
    WAL from twelve days earlier, whose frames describe page layouts the
    current file no longer has.
    """
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        # Keep frames in the WAL instead of folding them into the main file.
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("CREATE TABLE filler (id INTEGER PRIMARY KEY, blob TEXT)")
        for _ in range(800):
            connection.execute("INSERT INTO filler (blob) VALUES (?)", ("x" * 400,))
        connection.commit()
        # Read it while open; closing checkpoints the WAL away.
        wal = Path(f"{db}-wal")
        if not wal.exists():  # pragma: no cover - defensive
            pytest.skip("could not produce a non-empty WAL")
        stale = wal.read_bytes()
    finally:
        connection.close()

    # Move the main file on to a different generation entirely.
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("DROP TABLE filler")
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()

    Path(f"{db}-wal").write_bytes(stale)


def test_foreign_wal_makes_a_healthy_db_look_corrupt(tmp_path: Path) -> None:
    """Guards the premise: without the sidecar the file is provably fine."""
    db = tmp_path / "agent.db"
    make_db(db, ["a", "b", "c"])
    plant_stale_wal(db)

    with pytest.raises(sqlite3.DatabaseError, match="malformed"):
        connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()

    assert sessions(db) == 3


def test_orphan_wal_is_dropped_without_losing_data(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    make_db(db, ["a", "b", "c"])
    plant_stale_wal(db)

    note = repair_mismatched_sidecars(db)

    assert note is not None and "all data kept" in note
    assert sessions(db) == 3
    # Preserved for investigation rather than deleted.
    assert list(tmp_path.glob("agent.db.orphan-*"))


def test_store_opens_and_keeps_everything(tmp_path: Path) -> None:
    """The end-to-end symptom: restart must not roll back to an old backup."""
    db = tmp_path / "agent.db"
    make_db(db, ["old-1", "old-2"])

    # Work done after the last backup — the Slack workspace that kept vanishing.
    store = AgentStore(db, exclusive=True)
    try:
        store.create_session(title="connected-slack", workspace_path=None)
    finally:
        store.close()

    plant_stale_wal(db)

    store = AgentStore(db, exclusive=True)
    try:
        titles = {session.title for session in store.list_sessions()}
    finally:
        store.close()

    assert "connected-slack" in titles, "restart rolled back post-backup work"
    assert titles == {"old-1", "old-2", "connected-slack"}
    # A false corruption diagnosis must not have quarantined anything.
    assert not list(tmp_path.glob("agent.db.corrupt-*"))


def test_a_healthy_wal_is_never_discarded(tmp_path: Path) -> None:
    """The rescue must not throw away a live WAL holding real commits."""
    db = tmp_path / "agent.db"
    make_db(db, ["a"])

    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        # Uncheckpointed commits: these live only in the -wal right now.
        connection.execute("PRAGMA wal_autocheckpoint=0")
        for index in range(200):
            connection.execute(
                "INSERT INTO sessions (id, title, status, created_at, updated_at)"
                " VALUES (?, ?, 'idle', datetime('now'), datetime('now'))",
                (f"id-{index}", f"kept-{index}"),
            )
        connection.commit()
        assert Path(f"{db}-wal").exists()

        # A genuine WAL must be left alone even while another handle holds it.
        assert repair_mismatched_sidecars(db) is None
        assert Path(f"{db}-wal").exists()
    finally:
        connection.close()

    assert not list(tmp_path.glob("agent.db.orphan-*"))
    store = AgentStore(db, exclusive=True)
    try:
        titles = {session.title for session in store.list_sessions()}
    finally:
        store.close()
    assert "kept-199" in titles, "a healthy WAL's commits were dropped"


def test_unknown_probe_result_leaves_sidecars_alone(tmp_path: Path) -> None:
    """"Cannot tell" must never be treated as "corrupt"."""
    db = tmp_path / "agent.db"
    make_db(db, ["a"])
    Path(f"{db}-wal").write_bytes(b"")

    import agent_server.store_heal as heal

    original = heal.readonly_integrity_ok
    heal.readonly_integrity_ok = lambda path: None
    try:
        assert heal.repair_mismatched_sidecars(db) is None
    finally:
        heal.readonly_integrity_ok = original
    assert Path(f"{db}-wal").exists()


def test_genuine_corruption_still_heals(tmp_path: Path) -> None:
    """The rescue must not swallow real damage to the main file."""
    db = tmp_path / "agent.db"
    make_db(db, ["a", "b"])

    # Scribble over the middle of the main file, then add a sidecar.
    raw = bytearray(db.read_bytes())
    for offset in range(4096, min(len(raw), 40960)):
        raw[offset] = 0x5A
    db.write_bytes(bytes(raw))
    Path(f"{db}-wal").write_bytes(b"\x00" * 64)

    # Main file is not healthy on its own, so this must decline to "fix" it.
    assert repair_mismatched_sidecars(db) is None
