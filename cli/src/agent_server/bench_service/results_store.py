"""Persist and list bench result JSON files."""

from __future__ import annotations

import base64
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
    "name",
    "model_id",
    "provider",
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

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_NAME_LEN = 120


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


_GENERIC_PROVIDERS = frozenset(
    {"openai", "openai_compatible", "openai-compatible", "local"}
)
_CLOUD_PROFILE_IDS = frozenset({"", "openai", "openai_cloud"})
_LOCAL_BACKENDS = frozenset(
    {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}
)


def _profile_backend_lookup() -> dict[str, str]:
    try:
        from agent.config import Config

        mapping: dict[str, str] = {}
        for pid, rec in Config().openai_profiles(include_cloud=True).items():
            backend = str((rec or {}).get("backend") or "").strip().lower()
            key = str(pid or "").strip().lower()
            if key:
                mapping[key] = backend or key
        return mapping
    except Exception:  # noqa: BLE001
        return {}


def resolve_bench_provider(
    provider: str | None = None,
    *,
    profile_id: str | None = None,
    environment: dict[str, Any] | None = None,
    profiles: dict[str, str] | None = None,
) -> str | None:
    """Prefer the local profile backend (omlx, unsloth, …) over generic OpenAI."""
    env = environment if isinstance(environment, dict) else {}
    runtime = env.get("runtime") if isinstance(env.get("runtime"), dict) else {}
    model = env.get("model") if isinstance(env.get("model"), dict) else {}
    pid = str(
        profile_id
        or runtime.get("openai_profile_id")
        or model.get("openai_profile_id")
        or ""
    ).strip()
    raw = str(
        provider
        or runtime.get("provider")
        or model.get("provider")
        or ""
    ).strip()
    raw_l = raw.lower()
    pid_l = pid.lower()
    backends = profiles if profiles is not None else _profile_backend_lookup()
    backend = str(backends.get(pid_l) or "").strip().lower()
    if not backend and pid_l in _LOCAL_BACKENDS:
        backend = pid_l
    if backend and backend != "openai" and (not raw_l or raw_l in _GENERIC_PROVIDERS):
        if backend == "other":
            return pid or backend
        return backend
    if raw_l in _GENERIC_PROVIDERS and pid_l and pid_l not in _CLOUD_PROFILE_IDS:
        return backend or pid
    if raw:
        return raw
    model_id = str(env.get("model_id") or model.get("model_id") or "")
    if "/" in model_id:
        return model_id.split("/", 1)[0]
    return None


def _provider_from_row(
    row: dict[str, Any], *, profiles: dict[str, str] | None = None
) -> str | None:
    env = row.get("environment") if isinstance(row.get("environment"), dict) else None
    raw = row.get("provider")
    prov = str(raw).strip() if raw not in (None, "") else None
    resolved = resolve_bench_provider(
        prov,
        environment=env,
        profiles=profiles,
    )
    if resolved:
        return resolved
    model_id = str(row.get("model_id") or "")
    if "/" in model_id:
        return model_id.split("/", 1)[0]
    return None


def _live_run_statuses() -> dict[str, str]:
    try:
        from agent_server.bench_service.queue_runner import live_run_statuses

        return live_run_statuses()
    except Exception:  # noqa: BLE001
        return {}


def _effective_status(
    row: dict[str, Any], *, live: dict[str, str] | None = None
) -> str:
    """Stored ``running`` without a live job is a crash leftover."""
    rid = str(row.get("run_id") or "")
    if live and rid in live:
        return live[rid]
    status = str(row.get("status") or "completed").strip().lower()
    if not status:
        return "completed"
    if status in {"running", "queued"}:
        return "interrupted"
    return status


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


def _summarize(
    row: dict[str, Any],
    *,
    run_id: str,
    live: dict[str, str] | None = None,
    profiles: dict[str, str] | None = None,
) -> dict[str, Any]:
    summary = {k: row.get(k) for k in SUMMARY_KEYS if k in row or k == "run_id"}
    summary.setdefault("run_id", run_id)
    effort, fast = _reasoning_from_result(row)
    if effort is not None:
        summary["reasoning_effort"] = effort
    if fast is not None:
        summary["reasoning_fast"] = fast
    provider = _provider_from_row(row, profiles=profiles)
    if provider:
        summary["provider"] = provider
    name = row.get("name")
    if name not in (None, ""):
        summary["name"] = str(name)
    summary["status"] = _effective_status({**row, "run_id": run_id}, live=live)
    return summary


def _encode_offset(offset: int) -> str:
    raw = f"off:{max(0, int(offset))}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_offset(cursor: str) -> int | None:
    try:
        pad = "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(cursor + pad).decode()
        if raw.startswith("off:"):
            return max(0, int(raw[4:]))
    except (ValueError, TypeError, OSError):
        return None
    return None


def _matches(
    row: dict[str, Any],
    *,
    q: str | None,
    suite: str | None,
    status: str | None,
    provider: str | None,
) -> bool:
    if suite and str(row.get("benchmark") or "") != suite:
        return False
    if provider:
        want = {part.strip().lower() for part in provider.split(",") if part.strip()}
        have = str(row.get("provider") or "").strip().lower()
        if have not in want:
            return False
    if status:
        want = {part.strip().lower() for part in status.split(",") if part.strip()}
        if not want or want == {"__none__"}:
            return False
        have = str(row.get("status") or "").lower()
        if "completed" in want and have in {"completed", ""}:
            pass
        elif have not in want:
            return False
    if q:
        needle = q.strip().lower()
        hay = " ".join(
            str(row.get(key) or "")
            for key in ("name", "model_id", "provider", "benchmark", "run_id")
        ).lower()
        if needle not in hay:
            return False
    return True


def list_results(limit: int = 50, *, lean: bool = True) -> list[dict[str, Any]]:
    page = list_results_page(limit=limit, lean=lean)
    return page["data"]


def list_results_page(
    *,
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
    q: str | None = None,
    suite: str | None = None,
    status: str | None = None,
    provider: str | None = None,
    sort: str = "date_desc",
    lean: bool = True,
    paginate: bool = True,
) -> dict[str, Any]:
    """Filter result files, then offset-paginate. Newest first by default."""
    size = max(1, min(MAX_PAGE_SIZE, int(limit or DEFAULT_PAGE_SIZE)))
    live = _live_run_statuses()
    profiles = _profile_backend_lookup()
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    providers: set[str] = set()
    for path in results_dir().glob("*.json"):
        if not _is_result_file(path):
            continue
        try:
            mtime_ns = path.stat().st_mtime_ns
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(row, dict):
            continue
        rid = str(row.get("run_id") or path.stem)
        if lean:
            summary = _summarize(row, run_id=rid, live=live, profiles=profiles)
        else:
            resolved = _provider_from_row(row, profiles=profiles)
            summary = {
                **row,
                "run_id": rid,
                "status": _effective_status({**row, "run_id": rid}, live=live),
            }
            if resolved:
                summary["provider"] = resolved
        prov = str(summary.get("provider") or "").strip()
        if prov:
            providers.add(prov)
        if not _matches(
            summary, q=q, suite=suite, status=status, provider=provider
        ):
            continue
        ranked.append((mtime_ns, rid, summary))
    newest_first = str(sort or "date_desc").lower() != "date_asc"
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=newest_first)
    total = len(ranked)
    offset = _decode_offset(cursor or "") or 0
    if not paginate:
        return {
            "data": [item[2] for item in ranked],
            "next_cursor": None,
            "total": total,
            "providers": sorted(providers, key=str.lower),
        }
    page = ranked[offset : offset + size]
    next_cursor = None
    if offset + size < total:
        next_cursor = _encode_offset(offset + size)
    return {
        "data": [item[2] for item in page],
        "next_cursor": next_cursor,
        "total": total,
        "providers": sorted(providers, key=str.lower),
    }


def slice_page(
    rows: list[dict[str, Any]],
    *,
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> dict[str, Any]:
    size = max(1, min(MAX_PAGE_SIZE, int(limit or DEFAULT_PAGE_SIZE)))
    offset = _decode_offset(cursor or "") or 0
    total = len(rows)
    page = rows[offset : offset + size]
    next_cursor = _encode_offset(offset + size) if offset + size < total else None
    return {"data": page, "next_cursor": next_cursor, "total": total}


def apply_live_status(row: dict[str, Any]) -> dict[str, Any]:
    rid = str(row.get("run_id") or "")
    status = _effective_status({**row, "run_id": rid}, live=_live_run_statuses())
    if str(row.get("status") or "") == status:
        return row
    return {**row, "status": status}


def get_result(run_id: str) -> dict[str, Any] | None:
    path = results_dir() / f"{run_id}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def result_from_checkpoint(ckpt: dict[str, Any]) -> dict[str, Any]:
    """Minimal result row so a paused stack without a JSON file still loads."""
    completed = list(ckpt.get("completed_question_ids") or [])
    remaining = list(ckpt.get("remaining_question_ids") or [])
    total = len(completed) + len(remaining)
    sample = ckpt.get("sample_size")
    if not total and sample not in (None, ""):
        try:
            total = int(sample)
        except (TypeError, ValueError):
            total = 0
    return {
        "run_id": str(ckpt.get("run_id") or ""),
        "model_id": str(ckpt.get("model_id") or ""),
        "benchmark": str(ckpt.get("benchmark") or ckpt.get("suite_id") or ""),
        "accuracy": 0.0,
        "correct": len(completed),
        "total": total,
        "skipped": 0,
        "time_s": float(ckpt.get("elapsed_s") or 0),
        "thinking_used": bool(ckpt.get("thinking")),
        "status": str(ckpt.get("status") or "paused"),
        "provider": ckpt.get("provider"),
        "project_id": ckpt.get("project_id"),
        "created_at": ckpt.get("updated_at") or ckpt.get("created_at"),
        "questions": [],
    }


def rename_result(run_id: str, name: str) -> dict[str, Any] | None:
    row = get_result(run_id)
    if row is None:
        return None
    cleaned = " ".join(str(name or "").split())[:MAX_NAME_LEN]
    if cleaned:
        row["name"] = cleaned
    else:
        row.pop("name", None)
    save_result(row)
    return row


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
    for path in list(results_dir().glob(f"*{CHECKPOINT_SUFFIX}")):
        path.unlink(missing_ok=True)
        n += 1
    return n, sessions
