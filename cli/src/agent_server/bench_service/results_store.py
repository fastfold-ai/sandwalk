"""Persist and list bench result JSON files."""

from __future__ import annotations

import base64
import json
import time
import uuid
from pathlib import Path
from typing import Any

from agent_server.bench_service.bootstrap import results_dir
from agent_server.bench_service.checkpoint import (
    CHECKPOINT_SUFFIX,
    checkpoint_path,
    checkpoint_resume_status,
    delete_checkpoint,
    is_resumable_checkpoint,
    load_checkpoint,
)
from agent_server.bench_service.cleanup import delete_bench_project_data

SUMMARY_KEYS = (
    "run_id",
    "name",
    "model_id",
    "provider",
    "benchmark",
    "accuracy",
    "correct",
    "answered",
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
    "resumable",
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


def _answered_count(row: dict[str, Any]) -> int | None:
    questions = row.get("questions")
    if not isinstance(questions, list):
        return None
    return len(questions)


def is_incomplete_result(
    row: dict[str, Any], *, checkpoint: dict[str, Any] | None = None
) -> bool:
    """True when the run can still grade more questions."""
    if is_resumable_checkpoint(checkpoint):
        return True
    status = str(row.get("status") or "").strip().lower()
    if status == "cancelled":
        return False
    if status in {"paused", "interrupted", "running", "queued"}:
        return True
    answered = _answered_count(row)
    try:
        total = int(row.get("total") or 0)
    except (TypeError, ValueError):
        total = 0
    return answered is not None and total > 0 and answered < total


def _checkpoint_map() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in results_dir().glob(f"*{CHECKPOINT_SUFFIX}"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(row, dict):
            continue
        rid = str(row.get("run_id") or "")
        if rid:
            out[rid] = row
    return out


def _effective_status(
    row: dict[str, Any],
    *,
    live: dict[str, str] | None = None,
    checkpoints: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Stored ``running`` without a live job is a crash leftover."""
    rid = str(row.get("run_id") or "")
    if live and rid in live:
        return live[rid]
    ckpt = None
    if checkpoints is not None:
        ckpt = checkpoints.get(rid)
    elif rid:
        ckpt = load_checkpoint(rid)
    resume_as = checkpoint_resume_status(ckpt)
    if resume_as:
        return resume_as
    status = str(row.get("status") or "completed").strip().lower()
    if not status:
        status = "completed"
    if is_incomplete_result(row, checkpoint=ckpt):
        return "paused" if status == "paused" else "interrupted"
    if status in {"running", "queued"}:
        return "interrupted"
    return status


def is_retryable_failure(item: dict[str, Any]) -> bool:
    """True for infra/judge failures — not a graded-wrong answer."""
    if item.get("skipped") or item.get("terminal") is True:
        return True
    if str(item.get("eval_mode") or "") == "error":
        return True
    judge = item.get("judge") if isinstance(item.get("judge"), dict) else {}
    if str(judge.get("error") or "").strip():
        return True
    blob = " ".join(
        [
            str(judge.get("error") or ""),
            str(item.get("raw_response") or ""),
            str(item.get("predicted") or ""),
        ]
    ).lower()
    hints = (
        "rate limit",
        "429",
        "overloaded",
        "capacity",
        "timed out",
        "timeout",
        "stalled",
        "provider disconnect",
        "unavailable",
        "nodename nor servname",
        "connection reset",
        "econnreset",
        "503",
        "502",
    )
    return any(hint in blob for hint in hints)


def retryable_failure_ids(row: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in (row or {}).get("questions") or []:
        if not isinstance(item, dict) or not is_retryable_failure(item):
            continue
        qid = str(item.get("question_id") or "").strip()
        if qid and qid not in seen:
            seen.add(qid)
            out.append(qid)
    return out


def _terminal_question_ids(row: dict[str, Any] | None) -> set[str]:
    ids: set[str] = set()
    for item in (row or {}).get("questions") or []:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("question_id") or "").strip()
        if not qid:
            continue
        if item.get("terminal") is True:
            ids.add(qid)
            continue
        judge = item.get("judge") if isinstance(item.get("judge"), dict) else {}
        err = str(judge.get("error") or "").lower()
        if item.get("eval_mode") == "error" and (
            "stalled" in err or "timed out" in err
        ):
            ids.add(qid)
    return ids


def _exhausted_questions_from_stores(
    project_id: str | None, stores: list[Any] | None
) -> set[str]:
    pid = str(project_id or "").strip()
    if not pid or not stores:
        return set()
    found: set[str] = set()
    for store in stores:
        lookup = getattr(store, "bench_question_session_counts", None)
        if lookup is None:
            continue
        try:
            counts = (lookup([pid]) or {}).get(pid) or {}
        except Exception:  # noqa: BLE001
            counts = {}
        if not counts:
            continue
        from agent_server.store.session_queries import exhausted_bench_question_ids

        found.update(exhausted_bench_question_ids(counts))
    return found


def _leftover_questions_from_stores(
    project_id: str | None, stores: list[Any] | None
) -> list[str]:
    pid = str(project_id or "").strip()
    if not pid or not stores:
        return []
    for store in stores:
        lookup = getattr(store, "interrupted_bench_questions_by_project", None)
        if lookup is None:
            continue
        try:
            leftover = lookup([pid]).get(pid) or []
        except Exception:  # noqa: BLE001
            leftover = []
        if leftover:
            return [str(item) for item in leftover if str(item).strip()]
    return []


def build_resume_checkpoint(
    run_id: str, *, stores: list[Any] | None = None
) -> dict[str, Any] | None:
    """Load a disk checkpoint, or rebuild one from a leftover result file."""
    rid = str(run_id or "").strip()
    if not rid:
        return None
    ckpt = load_checkpoint(rid)
    if is_resumable_checkpoint(ckpt) and not stores:
        return ckpt
    row = get_result(rid)
    project_id = (row or {}).get("project_id") or (ckpt or {}).get("project_id")
    leftover = [
        qid
        for qid in _leftover_questions_from_stores(project_id, stores)
        if qid not in _terminal_question_ids(row)
    ]
    exhausted = _exhausted_questions_from_stores(project_id, stores)
    exhausted.update(_terminal_question_ids(row))
    if leftover and ckpt:
        ckpt = {
            **ckpt,
            "status": "interrupted",
            "remaining_question_ids": leftover,
            "completed_question_ids": [
                str(item)
                for item in (ckpt.get("completed_question_ids") or [])
                if str(item) not in set(leftover)
            ],
        }
        return ckpt
    if is_resumable_checkpoint(ckpt) and stores is None:
        return ckpt
    if row is None:
        return None
    ckpt_remaining = [
        str(item)
        for item in ((ckpt or {}).get("remaining_question_ids") or [])
        if str(item) not in exhausted
    ]
    if not leftover and not ckpt_remaining and not is_incomplete_result(
        row, checkpoint=None
    ):
        return None
    env = row.get("environment") if isinstance(row.get("environment"), dict) else {}
    suite = env.get("suite") if isinstance(env.get("suite"), dict) else {}
    model = env.get("model") if isinstance(env.get("model"), dict) else {}
    questions = row.get("questions") if isinstance(row.get("questions"), list) else []
    all_ids = [
        str(item.get("question_id"))
        for item in questions
        if isinstance(item, dict) and item.get("question_id")
    ]
    remaining = leftover or ckpt_remaining
    skip = set(remaining)
    completed = [qid for qid in all_ids if qid not in skip]
    for qid in exhausted:
        if qid not in skip and qid not in completed:
            completed.append(qid)
    if stores is not None and not remaining and not leftover:
        if not is_incomplete_result(row, checkpoint=None):
            return None
        # Missing questions with no open sessions: keep a rebuild so spawn
        # can finish from completed_ids. Exhausted leftovers stay completed.
    sample = suite.get("sample_size")
    if sample in (None, ""):
        sample = row.get("total")
    return _checkpoint_payload(
        row,
        run_id=rid,
        remaining=remaining,
        completed=completed,
        env=env,
        suite=suite,
        model=model,
        sample=sample,
    )


def _checkpoint_payload(
    row: dict[str, Any],
    *,
    run_id: str,
    remaining: list[str],
    completed: list[str],
    env: dict[str, Any],
    suite: dict[str, Any],
    model: dict[str, Any],
    sample: Any,
    force_retry: bool = False,
    concurrency: int = 1,
) -> dict[str, Any]:
    payload = {
        "run_id": run_id,
        "status": "interrupted",
        "suite_id": str(suite.get("suite_id") or row.get("benchmark") or ""),
        "pack_id": suite.get("pack_id"),
        "matrix": suite.get("matrix"),
        "model_id": str(row.get("model_id") or model.get("model_id") or ""),
        "provider": row.get("provider") or model.get("provider"),
        "sample_size": sample,
        "project_id": row.get("project_id"),
        "project_name": row.get("name"),
        "specialist_id": model.get("specialist_id"),
        "thinking": bool(row.get("thinking_used") or model.get("thinking")),
        "client_surface": "ui",
        "concurrency": max(1, int(concurrency)),
        "cleanup_sessions": False,
        "completed_question_ids": completed,
        "remaining_question_ids": remaining,
        "environment": env or None,
        "elapsed_s": row.get("time_s"),
        "name": row.get("name"),
    }
    if force_retry:
        payload["force_retry"] = True
    return payload


def build_retry_failed_checkpoint(
    run_id: str, *, question_ids: list[str] | None = None
) -> dict[str, Any] | None:
    """Rebuild a checkpoint that re-runs infra/judge failures, or specific ids."""
    rid = str(run_id or "").strip()
    if not rid:
        return None
    row = get_result(rid)
    if row is None:
        return None
    wanted = [str(item).strip() for item in (question_ids or []) if str(item).strip()]
    if wanted:
        known = {
            str(item.get("question_id") or "").strip()
            for item in (row.get("questions") or [])
            if isinstance(item, dict) and item.get("question_id")
        }
        remaining = [qid for qid in wanted if qid in known]
    else:
        remaining = retryable_failure_ids(row)
    if not remaining:
        return None
    skip = set(remaining)
    questions = row.get("questions") if isinstance(row.get("questions"), list) else []
    completed = [
        str(item.get("question_id"))
        for item in questions
        if isinstance(item, dict)
        and item.get("question_id")
        and str(item.get("question_id")) not in skip
    ]
    env = row.get("environment") if isinstance(row.get("environment"), dict) else {}
    suite = env.get("suite") if isinstance(env.get("suite"), dict) else {}
    model = env.get("model") if isinstance(env.get("model"), dict) else {}
    sample = suite.get("sample_size")
    if sample in (None, ""):
        sample = row.get("total")
    return _checkpoint_payload(
        row,
        run_id=rid,
        remaining=remaining,
        completed=completed,
        env=env,
        suite=suite,
        model=model,
        sample=sample,
        force_retry=True,
        concurrency=min(4, max(1, len(remaining))),
    )


def _session_project_ids(session_ids: list[str], stores: list[Any]) -> list[str]:
    wanted = [str(item).strip() for item in session_ids if str(item).strip()]
    if not wanted:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for store in stores:
        lookup = getattr(store, "list_sessions_by_ids", None)
        if lookup is None:
            continue
        try:
            sessions = lookup(wanted)
        except Exception:  # noqa: BLE001
            continue
        for session in sessions:
            pid = getattr(session, "project_id", None)
            if pid is None and isinstance(session, dict):
                pid = session.get("project_id")
            key = str(pid or "").strip()
            if key and key not in seen:
                seen.add(key)
                found.append(key)
    return found


def attach_usage_and_resume(
    rows: list[dict[str, Any]],
    *,
    stores: list[Any] | None = None,
    run_tokens: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Fill lifetime tokens and mark leftover interrupted sessions as resumable."""
    stores = [store for store in (stores or []) if store is not None]
    pids: list[str] = []
    for row in rows:
        pid = str(row.get("project_id") or "").strip()
        if pid:
            pids.append(pid)
        pids.extend(_session_project_ids(list(row.get("usage_session_ids") or []), stores))
    pids = list(dict.fromkeys(pids))
    leftover_by_project: dict[str, list[str]] = {}
    project_tokens: dict[str, int] = {}
    for store in stores:
        lookup = getattr(store, "interrupted_bench_questions_by_project", None)
        if lookup is not None:
            try:
                for pid, qids in lookup(pids).items():
                    if qids and pid not in leftover_by_project:
                        leftover_by_project[pid] = list(qids)
            except Exception:  # noqa: BLE001
                pass
        proj_lookup = getattr(store, "lifetime_tokens_by_project", None)
        if proj_lookup is not None:
            try:
                for pid, n in proj_lookup(pids).items():
                    current = int(project_tokens.get(pid) or 0)
                    project_tokens[pid] = max(current, int(n or 0))
            except Exception:  # noqa: BLE001
                pass
    out: list[dict[str, Any]] = []
    for row in rows:
        rid = str(row.get("run_id") or "")
        pid = str(row.get("project_id") or "").strip()
        related = [pid] if pid else []
        related.extend(_session_project_ids(list(row.get("usage_session_ids") or []), stores))
        leftover: list[str] = []
        full = get_result(rid) if rid else None
        skip = _terminal_question_ids(full or row)
        graded_ids = {
            str(item.get("question_id") or "").strip()
            for item in ((full or row).get("questions") or [])
            if isinstance(item, dict) and item.get("question_id")
        }
        # Only this run's project — usage may point at an older project
        # whose interrupted sessions would fake a leftover forever.
        # Question ids already in the result file are done; leftover
        # sessions after a retry must not flip a completed suite.
        for item in ([pid] if pid else []):
            leftover.extend(
                qid
                for qid in (leftover_by_project.get(item) or [])
                if qid not in skip and qid not in graded_ids
            )
        leftover = list(dict.fromkeys(leftover))
        candidates = [
            row.get("lifetime_tokens"),
            (run_tokens or {}).get(rid),
            *(project_tokens.get(item) for item in related),
        ]
        tokens = max((_as_token(value) for value in candidates), default=0)
        next_row = {**row, "lifetime_tokens": tokens}
        next_row.pop("usage_session_ids", None)
        answered = _answered_count(full or next_row)
        if answered is None and next_row.get("answered") not in (None, ""):
            try:
                answered = int(next_row["answered"])
            except (TypeError, ValueError):
                answered = None
        try:
            total = int(next_row.get("total") or 0)
        except (TypeError, ValueError):
            total = 0
        if leftover:
            status = str(next_row.get("status") or "").lower()
            if status not in {"running", "queued", "paused"}:
                next_row["status"] = "interrupted"
            next_row["resumable"] = True
        elif (
            answered is not None
            and total > 0
            and answered >= total
            and str(next_row.get("status") or "").lower()
            not in {"running", "queued", "paused"}
        ):
            next_row["status"] = "completed"
            next_row["resumable"] = bool(retryable_failure_ids(full or next_row))
        out.append(next_row)
    return out


def _as_token(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


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
    checkpoints: dict[str, dict[str, Any]] | None = None,
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
    session_ids: list[str] = []
    for item in row.get("questions") or []:
        if not isinstance(item, dict):
            continue
        sid = item.get("session_id") or item.get("sessionId")
        if sid:
            session_ids.append(str(sid))
    if session_ids:
        summary["usage_session_ids"] = session_ids
    merged = {**row, "run_id": run_id}
    status = _effective_status(merged, live=live, checkpoints=checkpoints)
    summary["status"] = status
    live_state = (live or {}).get(run_id)
    ckpt = (checkpoints or {}).get(run_id)
    answered = _answered_count(row)
    if answered is None and ckpt:
        answered = len(ckpt.get("completed_question_ids") or [])
    if answered is not None:
        summary["answered"] = answered
    failed_n = len(retryable_failure_ids(row))
    if failed_n:
        summary["failed_count"] = failed_n
    summary["resumable"] = live_state not in {"running", "queued"} and (
        is_incomplete_result(merged, checkpoint=ckpt)
        or status in {"paused", "interrupted"}
        or failed_n > 0
    )
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
    checkpoints = _checkpoint_map()
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    providers: set[str] = set()
    seen: set[str] = set()
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
        seen.add(rid)
        if lean:
            summary = _summarize(
                row,
                run_id=rid,
                live=live,
                profiles=profiles,
                checkpoints=checkpoints,
            )
        else:
            resolved = _provider_from_row(row, profiles=profiles)
            merged = {**row, "run_id": rid}
            status_value = _effective_status(
                merged, live=live, checkpoints=checkpoints
            )
            live_state = live.get(rid)
            summary = {
                **merged,
                "status": status_value,
                "resumable": live_state not in {"running", "queued"}
                and (
                    is_incomplete_result(merged, checkpoint=checkpoints.get(rid))
                    or status_value in {"paused", "interrupted"}
                ),
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
    for rid, ckpt in checkpoints.items():
        if rid in seen or not checkpoint_resume_status(ckpt):
            continue
        row = result_from_checkpoint(ckpt)
        try:
            mtime_ns = checkpoint_path(rid).stat().st_mtime_ns
        except OSError:
            mtime_ns = 0
        summary = _summarize(
            row,
            run_id=rid,
            live=live,
            profiles=profiles,
            checkpoints=checkpoints,
        )
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
    live = _live_run_statuses()
    merged = {**row, "run_id": rid}
    status = _effective_status(merged, live=live)
    resumable = live.get(rid) not in {"running", "queued"} and (
        is_incomplete_result(merged) or status in {"paused", "interrupted"}
    )
    if str(row.get("status") or "") == status and bool(row.get("resumable")) == resumable:
        return row
    return {**row, "status": status, "resumable": resumable}


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
        "answered": len(completed),
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
