"""Copy finished-suite token totals onto the chat usage ledger once."""

from __future__ import annotations

from datetime import date
from typing import Any

from agent_server.store.usage import _project_token_cache, _project_token_lock


def _int(row: dict[str, Any], *keys: str) -> int:
    for key in keys:
        raw = row.get(key)
        if raw is None:
            continue
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            continue
    return 0


def sum_bench_usage(bench_store: Any, project_id: str | None) -> dict[str, int]:
    pid = str(project_id or "").strip()
    if not pid or bench_store is None:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
        }
    rows = bench_store.list_usage_runs(project_id=pid, include_bench=True)
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
    }
    for row in rows:
        totals["input_tokens"] += _int(row, "input_tokens")
        totals["output_tokens"] += _int(row, "output_tokens")
        totals["cache_read_tokens"] += _int(row, "cache_read_tokens")
        totals["cache_creation_tokens"] += _int(row, "cache_creation_tokens")
    return totals


def rollup_suite_usage(
    *,
    chat_store: Any,
    bench_store: Any | None,
    result: dict[str, Any],
    usage_project_id: str | None = None,
    surface: str = "ui",
) -> dict[str, Any]:
    """Upsert one chat-ledger row for a paused/completed suite. Idempotent."""
    run_id = str(result.get("run_id") or "").strip()
    if not run_id or chat_store is None:
        return result
    totals = sum_bench_usage(bench_store, result.get("project_id"))
    chat_totals = sum_bench_usage(chat_store, result.get("project_id"))
    if sum(chat_totals.values()) > sum(totals.values()):
        totals = chat_totals
    if sum(totals.values()) <= 0:
        totals = {
            "input_tokens": _int(result, "input_tokens"),
            "output_tokens": _int(result, "output_tokens"),
            "cache_read_tokens": _int(result, "cache_read_tokens"),
            "cache_creation_tokens": _int(result, "cache_creation_tokens"),
        }
    lifetime = max(
        totals["input_tokens"] + totals["output_tokens"],
        _int(result, "lifetime_tokens"),
    )
    result["input_tokens"] = totals["input_tokens"]
    result["output_tokens"] = totals["output_tokens"]
    result["cache_read_tokens"] = totals["cache_read_tokens"]
    result["cache_creation_tokens"] = totals["cache_creation_tokens"]
    result["lifetime_tokens"] = lifetime
    day = str(result.get("created_at") or "")[:10]
    if len(day) != 10:
        day = date.today().isoformat()
    pid = str(usage_project_id or result.get("usage_project_id") or "").strip() or None
    chat_store.upsert_usage_run(
        run_id=run_id,
        session_id=None,
        day=day,
        surface=surface,
        model_id=str(result.get("model_id") or "") or None,
        provider=str(result.get("provider") or "") or None,
        project_id=pid,
        kind="bench",
        input_tokens=totals["input_tokens"],
        output_tokens=totals["output_tokens"],
        cache_read_tokens=totals["cache_read_tokens"],
        cache_creation_tokens=totals["cache_creation_tokens"],
    )
    if pid:
        with _project_token_lock:
            _project_token_cache.pop(pid, None)
    return result
