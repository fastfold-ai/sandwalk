"""Database heal helpers: backup, quarantine, recover, and volume checks."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from agent_server import store_heal as heal


def _db(path: Path, rows: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE sessions (id TEXT)")
        conn.execute("CREATE TABLE messages (id TEXT)")
        conn.execute("CREATE TABLE library_items (id TEXT)")
        for index in range(rows):
            conn.execute("INSERT INTO sessions (id) VALUES (?)", (f"s{index}",))
        conn.commit()
    return path


def test_heal_file_helpers(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDWALK_DB_AUTO_HEAL", "off")
    assert heal.auto_heal_enabled() is False
    monkeypatch.setenv("SANDWALK_DB_AUTO_HEAL", "1")
    assert heal.auto_heal_enabled() is True

    db = _db(tmp_path / "agent.db", rows=30)
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    missing = tmp_path / "missing.db"
    assert heal.integrity_ok(empty) is False
    assert heal.integrity_ok(db) is True
    assert heal.integrity_ok(db, isolate_main=True) is True
    assert heal.readonly_readable(empty) is None
    assert heal.readonly_readable(db) is True
    assert heal.readonly_integrity_ok(missing) is None
    assert heal.readonly_integrity_ok(db) is True
    assert heal.data_volume(missing) is None
    assert heal.data_volume(db) == 30
    junk = tmp_path / "junk.db"
    junk.write_text("not a database")
    assert heal.data_volume(junk) is None
    assert heal.readonly_readable(junk) is False

    side = Path(f"{db}-wal")
    side.write_text("wal")
    assert heal.database_fingerprint(db)[2] > 0
    heal.clear_wal_sidecars(db)
    assert not side.exists()

    dest = tmp_path / "installed.db"
    heal.install_database_file(db, dest)
    assert heal.integrity_ok(dest) is True
    assert heal.backup_age_seconds(db) is None
    backup = heal.backup_path_for(db)
    backup.write_bytes(db.read_bytes())
    assert heal.backup_age_seconds(db) == 0 or heal.backup_age_seconds(db) >= 0

    small = _db(tmp_path / "small.db", rows=1)
    assert "would survive" in (heal.replacement_loses_data(db, small) or "")
    assert heal.replacement_loses_data(db, db) is None
    assert heal.replacement_loses_data(missing, db) is None

    quarantined = heal.quarantine_database(db)
    assert quarantined.exists()
    again = heal.quarantine_database(db)
    assert again != quarantined
    assert heal.prune_quarantines(db, keep=1) >= 1

    refreshed = heal.refresh_healthy_backup(db, force=True)
    assert refreshed is True
    assert heal.refresh_healthy_backup(db, force=False) in {True, False}
    assert heal.restore_from_backup(tmp_path / "restored.db", heal.backup_path_for(db)) is True
    assert heal.restore_from_backup(tmp_path / "nope.db", empty) is False


def test_recover_via_sqlite_cli(tmp_path, monkeypatch):
    db = _db(tmp_path / "corrupt.db")
    dest = tmp_path / "out.db"
    monkeypatch.setattr(
        heal.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "CREATE TABLE t(id INT);", ""),
    )
    assert heal.recover_via_sqlite_cli(db, dest) is True

    monkeypatch.setattr(
        heal.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", "nope"),
    )
    assert heal.recover_via_sqlite_cli(db, tmp_path / "bad.db") is False

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="sqlite3", timeout=1)

    monkeypatch.setattr(heal.subprocess, "run", _timeout)
    assert heal.recover_via_sqlite_cli(db, tmp_path / "slow.db") is False

    missing = tmp_path / "absent.db"

    def _no_copy(*args, **kwargs):
        raise OSError("no")

    monkeypatch.setattr(heal.shutil, "copy2", _no_copy)
    assert heal.recover_via_sqlite_cli(missing, tmp_path / "copy-fail.db") is False


def test_heal_failure_branches(tmp_path, monkeypatch):
    db = _db(tmp_path / "agent.db", rows=2)
    real_copy = heal.shutil.copy2

    def _copy(src, dst, *args, **kwargs):
        if ".icheck-" in str(dst):
            raise OSError("isolate")
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(heal.shutil, "copy2", _copy)
    assert heal.integrity_ok(db, isolate_main=True) is False
    monkeypatch.setattr(heal.shutil, "copy2", real_copy)

    live = _db(tmp_path / "live.db")
    Path(f"{live}-wal").write_bytes(b"foreign-wal")
    note = heal.repair_mismatched_sidecars(live)
    assert note is None or "mismatched" in note
    assert heal.repair_mismatched_sidecars(tmp_path / "no-side.db") is None

    bare = tmp_path / "bare.db"
    with sqlite3.connect(bare) as conn:
        conn.execute("CREATE TABLE other (id TEXT)")
    assert heal.data_volume(bare) is None
    assert heal.refresh_healthy_backup(tmp_path / "garbage.db", force=True) is None
    (tmp_path / "garbage.db").write_text("nope")
    assert heal.refresh_healthy_backup(tmp_path / "garbage.db", force=True) is None

    monkeypatch.setattr(
        heal.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "this is not sql;", ""),
    )
    assert heal.recover_via_sqlite_cli(db, tmp_path / "sql.db") is False
    monkeypatch.setattr(
        heal.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "CREATE TABLE t(id INT);", ""),
    )
    monkeypatch.setattr(heal, "integrity_ok", lambda *a, **k: False)
    assert heal.recover_via_sqlite_cli(db, tmp_path / "bad-check.db") is False

    monkeypatch.setattr(heal, "integrity_ok", lambda *a, **k: True)

    def _install_fails(*args, **kwargs):
        raise OSError("disk")

    monkeypatch.setattr(heal, "install_database_file", _install_fails)
    backup = _db(tmp_path / "backup.db")
    assert heal.restore_from_backup(tmp_path / "restored.db", backup) is False
