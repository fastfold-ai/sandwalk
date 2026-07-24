"""Exclusive-lock acquisition and raw SQLite connection handling."""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path

from agent_server.store.errors import AgentStoreCorruptedError, AgentStoreLockError

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]


class ConnectionMixin:
    """Lock, connect, and integrity-check plumbing for :class:`AgentStoreBase`."""

    path: Path
    _lock_path: Path
    _lock_fd: int | None
    last_heal_note: str | None

    def _acquire_exclusive_lock(self) -> None:
        """Non-blocking exclusive flock so only one serve owns this DB.

        Retries so a graceful restart (old process shutting down) can release
        the lock. Waits longer than a typical uvicorn drain so menubar Restart
        does not race into a permanent "starting…" failure.
        """
        deadline = time.monotonic() + 15.0
        last_exc: OSError | None = None
        while True:
            fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o644)
            try:
                if fcntl is not None:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:  # pragma: no cover - Windows
                    import msvcrt

                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                try:
                    os.ftruncate(fd, 0)
                    os.lseek(fd, 0, os.SEEK_SET)
                    os.write(fd, f"{os.getpid()}\n".encode())
                except OSError:
                    pass
                self._lock_fd = fd
                return
            except OSError as exc:
                last_exc = exc
                holder = ""
                holder_pid: int | None = None
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    raw = os.read(fd, 64).decode("utf-8", errors="replace").strip()
                    if raw:
                        holder = f" (held by pid {raw})"
                        try:
                            holder_pid = int(raw.split()[0])
                        except ValueError:
                            holder_pid = None
                except OSError:
                    pass
                os.close(fd)
                # Stale pid in the lock file (process already gone) — keep
                # retrying; the flock itself is what matters.
                if holder_pid is not None:
                    try:
                        os.kill(holder_pid, 0)
                    except ProcessLookupError:
                        time.sleep(0.05)
                        if time.monotonic() < deadline:
                            continue
                    except PermissionError:
                        pass
                if time.monotonic() >= deadline:
                    raise AgentStoreLockError(
                        f"Another Sandwalk server already has this database open"
                        f"{holder}: {self.path}. Stop the other process before "
                        "starting a new one."
                    ) from last_exc
                time.sleep(0.15)

    def _release_exclusive_lock(self) -> None:
        fd = self._lock_fd
        self._lock_fd = None
        if fd is None:
            return
        try:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
            else:  # pragma: no cover - Windows
                import msvcrt

                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
        finally:
            try:
                os.close(fd)
            except OSError:
                pass

    def _connect(self) -> sqlite3.Connection:
        try:
            return self._open_connection()
        except sqlite3.DatabaseError as exc:
            # Exclusive serve: a mid-flight malformed DB (stale WAL after a hard
            # kill/restart) can be healed once under the write lock.
            if not getattr(self, "_exclusive", False):
                raise
            detail = str(exc).lower()
            healable = (
                "malformed" in detail
                or "corrupt" in detail
                or "not a database" in detail
                or "disk image is malformed" in detail
            )
            if not healable:
                raise
            with self._write_lock:
                logger.warning("Agent DB error on connect (%s); attempting heal", exc)
                self._assert_healthy_database(allow_heal=True)
                return self._open_connection()

    def _open_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        # Exclusive serve uses FULL so a SIGKILL mid-write is far less likely to
        # leave a torn main DB. CLI/shared opens keep NORMAL for speed.
        sync = "FULL" if getattr(self, "_exclusive", False) else "NORMAL"
        connection.execute(f"PRAGMA synchronous = {sync}")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _assert_healthy_database(self, *, allow_heal: bool = False) -> None:
        """Fail loud on a malformed DB — optionally self-heal under exclusive lock."""
        if not self.path.exists():
            return
        try:
            with sqlite3.connect(self.path, timeout=5) as connection:
                row = connection.execute("PRAGMA integrity_check").fetchone()
                if row and str(row[0]) == "ok":
                    return
                detail = str(row[0]) if row else "integrity_check failed"
        except sqlite3.DatabaseError as exc:
            detail = str(exc)

        if allow_heal:
            from agent_server.store_heal import attempt_self_heal

            try:
                self.last_heal_note = attempt_self_heal(self.path, detail=detail)
                # Re-check after heal.
                with sqlite3.connect(self.path, timeout=5) as connection:
                    row = connection.execute("PRAGMA integrity_check").fetchone()
                    if row and str(row[0]) == "ok":
                        return
                    detail = str(row[0]) if row else "integrity_check failed after heal"
            except Exception as heal_exc:  # noqa: BLE001
                raise AgentStoreCorruptedError(str(heal_exc)) from heal_exc

        raise AgentStoreCorruptedError(
            f"Agent store database is corrupt ({detail}): {self.path}. "
            "Refusing to auto-repair so settings are not silently rewritten. "
            "Restore from backup or remove the file only if you accept data loss."
        )
