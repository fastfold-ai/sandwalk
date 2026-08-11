"""SQLite integrity/size probe for ``~/.sandwalk/agent-server.db``."""

from __future__ import annotations

from pathlib import Path

from agent_server.models import StorageDatabaseProbe
from agent_server.storage_service.path_size import _path_size_bytes


def probe_agent_database(home: Path) -> StorageDatabaseProbe:
    """Measure size + integrity for the exclusive agent SQLite store."""
    import sqlite3

    from agent_server.store_heal import auto_heal_enabled, backup_path_for, integrity_ok

    db_path = (home / "agent-server.db").expanduser()
    wal_path = Path(f"{db_path}-wal")
    shm_path = Path(f"{db_path}-shm")
    backup = backup_path_for(db_path)
    quarantine_count = len(
        [
            p
            for p in home.glob("agent-server.db.corrupt-*")
            if p.is_file() and "-wal" not in p.name and "-shm" not in p.name
        ]
    )

    integrity = "missing"
    page_count: int | None = None
    page_size: int | None = None
    journal_mode: str | None = None
    session_count: int | None = None
    message_count: int | None = None

    if db_path.exists():
        try:
            with sqlite3.connect(db_path, timeout=5) as connection:
                row = connection.execute("PRAGMA integrity_check").fetchone()
                integrity = str(row[0]) if row else "unknown"
                page_count_row = connection.execute("PRAGMA page_count").fetchone()
                page_size_row = connection.execute("PRAGMA page_size").fetchone()
                journal_row = connection.execute("PRAGMA journal_mode").fetchone()
                page_count = int(page_count_row[0]) if page_count_row else None
                page_size = int(page_size_row[0]) if page_size_row else None
                journal_mode = str(journal_row[0]) if journal_row else None
                try:
                    session_count = int(
                        connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
                    )
                    message_count = int(
                        connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
                    )
                except sqlite3.Error:
                    session_count = None
                    message_count = None
        except sqlite3.DatabaseError as exc:
            integrity = str(exc)

    backup_integrity: str | None
    if not backup.exists():
        backup_integrity = "missing"
    elif integrity_ok(backup):
        backup_integrity = "ok"
    else:
        backup_integrity = "corrupt"

    return StorageDatabaseProbe(
        path=str(db_path),
        exists=db_path.exists(),
        bytes=_path_size_bytes(db_path) if db_path.exists() else 0,
        wal_bytes=_path_size_bytes(wal_path) if wal_path.exists() else 0,
        shm_bytes=_path_size_bytes(shm_path) if shm_path.exists() else 0,
        integrity=integrity,
        page_count=page_count,
        page_size=page_size,
        journal_mode=journal_mode,
        session_count=session_count,
        message_count=message_count,
        backup_path=str(backup) if backup.exists() else None,
        backup_bytes=_path_size_bytes(backup) if backup.exists() else 0,
        backup_integrity=backup_integrity,
        auto_heal_enabled=auto_heal_enabled(),
        quarantine_count=quarantine_count,
    )
