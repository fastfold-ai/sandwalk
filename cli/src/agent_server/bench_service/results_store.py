"""Persist and list bench result JSON files."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from agent_server.bench_service.bootstrap import results_dir


def new_run_id() -> str:
    return str(uuid.uuid4())


def save_result(result: dict[str, Any]) -> Path:
    run_id = str(result.get("run_id") or new_run_id())
    result["run_id"] = run_id
    result.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    path = results_dir() / f"{run_id}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def list_results(limit: int = 50) -> list[dict[str, Any]]:
    files = sorted(results_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for path in files[:limit]:
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
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


def clear_results() -> int:
    n = 0
    for path in results_dir().glob("*.json"):
        path.unlink(missing_ok=True)
        n += 1
    return n
