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
from contextlib import closing
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
        with closing(sqlite3.connect(check_path, timeout=5)) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            return bool(row and str(row[0]) == "ok")
    except sqlite3.DatabaseError:
        return False
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
            clear_wal_sidecars(tmp)


def readonly_readable(path: Path) -> bool | None:
    """Cheap read-only probe of the main-plus-sidecar pairing.

    A mismatched WAL fails at open or on the first page read, so a trivial
    query is enough to spot it — and unlike ``readonly_integrity_ok`` this
    stays O(1), which matters because shared CLI opens run it routinely.

    True readable, False definitely broken, None unknown (busy, or a ``-shm``
    this process cannot map). "Unknown" must never be read as "broken".
    """
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)) as c:
            c.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
            return True
    except sqlite3.OperationalError:
        return None
    except sqlite3.DatabaseError:
        return False


def readonly_integrity_ok(path: Path) -> bool | None:
    """Integrity check that can never write to ``path``.

    A read-write open of a database paired with a mismatched ``-wal`` replays
    that WAL into the main file and destroys it. Read-only opens cannot, so
    this is the only safe way to inspect a live database before touching it.

    Returns True for a clean database, False for genuine corruption, and None
    when the answer is unknown — a locked database, or one whose ``-shm`` this
    process cannot map. "Unknown" must never be read as "corrupt": acting on it
    would discard a perfectly good WAL along with the writes it holds.
    """
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)) as c:
            row = c.execute("PRAGMA integrity_check").fetchone()
            return bool(row and str(row[0]) == "ok")
    except sqlite3.OperationalError:
        # Busy, locked, or unable to open — says nothing about the contents.
        return None
    except sqlite3.DatabaseError:
        return False


def _quarantine_target(db_path: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = db_path.with_name(f"{db_path.name}.corrupt-{stamp}")
    # Avoid clobbering an existing quarantine with the same second.
    n = 1
    while target.exists():
        target = db_path.with_name(f"{db_path.name}.corrupt-{stamp}-{n}")
        n += 1
    return target


def quarantine_database(db_path: Path) -> Path:
    """Copy the corrupt DB (+ WAL/SHM) aside; return the quarantined main path.

    Deliberately a copy, not a move. Recovery can take up to two minutes, and if
    the process is killed in that window a *moved* original would leave no
    database at all — the next start would silently create an empty one. The
    live file stays put until a verified replacement is ready to swap in.
    """
    target = _quarantine_target(db_path)
    shutil.copy2(db_path, target)
    for suffix in ("-wal", "-shm"):
        side = Path(f"{db_path}{suffix}")
        if side.exists():
            shutil.copy2(side, Path(f"{target}{suffix}"))
    logger.warning("Quarantined corrupt agent DB → %s", target)
    return target


# Tables whose row counts stand in for "how much of the user's work is here".
_VOLUME_TABLES = ("sessions", "messages", "library_items")


def data_volume(path: Path) -> int | None:
    """Rough row count across key tables, or None when unreadable."""
    if not path.exists():
        return None
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)) as db:
            total = 0
            readable = False
            for table in _VOLUME_TABLES:
                try:
                    total += int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                    readable = True
                except sqlite3.DatabaseError:
                    continue
            # No table readable at all means the file is unusable, which is a
            # different thing from a genuinely empty database.
            return total if readable else None
    except sqlite3.DatabaseError:
        return None


def replacement_loses_data(current: Path, candidate: Path) -> str | None:
    """Describe the loss when swapping ``current`` for ``candidate``, else None.

    A corrupt database is usually still *partly* readable, so if a "repair"
    would drop most of the user's sessions and messages we would rather stop
    and say so than quietly restore a stale backup.
    """
    before = data_volume(current)
    after = data_volume(candidate)
    if before is None or after is None or before == 0:
        return None
    if after >= before:
        return None
    lost = before - after
    # Small drifts are expected — a few rows can be unrecoverable. A large drop
    # means we are about to install a much older or much emptier database.
    if lost <= max(5, before // 20):
        return None
    return f"{after} of {before} rows would survive ({lost} lost)"


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
        with closing(sqlite3.connect(dest)) as connection:
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


def backup_age_seconds(db_path: Path) -> float | None:
    """Seconds since the healthy backup was last refreshed, or None if absent."""
    backup = backup_path_for(db_path)
    if not backup.exists():
        return None
    return max(0.0, time.time() - backup.stat().st_mtime)


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
        # Both must be closed: leaving the live connection open holds a reader
        # for the life of the process and blocks the shutdown checkpoint.
        with closing(sqlite3.connect(db_path, timeout=30)) as src:
            with closing(sqlite3.connect(tmp)) as dst:
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


# Enough history to investigate a bad heal without hoarding gigabytes.
_KEEP_QUARANTINES = 5


def prune_quarantines(db_path: Path, *, keep: int = _KEEP_QUARANTINES) -> int:
    """Delete all but the newest ``keep`` quarantine copies. Returns how many went."""
    pattern = f"{db_path.name}.corrupt-*"
    mains = [
        item
        for item in db_path.parent.glob(pattern)
        if not item.name.endswith(("-wal", "-shm"))
    ]
    mains.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    removed = 0
    for stale in mains[keep:]:
        for path in (stale, Path(f"{stale}-wal"), Path(f"{stale}-shm")):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
        removed += 1
    if removed:
        logger.info("Pruned %s old agent DB quarantine copies", removed)
    return removed


def _orphan_target(db_path: Path, suffix: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = db_path.with_name(f"{db_path.name}.orphan-{stamp}{suffix}")
    n = 1
    while target.exists():
        target = db_path.with_name(f"{db_path.name}.orphan-{stamp}-{n}{suffix}")
        n += 1
    return target


def repair_mismatched_sidecars(db_path: Path) -> str | None:
    """Rescue a healthy main file that a foreign ``-wal``/``-shm`` makes unreadable.

    A ``-wal`` belonging to a different generation of the database makes every
    open fail with "disk image is malformed" even though the main file is
    perfectly intact. Worse, a *read-write* open in that state replays the
    foreign frames into the main file and genuinely destroys it — so by the
    time a heal runs there is nothing left to rescue and it falls back to a
    backup from the last boot. That is the loop behind repeatedly vanishing
    work: the sidecar survives the restore, so the next start does it again.

    This must therefore run before anything opens the database read-write.
    Removing the sidecar is safe precisely *because* SQLite cannot read it: its
    frames are unreachable whatever we do, so the real choice is between a
    complete main file and an older backup. The files are moved aside rather
    than deleted, and put back if dropping them does not actually help.

    Returns a note when repaired, or None to let the real heal run.
    """
    wal = Path(f"{db_path}-wal")
    shm = Path(f"{db_path}-shm")
    present = [path for path in (wal, shm) if path.exists()]
    if not present:
        return None
    # Read-only: probing with a read-write open is the destructive act itself.
    # Only a definite "corrupt" justifies touching the sidecars; a database
    # that is merely busy or unmappable must be left exactly as it is.
    if readonly_integrity_ok(db_path) is not False:
        return None
    # Only when the main file stands on its own is the sidecar the culprit.
    if not integrity_ok(db_path, isolate_main=True):
        return None

    moved: list[tuple[Path, Path]] = []
    try:
        for path in present:
            target = _orphan_target(db_path, "-wal" if path == wal else "-shm")
            path.replace(target)
            moved.append((path, target))
    except OSError as exc:
        logger.warning("Could not set aside mismatched WAL sidecars: %s", exc)
        for original, target in reversed(moved):
            target.replace(original)
        return None

    if integrity_ok(db_path, isolate_main=False):
        names = ", ".join(target.name for _, target in moved)
        note = (
            f"Dropped a mismatched WAL sidecar that made {db_path.name} unreadable; "
            f"all data kept (set aside as {names})"
        )
        logger.warning(note)
        return note

    # Wrong diagnosis — restore exactly what was there and heal for real.
    for original, target in reversed(moved):
        target.replace(original)
    return None


def attempt_self_heal(db_path: Path, *, detail: str) -> str:
    """Quarantine + recover/backup. Returns a human note on success; raises on failure."""
    # Runs ahead of the auto-heal gate: it never rewrites data, and reporting
    # "database is corrupt" for a healthy file with a foreign sidecar would be
    # a false diagnosis whichever way the flag is set.
    sidecar_note = repair_mismatched_sidecars(db_path)
    if sidecar_note is not None:
        return sidecar_note

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
        loss = replacement_loses_data(db_path, recovered_tmp)
        if loss is not None:
            recovered_tmp.unlink(missing_ok=True)
            clear_wal_sidecars(recovered_tmp)
            raise RuntimeError(
                f"Refusing to repair the agent database: {loss}. "
                f"The original is untouched at {db_path} and copied to "
                f"{quarantined.name}. Investigate before restarting, or set "
                "SANDWALK_DB_AUTO_HEAL=0 to always fail loud."
            )
        # Sidecars at the live path must be gone before the main appears.
        clear_wal_sidecars(db_path)
        recovered_tmp.replace(db_path)
        clear_wal_sidecars(db_path)
        note = f"Recovered agent DB via sqlite3 .recover (quarantined {quarantined.name})"
        logger.warning(note)
        prune_quarantines(db_path)
        refresh_healthy_backup(db_path)
        return note

    recovered_tmp.unlink(missing_ok=True)
    clear_wal_sidecars(recovered_tmp)
    backup = backup_path_for(db_path)
    backup_loss = replacement_loses_data(db_path, backup)
    if backup_loss is not None:
        raise RuntimeError(
            f"Refusing to restore the backup {backup.name}: {backup_loss}. "
            f"The original is untouched at {db_path} and copied to "
            f"{quarantined.name}. Investigate before restarting."
        )
    if restore_from_backup(db_path, backup):
        note = (
            f"Restored agent DB from backup {backup.name} "
            f"(quarantined {quarantined.name}; .recover failed)"
        )
        logger.warning(note)
        prune_quarantines(db_path)
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
