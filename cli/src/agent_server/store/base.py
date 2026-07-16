"""Lifecycle: open/close, schema bootstrap, and the small key/value meta table."""

from __future__ import annotations

import atexit
import logging
import sqlite3
import threading
from pathlib import Path

from agent import config as agent_config
from agent_server.store.connection import ConnectionMixin
from agent_server.store.migrations import apply_migrations
from agent_server.store.schema import create_schema
from agent_server.store.util import utc_now

logger = logging.getLogger(__name__)


class AgentStoreBase(ConnectionMixin):
    """Small durable store shared by CLI and web transports.

    Durability rules:
    - Exclusive serve takes a process lock so a second serve cannot open the
      same file, and checkpoints WAL on ``close()``.
    - Short-lived CLI opens leave ``exclusive=False`` so they can share the DB
      with a running server via SQLite WAL.
    - On exclusive open, a corrupt DB is auto-healed when enabled (default):
      quarantine → ``sqlite3 .recover`` → last ``*.recovered`` backup. Set
      ``SANDWALK_DB_AUTO_HEAL=0`` to refuse and fail loud instead.
    - Hard ``kill -9`` / crash mid-write is the usual corruption cause (menubar
      restart loops historically SIGKILL'd the API after ~0.2s).
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        exclusive: bool = False,
        verify_integrity: bool | None = None,
    ) -> None:
        self.path = (path or (agent_config.CONFIG_DIR / "agent-server.db")).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        self._exclusive = exclusive
        self._lock_fd: int | None = None
        self._lock_path = self.path.with_name(f"{self.path.name}.lock")
        self._closed = False
        self._atexit_registered = False
        self.last_heal_note: str | None = None

        if exclusive:
            self._acquire_exclusive_lock()

        try:
            check = verify_integrity if verify_integrity is not None else exclusive
            if check:
                self._assert_healthy_database(allow_heal=exclusive)
            self._initialize()
            if exclusive and self.path.exists():
                from agent_server.store_heal import refresh_healthy_backup

                refresh_healthy_backup(self.path)
        except Exception:
            self._release_exclusive_lock()
            raise

        if exclusive:
            atexit.register(self.close)
            self._atexit_registered = True

    def close(self) -> None:
        """Checkpoint WAL and release the exclusive lock (idempotent)."""
        with self._write_lock:
            if self._closed:
                return
            self._closed = True
            try:
                if self.path.exists():
                    with self._connect() as connection:
                        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error as exc:
                logger.warning("WAL checkpoint on close failed: %s", exc)
            self._release_exclusive_lock()

    def _initialize(self) -> None:
        with self._connect() as connection:
            create_schema(connection)
            apply_migrations(connection)
        self._bootstrap_defaults()

    def _bootstrap_defaults(self) -> None:
        from agent.config import Config
        from agent.tool_tiers import apply_core_tool_defaults
        from agent_server.default_specialists import (
            ensure_default_specialist_tool_names,
            ensure_default_specialists,
            ensure_fast_computational_scientist,
        )

        ensure_default_specialists(self)
        ensure_fast_computational_scientist(self)
        ensure_default_specialist_tool_names(self)
        # Idempotent via config flag (safe across multiple AgentStore paths).
        apply_core_tool_defaults(Config.load())

    def get_meta(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM store_meta WHERE key = ?",
                (key,),
            ).fetchone()
        return str(row["value"]) if row is not None else None

    def set_meta(self, key: str, value: str) -> None:
        with self._write_lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO store_meta(key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )


__all__ = ["AgentStoreBase", "utc_now"]
