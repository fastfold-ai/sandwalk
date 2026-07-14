"""AgentStore durability: no silent rewrite; exclusive serve lock."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_server.store import (
    AgentStore,
    AgentStoreCorruptedError,
    AgentStoreLockError,
)


def test_store_refuses_malformed_database(tmp_path: Path) -> None:
    path = tmp_path / "agent-server.db"
    path.write_bytes(b"not a sqlite database at all")

    with pytest.raises(AgentStoreCorruptedError, match="corrupt"):
        AgentStore(path, verify_integrity=True)

    # Must not quarantine / wipe / invent a sibling recovered file.
    assert list(tmp_path.glob("agent-server.db.corrupt-*")) == []
    assert not Path(f"{path}.recovered").exists()
    assert path.read_bytes() == b"not a sqlite database at all"


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
