"""ops: shared storage-path and formatting helpers. Split from tools/ops.py."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.config import CONFIG_DIR


def _ops_root(_session=None) -> Path:
    """Return base directory for ops storage and ensure it exists."""
    base = None
    if _session is not None and getattr(_session, "config", None) is not None:
        base = _session.config.get("ops.base_dir")

    root = Path(base).expanduser() if base else (CONFIG_DIR / "ops")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _notebook_path(_session=None) -> Path:
    return _ops_root(_session) / "notebook.jsonl"


def _todos_path(_session=None) -> Path:
    return _ops_root(_session) / "todos.json"


def _workflow_dir(_session=None) -> Path:
    path = _ops_root(_session) / "workflows"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default
