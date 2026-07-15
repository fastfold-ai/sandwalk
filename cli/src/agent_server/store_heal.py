"""Safe self-heal for a corrupt agent-server SQLite database.

Designed for exclusive serve open (flock already held): quarantine the bad
file, try ``sqlite3 .recover``, then fall back to the last healthy backup.
Never silently wipes to an empty DB without attempting recovery first.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def auto_heal_enabled() -> bool:
    raw = (os.environ.get("SANDWALK_DB_AUTO_HEAL") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def backup_path_for(db_path: Path) -> Path:
    return db_path.with_name(f"{db_path.name}.recovered")


def integrity_ok(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with sqlite3.connect(path, timeout=5) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            return bool(row and str(row[0]) == "ok")
    except sqlite3.DatabaseError:
        return False


def quarantine_database(db_path: Path) -> Path:
    """Move corrupt DB (+ WAL/SHM) aside; return the quarantined main path."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = db_path.with_name(f"{db_path.name}.corrupt-{stamp}")
    # Avoid clobbering an existing quarantine with the same second.
    n = 1
    while target.exists():
        target = db_path.with_name(f"{db_path.name}.corrupt-{stamp}-{n}")
        n += 1
    db_path.rename(target)
    for suffix in ("-wal", "-shm"):
        side = Path(f"{db_path}{suffix}")
        if side.exists():
            side.rename(Path(f"{target}{suffix}"))
    logger.warning("Quarantined corrupt agent DB → %s", target)
    return target


def recover_via_sqlite_cli(corrupt_path: Path, dest: Path) -> bool:
    """Use ``sqlite3 .recover`` when available; verify the result."""
    dest.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(f"{dest}{suffix}").unlink(missing_ok=True)
    try:
        completed = subprocess.run(
            ["sqlite3", str(corrupt_path), ".recover"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("sqlite3 .recover unavailable/failed: %s", exc)
        return False
    if completed.returncode != 0 or not (completed.stdout or "").strip():
        err = (completed.stderr or "").strip()[:300]
        logger.warning("sqlite3 .recover failed (code=%s): %s", completed.returncode, err)
        return False
    try:
        with sqlite3.connect(dest) as connection:
            connection.executescript(completed.stdout)
            connection.commit()
    except sqlite3.Error as exc:
        logger.warning("Applying .recover SQL failed: %s", exc)
        dest.unlink(missing_ok=True)
        return False
    if not integrity_ok(dest):
        dest.unlink(missing_ok=True)
        return False
    return True


def restore_from_backup(db_path: Path, backup: Path) -> bool:
    if not integrity_ok(backup):
        return False
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    shutil.copy2(backup, db_path)
    # Fresh WAL/SHM after restore.
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    if not integrity_ok(db_path):
        return False
    logger.warning("Restored agent DB from healthy backup %s", backup)
    return True


def refresh_healthy_backup(db_path: Path) -> None:
    """Copy a verified DB to ``*.recovered`` for the next self-heal."""
    if not integrity_ok(db_path):
        return
    backup = backup_path_for(db_path)
    tmp = backup.with_suffix(backup.suffix + ".tmp")
    try:
        # Online backup API copies a consistent snapshot even under WAL.
        with sqlite3.connect(db_path, timeout=30) as src:
            with sqlite3.connect(tmp) as dst:
                src.backup(dst)
        if not integrity_ok(tmp):
            tmp.unlink(missing_ok=True)
            return
        tmp.replace(backup)
        for suffix in ("-wal", "-shm"):
            Path(f"{backup}{suffix}").unlink(missing_ok=True)
            Path(f"{tmp}{suffix}").unlink(missing_ok=True)
        logger.info("Refreshed healthy agent DB backup → %s", backup)
    except (OSError, sqlite3.Error) as exc:
        logger.warning("Could not refresh DB backup: %s", exc)
        tmp.unlink(missing_ok=True)


def attempt_self_heal(db_path: Path, *, detail: str) -> str:
    """Quarantine + recover/backup. Returns a human note on success; raises on failure."""
    if not auto_heal_enabled():
        raise RuntimeError(
            f"Agent store database is corrupt ({detail}): {db_path}. "
            "Auto-heal is disabled (SANDWALK_DB_AUTO_HEAL=0). Restore from backup "
            "or remove the file only if you accept data loss."
        )

    if not db_path.exists():
        raise RuntimeError(f"Corrupt DB path missing: {db_path}")

    quarantined = quarantine_database(db_path)
    recovered_tmp = db_path.with_name(f"{db_path.name}.heal-{int(time.time())}")

    if recover_via_sqlite_cli(quarantined, recovered_tmp):
        recovered_tmp.replace(db_path)
        for suffix in ("-wal", "-shm"):
            Path(f"{db_path}{suffix}").unlink(missing_ok=True)
        note = f"Recovered agent DB via sqlite3 .recover (quarantined {quarantined.name})"
        logger.warning(note)
        refresh_healthy_backup(db_path)
        return note

    recovered_tmp.unlink(missing_ok=True)
    backup = backup_path_for(db_path)
    if restore_from_backup(db_path, backup):
        note = (
            f"Restored agent DB from backup {backup.name} "
            f"(quarantined {quarantined.name}; .recover failed)"
        )
        logger.warning(note)
        return note

    # Put the corrupt file back under the expected name? No — leave quarantined
    # so the user can inspect it; raise with clear instructions.
    raise RuntimeError(
        f"Agent store database is corrupt ({detail}): quarantined as {quarantined}. "
        f"sqlite3 .recover failed and no healthy backup at {backup}. "
        "Remove the quarantine only if you accept starting fresh, or restore a "
        "known-good copy to "
        f"{db_path}."
    )
