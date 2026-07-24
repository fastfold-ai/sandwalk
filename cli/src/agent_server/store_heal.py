"""Safe self-heal for a corrupt agent-server SQLite database.

Designed for exclusive serve open (flock already held): quarantine the bad
file, try ``sqlite3 .recover``, then fall back to the last healthy backup.
Never silently wipes to an empty DB without attempting recovery first.

Critical: never install a new main DB while a stale ``-wal``/``-shm`` from a
previous generation still sits beside it — SQLite will apply that WAL to the
new main and re-corrupt the file. That was the usual kill/restart loop.
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


def clear_wal_sidecars(db_path: Path) -> None:
    """Remove ``-wal`` / ``-shm`` next to ``db_path`` (missing is fine)."""
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)


def install_database_file(source: Path, dest: Path) -> None:
    """Install ``source`` as ``dest`` without inheriting stale WAL/SHM.

    Sidecars are cleared both before and after the replace so a crash between
    steps cannot leave a new main paired with an old WAL.
    """
    clear_wal_sidecars(dest)
    tmp = dest.with_name(f"{dest.name}.install-{os.getpid()}-{time.time_ns()}")
    clear_wal_sidecars(tmp)
    shutil.copy2(source, tmp)
    clear_wal_sidecars(dest)
    tmp.replace(dest)
    clear_wal_sidecars(dest)
    clear_wal_sidecars(tmp)


def integrity_ok(path: Path, *, isolate_main: bool = False) -> bool:
    """Return True when ``PRAGMA integrity_check`` reports ok.

    When ``isolate_main`` is True, copy only the main file (no ``-wal``/``-shm``)
    to a temp path first. Use that for heal candidates where a stale sidecar
    may poison the check — never pass ``isolate_main=True`` for a live serve
    DB that may have uncheckpointed WAL frames.
    """
    if not path.exists() or path.stat().st_size == 0:
        return False
    check_path = path
    tmp: Path | None = None
    if isolate_main:
        tmp = path.with_name(f"{path.name}.icheck-{os.getpid()}-{time.time_ns()}")
        try:
            shutil.copy2(path, tmp)
            clear_wal_sidecars(tmp)
        except OSError:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
            return False
        check_path = tmp
    try:
        with sqlite3.connect(check_path, timeout=5) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            return bool(row and str(row[0]) == "ok")
    except sqlite3.DatabaseError:
        return False
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
            clear_wal_sidecars(tmp)


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
    # Live path must have no leftover sidecars after quarantine.
    clear_wal_sidecars(db_path)
    logger.warning("Quarantined corrupt agent DB → %s", target)
    return target


def recover_via_sqlite_cli(corrupt_path: Path, dest: Path) -> bool:
    """Use ``sqlite3 .recover`` on the main file only (ignore mismatched WAL)."""
    dest.unlink(missing_ok=True)
    clear_wal_sidecars(dest)
    # Isolate the main DB without its -wal/-shm. A stale WAL from an older
    # generation is a common poison after kill/restart + heal cycles.
    isolated = dest.with_name(f"{dest.name}.isolated-{os.getpid()}")
    isolated.unlink(missing_ok=True)
    clear_wal_sidecars(isolated)
    try:
        shutil.copy2(corrupt_path, isolated)
    except OSError as exc:
        logger.warning("Could not isolate corrupt DB for recover: %s", exc)
        return False
    try:
        completed = subprocess.run(
            ["sqlite3", str(isolated), ".recover"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("sqlite3 .recover unavailable/failed: %s", exc)
        isolated.unlink(missing_ok=True)
        clear_wal_sidecars(isolated)
        return False
    finally:
        isolated.unlink(missing_ok=True)
        clear_wal_sidecars(isolated)

    if completed.returncode != 0 or not (completed.stdout or "").strip():
        err = (completed.stderr or "").strip()[:300]
        logger.warning("sqlite3 .recover failed (code=%s): %s", completed.returncode, err)
        return False
    try:
        clear_wal_sidecars(dest)
        with sqlite3.connect(dest) as connection:
            connection.executescript(completed.stdout)
            connection.commit()
            connection.execute("PRAGMA journal_mode = DELETE")
    except sqlite3.Error as exc:
        logger.warning("Applying .recover SQL failed: %s", exc)
        dest.unlink(missing_ok=True)
        clear_wal_sidecars(dest)
        return False
    clear_wal_sidecars(dest)
    if not integrity_ok(dest, isolate_main=True):
        dest.unlink(missing_ok=True)
        clear_wal_sidecars(dest)
        return False
    return True


def restore_from_backup(db_path: Path, backup: Path) -> bool:
    if not integrity_ok(backup, isolate_main=True):
        return False
    try:
        install_database_file(backup, db_path)
    except OSError as exc:
        logger.warning("Restoring backup failed: %s", exc)
        return False
    if not integrity_ok(db_path, isolate_main=True):
        return False
    logger.warning("Restored agent DB from healthy backup %s", backup)
    return True


def refresh_healthy_backup(db_path: Path) -> None:
    """Copy a verified DB to ``*.recovered`` for the next self-heal."""
    # Live path — do not strip WAL; use the online backup API instead.
    if not integrity_ok(db_path, isolate_main=False):
        return
    backup = backup_path_for(db_path)
    tmp = backup.with_suffix(backup.suffix + ".tmp")
    clear_wal_sidecars(tmp)
    try:
        # Online backup API copies a consistent snapshot even under WAL.
        with sqlite3.connect(db_path, timeout=30) as src:
            with sqlite3.connect(tmp) as dst:
                src.backup(dst)
                dst.execute("PRAGMA journal_mode = DELETE")
        clear_wal_sidecars(tmp)
        if not integrity_ok(tmp, isolate_main=True):
            tmp.unlink(missing_ok=True)
            clear_wal_sidecars(tmp)
            return
        clear_wal_sidecars(backup)
        tmp.replace(backup)
        clear_wal_sidecars(backup)
        clear_wal_sidecars(tmp)
        logger.info("Refreshed healthy agent DB backup → %s", backup)
    except (OSError, sqlite3.Error) as exc:
        logger.warning("Could not refresh DB backup: %s", exc)
        tmp.unlink(missing_ok=True)
        clear_wal_sidecars(tmp)


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
    clear_wal_sidecars(recovered_tmp)

    if recover_via_sqlite_cli(quarantined, recovered_tmp):
        # Sidecars at the live path must be gone before the main appears.
        clear_wal_sidecars(db_path)
        recovered_tmp.replace(db_path)
        clear_wal_sidecars(db_path)
        note = f"Recovered agent DB via sqlite3 .recover (quarantined {quarantined.name})"
        logger.warning(note)
        refresh_healthy_backup(db_path)
        return note

    recovered_tmp.unlink(missing_ok=True)
    clear_wal_sidecars(recovered_tmp)
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
