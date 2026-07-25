"""Self-heal must never trade data for a clean integrity check.

Regressions guarded here:
  * quarantine copies rather than moves, so a kill mid-recovery cannot leave
    the machine with no database at all;
  * a "repair" that would drop most rows is refused instead of applied;
  * quarantine copies are pruned so they do not accumulate forever.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from agent_server.store_heal import (
    data_volume,
    prune_quarantines,
    quarantine_database,
    replacement_loses_data,
)


def make_db(path: Path, *, sessions: int) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS library_items (id TEXT PRIMARY KEY);
            """
        )
        connection.executemany(
            "INSERT INTO sessions(id) VALUES (?)",
            [(f"s{index}",) for index in range(sessions)],
        )
        connection.commit()
    finally:
        connection.close()


def test_quarantine_leaves_the_original_in_place(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    make_db(db, sessions=3)

    quarantined = quarantine_database(db)

    # Moving the original was the bug: a kill during the 120s recover window
    # would leave no database at all.
    assert db.exists(), "live database was moved away during quarantine"
    assert quarantined.exists()
    assert data_volume(db) == 3
    assert data_volume(quarantined) == 3


def test_quarantine_copies_sidecars_too(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    make_db(db, sessions=1)
    Path(f"{db}-wal").write_bytes(b"stale")

    quarantined = quarantine_database(db)
    assert Path(f"{quarantined}-wal").exists()
    assert Path(f"{db}-wal").exists()


def test_data_volume_reports_none_for_unreadable(tmp_path: Path) -> None:
    missing = tmp_path / "nope.db"
    assert data_volume(missing) is None

    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database at all")
    assert data_volume(junk) is None


def test_replacement_that_drops_most_rows_is_flagged(tmp_path: Path) -> None:
    current = tmp_path / "current.db"
    candidate = tmp_path / "candidate.db"
    make_db(current, sessions=300)
    make_db(candidate, sessions=10)

    loss = replacement_loses_data(current, candidate)
    assert loss is not None
    assert "10 of 300" in loss


def test_small_losses_are_tolerated(tmp_path: Path) -> None:
    current = tmp_path / "current.db"
    candidate = tmp_path / "candidate.db"
    make_db(current, sessions=300)
    make_db(candidate, sessions=299)

    # Recovery legitimately drops the odd unreadable row; that must not block
    # an otherwise good repair.
    assert replacement_loses_data(current, candidate) is None


def test_bigger_replacement_is_fine(tmp_path: Path) -> None:
    current = tmp_path / "current.db"
    candidate = tmp_path / "candidate.db"
    make_db(current, sessions=5)
    make_db(candidate, sessions=50)

    assert replacement_loses_data(current, candidate) is None


def test_guard_is_skipped_when_current_is_unreadable(tmp_path: Path) -> None:
    current = tmp_path / "current.db"
    candidate = tmp_path / "candidate.db"
    current.write_bytes(b"shredded")
    make_db(candidate, sessions=2)

    # Nothing to compare against, so recovery should be allowed to proceed.
    assert replacement_loses_data(current, candidate) is None


def test_prune_keeps_only_the_newest(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    make_db(db, sessions=1)

    for index in range(9):
        copy = tmp_path / f"agent.db.corrupt-2026010{index}-000000"
        copy.write_bytes(b"old")
        Path(f"{copy}-wal").write_bytes(b"old")

    removed = prune_quarantines(db, keep=3)
    assert removed == 6

    remaining = sorted(
        item.name
        for item in tmp_path.glob("agent.db.corrupt-*")
        if not item.name.endswith(("-wal", "-shm"))
    )
    assert len(remaining) == 3
    # Newest survive.
    assert remaining[-1].endswith("20260108-000000")
    # Sidecars go with them.
    assert not Path(f"{tmp_path}/agent.db.corrupt-20260100-000000-wal").exists()


def test_prune_is_safe_with_nothing_to_do(tmp_path: Path) -> None:
    db = tmp_path / "agent.db"
    make_db(db, sessions=1)
    assert prune_quarantines(db, keep=5) == 0
