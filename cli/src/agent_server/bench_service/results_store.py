"""Persist and list bench result JSON files."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from agent_server.bench_service.bootstrap import results_dir
from agent_server.bench_service.checkpoint import CHECKPOINT_SUFFIX, delete_checkpoint
from agent_server.bench_service.cleanup import delete_bench_project_data

SUMMARY_KEYS = (
    "run_id",
    "model_id",
    "benchmark",
    "accuracy",
    "correct",
    "total",
    "skipped",
    "time_s",
    "thinking_used",
    "project_id",
    "created_at",
    "status",
    "sessions_cleaned",
    "reasoning_effort",
    "reasoning_fast",
)


def _reasoning_from_result(row: dict[str, Any]) -> tuple[str | None, bool | None]:
    """Pull Effort/Fast from top-level fields or nested environment snapshot."""
    effort = row.get("reasoning_effort")
    fast = row.get("reasoning_fast")
    if effort is None or fast is None:
        env = row.get("environment")
        runtime = env.get("runtime") if isinstance(env, dict) else None
        if isinstance(runtime, dict):
            if effort is None:
                effort = runtime.get("reasoning_effort")
            if fast is None:
                fast = runtime.get("reasoning_fast")
    effort_s = str(effort).strip().lower() if effort not in (None, "") else None
    fast_b = None if fast is None else bool(fast)
    return effort_s, fast_b


def new_run_id() -> str:
    return str(uuid.uuid4())


def save_result(result: dict[str, Any]) -> Path:
    run_id = str(result.get("run_id") or new_run_id())
    result["run_id"] = run_id
    result.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    path = results_dir() / f"{run_id}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _is_result_file(path: Path) -> bool:
    name = path.name
    return name.endswith(".json") and not name.endswith(CHECKPOINT_SUFFIX)


def list_results(limit: int = 50, *, lean: bool = True) -> list[dict[str, Any]]:
    files = sorted(
        (p for p in results_dir().glob("*.json") if _is_result_file(p)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for path in files[:limit]:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(row, dict):
            continue
        if lean:
            summary = {
                k: row.get(k) for k in SUMMARY_KEYS if k in row or k == "run_id"
            }
            summary.setdefault("run_id", path.stem)
            effort, fast = _reasoning_from_result(row)
            if effort is not None:
                summary["reasoning_effort"] = effort
            if fast is not None:
                summary["reasoning_fast"] = fast
            out.append(summary)
        else:
            out.append(row)
    return out


def get_result(run_id: str) -> dict[str, Any] | None:
    path = results_dir() / f"{run_id}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def export_path(run_id: str) -> Path | None:
    path = results_dir() / f"{run_id}.json"
    return path if path.is_file() else None


def delete_result(
    run_id: str,
    *,
    store: Any | None = None,
    delete_sessions: bool = True,
) -> bool:
    row = get_result(run_id)
    path = results_dir() / f"{run_id}.json"
    deleted = False
    if path.is_file():
        path.unlink(missing_ok=True)
        deleted = True
    delete_checkpoint(run_id)
    if delete_sessions and store is not None and row:
        delete_bench_project_data(store, row.get("project_id"))
    return deleted


def clear_results(*, store: Any | None = None) -> tuple[int, int]:
    """Delete result JSON + checkpoints; optionally wipe linked projects.

    Returns ``(files_cleared, sessions_deleted)``.
    """
    n = 0
    sessions = 0
    for path in list(results_dir().glob("*.json")):
        if path.name.endswith(CHECKPOINT_SUFFIX):
            path.unlink(missing_ok=True)
            n += 1
            continue
        if not _is_result_file(path):
            continue
        project_id = None
        if store is not None:
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
                project_id = row.get("project_id") if isinstance(row, dict) else None
            except (OSError, json.JSONDecodeError):
                project_id = None
        path.unlink(missing_ok=True)
        n += 1
        if store is not None and project_id:
            sessions += delete_bench_project_data(store, project_id)
    # Orphan checkpoints with no matching result
    for path in list(results_dir().glob(f"*{CHECKPOINT_SUFFIX}")):
        path.unlink(missing_ok=True)
        n += 1
    return n, sessions
