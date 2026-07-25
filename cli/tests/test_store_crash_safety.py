"""The store must survive a hard kill without losing or corrupting data.

SQLite in WAL mode with ``synchronous=FULL`` is crash-safe by design, so a
SIGKILL should be a non-event. Corruption only happens when something violates
SQLite's assumptions — historically, this store deleting the ``-wal``/``-shm``
files behind SQLite's back on every close.
"""

from __future__ import annotations

import os
import signal
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[1] / "src")


def counts(db: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {
            "sessions": connection.execute(
                "SELECT COUNT(*) FROM sessions"
            ).fetchone()[0]
        }
    finally:
        connection.close()


def integrity(db: Path) -> str:
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        connection.close()


def writer_script(db: Path) -> str:
    return textwrap.dedent(
        f"""
        import sys, time
        from pathlib import Path
        sys.path.insert(0, {SRC!r})
        from agent_server.store import AgentStore

        store = AgentStore(Path({str(db)!r}), exclusive=True)
        for index in range(10_000):
            store.create_session(title=f"s{{index}}", workspace_path=None)
            print(index, flush=True)
            time.sleep(0.01)
        """
    ).strip()


def test_sigkill_mid_write_does_not_corrupt(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    script = tmp_path / "writer.py"
    script.write_text(writer_script(db))

    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # Let it commit a few rows, then kill it as violently as possible.
        assert proc.stdout is not None
        for _ in range(5):
            assert proc.stdout.readline(), "writer produced no output"
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=15)
    finally:
        if proc.poll() is None:  # pragma: no cover - defensive
            proc.kill()
            proc.wait(timeout=5)

    assert integrity(db) == "ok", "hard kill left a malformed database"
    # Committed rows survive; SQLite replays the WAL on the next open.
    assert counts(db)["sessions"] >= 5


def test_reopen_after_sigkill_needs_no_heal(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    script = tmp_path / "writer.py"
    script.write_text(writer_script(db))

    proc = subprocess.Popen(
        [sys.executable, str(script)], stdout=subprocess.PIPE, text=True
    )
    assert proc.stdout is not None
    for _ in range(5):
        proc.stdout.readline()
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=15)

    # A stale lock file must not block the next start either.
    from agent_server.store import AgentStore

    store = AgentStore(db, exclusive=True)
    try:
        # No heal note means the database opened cleanly, with no quarantine.
        assert store.last_heal_note is None
        assert not list(tmp_path.glob("*.corrupt-*"))
        before = len(store.list_sessions())
        store.create_session(title="after-crash", workspace_path=None)
        assert len(store.list_sessions()) == before + 1
    finally:
        store.close()


def test_close_leaves_sqlite_to_manage_its_own_wal(tmp_path: Path) -> None:
    """Never unlink -wal/-shm: a reader still holding them sees corruption."""
    db = tmp_path / "agent.db"
    from agent_server.store import AgentStore

    store = AgentStore(db, exclusive=True)
    store.create_session(title="Live", workspace_path=None)

    # Another process (CLI, tool) holds the database open across our close.
    reader = sqlite3.connect(db, timeout=5)
    reader.execute("SELECT COUNT(*) FROM sessions").fetchone()

    store.close()

    # The reader must still work — deleting its -shm out from under it is
    # exactly what produced "disk image is malformed".
    assert reader.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    reader.close()
    assert integrity(db) == "ok"


def test_backup_age_is_reported(tmp_path: Path) -> None:
    from agent_server.store import AgentStore
    from agent_server.store_heal import backup_age_seconds, refresh_healthy_backup

    db = tmp_path / "agent.db"
    store = AgentStore(db, exclusive=True)
    try:
        store.create_session(title="One", workspace_path=None)
        refresh_healthy_backup(db)
        age = backup_age_seconds(db)
        assert age is not None and age < 30
    finally:
        store.close()

    assert backup_age_seconds(tmp_path / "missing.db") is None


def test_periodic_refresh_captures_recent_writes(tmp_path: Path) -> None:
    """A heal must not roll back hours — the snapshot has to keep up."""
    from agent_server.store import AgentStore
    from agent_server.store_heal import backup_path_for, refresh_healthy_backup

    db = tmp_path / "agent.db"
    store = AgentStore(db, exclusive=True)
    try:
        store.create_session(title="Boot", workspace_path=None)
        refresh_healthy_backup(db)

        # Work done after boot, exactly like connecting a Slack workspace.
        store.create_session(title="Later", workspace_path=None)
        time.sleep(0.01)
        refresh_healthy_backup(db)

        titles = set()
        connection = sqlite3.connect(f"file:{backup_path_for(db)}?mode=ro", uri=True)
        try:
            titles = {row[0] for row in connection.execute("SELECT title FROM sessions")}
        finally:
            connection.close()
        assert "Later" in titles
    finally:
        store.close()
