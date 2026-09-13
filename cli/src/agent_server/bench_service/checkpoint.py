"""On-disk checkpoints for pause / resume / crash recovery."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from agent_server.bench_service.bootstrap import results_dir

CHECKPOINT_SUFFIX = ".checkpoint.json"


def checkpoint_path(run_id: str) -> Path:
    return results_dir() / f"{run_id}{CHECKPOINT_SUFFIX}"


def save_checkpoint(payload: dict[str, Any]) -> Path:
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        raise ValueError("checkpoint requires run_id")
    payload = {
        **payload,
        "run_id": run_id,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = checkpoint_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{run_id}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def load_checkpoint(run_id: str) -> dict[str, Any] | None:
    path = checkpoint_path(run_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def delete_checkpoint(run_id: str) -> bool:
    path = checkpoint_path(run_id)
    if not path.is_file():
        return False
    path.unlink(missing_ok=True)
    return True


def list_checkpoints() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(
        results_dir().glob(f"*{CHECKPOINT_SUFFIX}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(row, dict) and row.get("run_id"):
            out.append(row)
    return out


_RESUMABLE_STATUSES = frozenset({"paused", "running", "interrupted"})


def is_resumable_checkpoint(row: dict[str, Any] | None) -> bool:
    """True when a checkpoint still has work (or was mid-run when the process died)."""
    if not row or not row.get("run_id"):
        return False
    status = str(row.get("status") or "").strip().lower()
    if status == "cancelled":
        return False
    if status in _RESUMABLE_STATUSES:
        return True
    remaining = row.get("remaining_question_ids") or []
    return bool(remaining)


def checkpoint_resume_status(row: dict[str, Any] | None) -> str | None:
    """List/queue status for a leftover checkpoint, or None if it is not resumable."""
    if not is_resumable_checkpoint(row):
        return None
    status = str((row or {}).get("status") or "").strip().lower()
    return "paused" if status == "paused" else "interrupted"


def find_resumable_checkpoint() -> dict[str, Any] | None:
    """Newest checkpoint that can be resumed after a restart."""
    for row in list_checkpoints():
        if is_resumable_checkpoint(row):
            return row
    return None
