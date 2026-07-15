"""AgentStore durability: exclusive lock + optional corrupt-DB self-heal."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from agent_server.store import (
    AgentStore,
    AgentStoreCorruptedError,
    AgentStoreLockError,
)
from agent_server.store_heal import backup_path_for, refresh_healthy_backup


def test_store_refuses_malformed_database_without_heal(tmp_path: Path) -> None:
    path = tmp_path / "agent-server.db"
    path.write_bytes(b"not a sqlite database at all")

    with pytest.raises(AgentStoreCorruptedError, match="corrupt"):
        AgentStore(path, exclusive=False, verify_integrity=True)

    # Non-exclusive verify must not quarantine / invent a sibling recovered file.
    assert list(tmp_path.glob("agent-server.db.corrupt-*")) == []
    assert not Path(f"{path}.recovered").exists()
    assert path.read_bytes() == b"not a sqlite database at all"


def test_exclusive_auto_heals_from_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SANDWALK_DB_AUTO_HEAL", "1")
    path = tmp_path / "agent-server.db"

    healthy = AgentStore(path, exclusive=True)
    healthy.create_session(title="keep-me", workspace_path=None)
    healthy.close()
    refresh_healthy_backup(path)
    assert backup_path_for(path).exists()

    # Corrupt the primary while a healthy backup exists.
    path.write_bytes(b"totally broken")
    for suffix in ("-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)

    healed = AgentStore(path, exclusive=True)
    try:
        assert healed.last_heal_note is not None
        assert "backup" in healed.last_heal_note.lower() or "recover" in healed.last_heal_note.lower()
        sessions = healed.list_sessions()
        assert any(s.title == "keep-me" for s in sessions)
    finally:
        healed.close()

    assert list(tmp_path.glob("agent-server.db.corrupt-*"))


def test_auto_heal_disabled_still_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SANDWALK_DB_AUTO_HEAL", "0")
    path = tmp_path / "agent-server.db"
    path.write_bytes(b"not a sqlite database at all")

    with pytest.raises(AgentStoreCorruptedError, match="Auto-heal is disabled"):
        AgentStore(path, exclusive=True)

    assert path.exists()
    assert list(tmp_path.glob("agent-server.db.corrupt-*")) == []


def test_store_without_verify_skips_integrity_for_cli(tmp_path: Path) -> None:
    path = tmp_path / "agent.db"
    store = AgentStore(path, exclusive=False, verify_integrity=False)
    session = store.create_session(title="ok", workspace_path=None)
    assert store.get_session(session.id) is not None
    store.close()


def test_exclusive_lock_blocks_second_serve(tmp_path: Path) -> None:
    path = tmp_path / "agent.db"
    first = AgentStore(path, exclusive=True)
    try:
        with pytest.raises(AgentStoreLockError, match="already has this database open"):
            AgentStore(path, exclusive=True)
    finally:
        first.close()

    # After close, another exclusive open is allowed.
    second = AgentStore(path, exclusive=True)
    second.close()


def test_cli_open_allowed_while_server_holds_lock(tmp_path: Path) -> None:
    path = tmp_path / "agent.db"
    server = AgentStore(path, exclusive=True)
    try:
        cli = AgentStore(path, exclusive=False)
        session = cli.create_session(title="from-cli", workspace_path=None)
        assert server.get_session(session.id) is not None
        cli.close()
    finally:
        server.close()


def test_close_checkpoints_wal(tmp_path: Path) -> None:
    path = tmp_path / "agent.db"
    store = AgentStore(path, exclusive=True)
    store.create_session(title="checkpoint", workspace_path=None)
    store.close()
    wal = Path(f"{path}-wal")
    # Truncate checkpoint should leave an empty or absent WAL.
    assert (not wal.exists()) or wal.stat().st_size == 0


def test_refresh_healthy_backup_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "agent.db"
    store = AgentStore(path, exclusive=True)
    store.create_session(title="snap", workspace_path=None)
    store.close()
    refresh_healthy_backup(path)
    backup = backup_path_for(path)
    assert backup.exists()
    with sqlite3.connect(backup) as connection:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        assert row and row[0] == "ok"
