"""Session-scoped LangGraph checkpointers for HITL pause/resume."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from agent.config import CONFIG_DIR

logger = logging.getLogger("hitl")

_LOCK = threading.Lock()
_MEMORY_BY_SESSION: dict[str, Any] = {}
_SQLITE_SAVER: Any | None = None
_SQLITE_FAILED = False


def _checkpoints_dir() -> Path:
    path = CONFIG_DIR / "checkpoints"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _try_sqlite_saver() -> Any | None:
    """Prefer durable Sqlite when langgraph-checkpoint-sqlite is installed."""
    global _SQLITE_SAVER, _SQLITE_FAILED
    if _SQLITE_FAILED:
        return None
    if _SQLITE_SAVER is not None:
        return _SQLITE_SAVER
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = _checkpoints_dir() / "hitl.sqlite"
        # SqliteSaver.from_conn_string is a context manager in some versions;
        # keep a long-lived connection via constructor when available.
        try:
            _SQLITE_SAVER = SqliteSaver.from_conn_string(str(db_path))
            if hasattr(_SQLITE_SAVER, "__enter__"):
                _SQLITE_SAVER = _SQLITE_SAVER.__enter__()
        except Exception:  # noqa: BLE001
            import sqlite3

            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            _SQLITE_SAVER = SqliteSaver(conn)
        logger.debug("Using Sqlite HITL checkpointer at %s", db_path)
        return _SQLITE_SAVER
    except Exception as exc:  # noqa: BLE001
        _SQLITE_FAILED = True
        logger.debug("Sqlite HITL checkpointer unavailable (%s); using MemorySaver", exc)
        return None


def get_session_checkpointer(session_id: str | None) -> Any:
    """Return a checkpointer for ``thread_id`` = session_id.

    Uses Sqlite when the optional package is present; otherwise a process-local
    MemorySaver keyed by session (enough for pause/resume within one server).
    """
    sqlite = _try_sqlite_saver()
    if sqlite is not None:
        return sqlite

    from langgraph.checkpoint.memory import MemorySaver

    key = (session_id or "").strip() or "_default"
    with _LOCK:
        existing = _MEMORY_BY_SESSION.get(key)
        if existing is not None:
            return existing
        saver = MemorySaver()
        _MEMORY_BY_SESSION[key] = saver
        return saver
