"""Server-side bench queue: independent stacks, optional parallel jobs.

``concurrency`` (Workers in the UI) is in-suite cell parallelism.
``parallel_runs`` is how many independent stacks may execute at once.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from agent_server.app_deps import AppDeps
from agent_server.bench_service.checkpoint import (
    delete_checkpoint,
    find_resumable_checkpoint,
    list_checkpoints,
    load_checkpoint,
    save_checkpoint,
)
from agent_server.bench_service.results_store import (
    get_result,
    new_run_id,
    resolve_bench_provider,
    save_result,
)
from agent_server.bench_service.spawn_core import run_agent_suite
from agent_server.models.bench import (
    BenchActiveStatus,
    BenchProgress,
    BenchQueueItem,
    BenchSpawnRequest,
)
from agent_server.settings_service import SettingsService

logger = logging.getLogger(__name__)

MAX_PARALLEL_RUNS = 16
_PROGRESS_KEYS = (
    "type",
    "phase",
    "model_id",
    "benchmark",
    "message",
    "current",
    "total",
    "bench_current",
    "bench_total",
    "in_flight",
    "run_id",
)


@dataclass
class BenchJob:
    run_id: str
    model_id: str
    provider: str | None
    suites: list[dict[str, Any]]
    thinking: bool = False
    project_name: str | None = None
    specialist_id: str | None = None
    client_surface: str = "ui"
    concurrency: int = 1
    cleanup_sessions: bool = False
    resume_checkpoint: dict[str, Any] | None = None
    suite_index: int = 0
    started_at: str | None = None
    elapsed_s: float = 0.0


@dataclass
class BenchQueueState:
    queue: list[BenchJob] = field(default_factory=list)
    inflight: dict[str, BenchJob] = field(default_factory=dict)
    progress_by_run: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_progress: dict[str, Any] | None = None
    phase: str = "idle"
    cancel_ids: set[str] = field(default_factory=set)
    pause_ids: set[str] = field(default_factory=set)
    paused: dict[str, dict[str, Any]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    job_threads: dict[str, threading.Thread] = field(default_factory=dict)
    max_parallel: int = 1
    events: list[dict[str, Any]] = field(default_factory=list)


_state = BenchQueueState()
_job_hook = None


def reset_state_for_tests() -> None:
    """Drop in-memory queue state. Tests must join workers first."""
    global _state, _job_hook
    _state = BenchQueueState()
    _job_hook = None
    try:
        from agent_server.bench_service.runtime import _stopping

        _stopping.clear()
    except Exception:  # noqa: BLE001
        pass


def bootstrap_resumable() -> None:
    """On serve boot, advertise paused/interrupted checkpoints if present."""
    with _state.lock:
        if _state.inflight or _state.queue or _state.paused:
            return
        for ckpt in list_checkpoints():
            status = str(ckpt.get("status") or "")
            if status == "running":
                ckpt = {**ckpt, "status": "interrupted"}
                try:
                    save_checkpoint(ckpt)
                except Exception:  # noqa: BLE001
                    pass
                status = "interrupted"
            if status not in {"paused", "interrupted"}:
                continue
            rid = str(ckpt.get("run_id") or "")
            if rid:
                _state.paused[rid] = ckpt
        if not _state.paused:
            return
        _state.phase = "paused"
        first = next(iter(_state.paused.values()))
        _state.last_progress = {
            "type": "progress",
            "phase": "paused",
            "model_id": str(first.get("model_id") or ""),
            "benchmark": str(first.get("benchmark") or first.get("suite_id") or ""),
            "message": "Paused — resume to continue",
            "current": 0,
            "total": 1,
            "bench_current": len(first.get("completed_question_ids") or []),
            "bench_total": len(first.get("completed_question_ids") or [])
            + len(first.get("remaining_question_ids") or []),
            "run_id": str(first.get("run_id") or ""),
        }


def get_active_status() -> BenchActiveStatus:
    with _state.lock:
        inflight_items = [
            _job_item(job, "running", _state.progress_by_run.get(job.run_id))
            for job in _state.inflight.values()
        ]
        queue_items = [_job_item(job, "queued") for job in _state.queue]
        paused_map = dict(_state.paused)
        live_ids = set(_state.inflight) | {job.run_id for job in _state.queue}
        running = bool(_state.inflight)
        queued = bool(_state.queue)
        current = next(iter(_state.inflight.values()), None)
        current_model = current.model_id if current else None
        current_run_id = current.run_id if current else None
        progress_by_run = dict(_state.progress_by_run)
        last_progress = _state.last_progress
        phase_raw = _state.phase
        parallel = max(1, _state.max_parallel)
    for rid, ckpt in _disk_paused(exclude=live_ids | set(paused_map)).items():
        paused_map[rid] = ckpt
    paused_items = [_ckpt_item(ckpt) for ckpt in paused_map.values()]
    first_paused = next(iter(paused_map.values()), None)
    if running:
        phase = "running" if phase_raw in {"idle", "paused"} else phase_raw
    elif queued:
        phase = "loading"
    elif paused_map:
        phase = "paused"
    else:
        phase = "idle"
    resumable = first_paused
    if not running and resumable:
        current_model = current_model or str(resumable.get("model_id") or "") or None
        current_run_id = current_run_id or str(resumable.get("run_id") or "") or None
    project_id = None
    if current_run_id:
        live = progress_by_run.get(current_run_id)
        if live and live.get("project_id"):
            project_id = str(live.get("project_id"))
    if project_id is None and resumable and resumable.get("project_id"):
        project_id = str(resumable.get("project_id"))
    elif project_id is None and current_run_id:
        ckpt = load_checkpoint(current_run_id)
        if ckpt and ckpt.get("project_id"):
            project_id = str(ckpt.get("project_id"))
    progress_src = progress_by_run.get(current_run_id) if current_run_id else None
    if progress_src is None:
        progress_src = last_progress
    return BenchActiveStatus(
        running=running,
        phase=phase,
        current_model=current_model,
        current_run_id=current_run_id,
        last_progress=_progress_model(progress_src),
        queue=queue_items,
        inflight=inflight_items,
        paused=paused_items,
        parallel_runs=parallel,
        resumable_run_id=(
            str(resumable["run_id"]) if resumable and resumable.get("run_id") else None
        ),
        project_id=project_id,
    )


def enqueue(deps: AppDeps, req: BenchSpawnRequest) -> list[str]:
    settings = SettingsService.get()
    models = list(req.models or [])
    if req.model:
        models.insert(0, req.model)
    if not models:
        models = [settings.model]
    seen: set[str] = set()
    uniq: list[str] = []
    for m in models:
        if m and m not in seen:
            seen.add(m)
            uniq.append(m)

    suites = [
        {"suite_id": s.suite_id, "sample_size": s.sample_size}
        for s in req.suites
    ]
    if not suites:
        raise ValueError("At least one suite is required")

    concurrency = max(1, int(req.concurrency or 1))
    cleanup = bool(req.cleanup_sessions) if req.cleanup_sessions is not None else False
    parallel = _clamp_parallel(req.parallel_runs)

    run_ids: list[str] = []
    with _state.lock:
        if parallel is not None:
            _state.max_parallel = parallel
        for model_id in uniq:
            job = BenchJob(
                run_id=new_run_id(),
                model_id=model_id,
                provider=resolve_bench_provider(
                    req.provider or settings.provider,
                    profile_id=getattr(settings, "openai_profile_id", None),
                )
                or req.provider
                or settings.provider,
                suites=suites,
                thinking=req.thinking,
                project_name=req.project_name,
                specialist_id=req.specialist_id,
                client_surface=req.client_surface or "ui",
                concurrency=concurrency,
                cleanup_sessions=cleanup,
            )
            _state.queue.append(job)
            run_ids.append(job.run_id)
    _pump(deps)
    return run_ids


def cancel_current() -> str | None:
    return cancel_run(None)


def cancel_run(run_id: str | None = None) -> str | None:
    """Cancel one stack (inflight, queued, or paused). Leaves the rest of the queue."""
    rid = None if not run_id or run_id == "active" else run_id
    queued_hit = False
    paused_ckpt: dict[str, Any] | None = None
    with _state.lock:
        if rid is None:
            if _state.inflight:
                rid = next(iter(_state.inflight))
            elif _state.paused:
                rid = next(iter(_state.paused))
            elif _state.queue:
                rid = _state.queue[0].run_id
            else:
                ckpt = find_resumable_checkpoint()
                if ckpt and ckpt.get("run_id"):
                    rid = str(ckpt["run_id"])
        if rid is None:
            return None
        if rid in _state.inflight:
            _state.cancel_ids.add(rid)
            _state.pause_ids.discard(rid)
        else:
            before = len(_state.queue)
            _state.queue = [job for job in _state.queue if job.run_id != rid]
            queued_hit = len(_state.queue) < before
        paused_ckpt = _state.paused.pop(rid, None)
        if (
            rid not in _state.inflight
            and not queued_hit
            and paused_ckpt is None
            and not _state.inflight
            and not _state.queue
            and not _state.paused
        ):
            _state.phase = "idle"
            _state.last_progress = None
        cancel_rid = rid

    if queued_hit:
        return cancel_rid

    if paused_ckpt is not None or cancel_rid not in _live_inflight_ids():
        _mark_cancelled(cancel_rid)
    return cancel_rid


def pause_current() -> str | None:
    return pause_run(None)


def pause_run(run_id: str | None = None) -> str | None:
    with _state.lock:
        rid = None if not run_id or run_id == "active" else run_id
        if rid is None:
            rid = next(iter(_state.inflight), None)
        if rid is None or rid not in _state.inflight:
            return None
        _state.pause_ids.add(rid)
        _state.cancel_ids.discard(rid)
        return rid


def request_bench_shutdown() -> list[threading.Thread]:
    """Mark every inflight suite paused so Ctrl+C does not start new cells."""
    with _state.lock:
        for rid in _state.inflight:
            _state.pause_ids.add(rid)
            _state.cancel_ids.discard(rid)
        return [thread for thread in _state.job_threads.values() if thread.is_alive()]


def resume_run(deps: AppDeps, run_id: str | None = None) -> str | None:
    """Resume a paused/interrupted checkpoint into the live queue."""
    with _state.lock:
        ckpt = None
        if run_id and run_id != "active":
            ckpt = _state.paused.get(run_id)
        if ckpt is None and run_id and run_id != "active":
            ckpt = load_checkpoint(run_id)
        if ckpt is None:
            ckpt = next(iter(_state.paused.values()), None)
        if ckpt is None:
            ckpt = find_resumable_checkpoint()
        if ckpt is None:
            raise ValueError("No resumable bench checkpoint found")
        rid = str(ckpt.get("run_id") or "")
        if not rid:
            raise ValueError("Checkpoint missing run_id")
        if rid in _state.inflight:
            raise ValueError("That bench run is already in progress")
        if any(job.run_id == rid for job in _state.queue):
            return rid
        suite_id = str(ckpt.get("suite_id") or "")
        job = BenchJob(
            run_id=rid,
            model_id=str(ckpt.get("model_id") or ""),
            provider=ckpt.get("provider"),
            suites=[
                {
                    "suite_id": suite_id,
                    "sample_size": ckpt.get("sample_size"),
                    "pack_id": ckpt.get("pack_id"),
                    "matrix": ckpt.get("matrix"),
                }
            ],
            thinking=bool(ckpt.get("thinking")),
            project_name=ckpt.get("project_name"),
            specialist_id=ckpt.get("specialist_id"),
            client_surface=str(ckpt.get("client_surface") or "ui"),
            concurrency=max(1, int(ckpt.get("concurrency") or 1)),
            cleanup_sessions=bool(ckpt.get("cleanup_sessions", False)),
            resume_checkpoint=ckpt,
        )
        _state.paused.pop(rid, None)
        _state.pause_ids.discard(rid)
        _state.cancel_ids.discard(rid)
        _state.queue.insert(0, job)
        if not _state.inflight:
            _state.phase = "loading"
    _pump(deps)
    return rid


def remove_queued(index: int) -> bool:
    with _state.lock:
        if 0 <= index < len(_state.queue):
            _state.queue.pop(index)
            return True
        return False


def _clamp_parallel(value: int | None) -> int | None:
    if value is None:
        return None
    return max(1, min(MAX_PARALLEL_RUNS, int(value)))


def _live_inflight_ids() -> set[str]:
    with _state.lock:
        return set(_state.inflight)


def live_run_statuses() -> dict[str, str]:
    """In-memory queue status keyed by run_id (running / queued / paused)."""
    with _state.lock:
        statuses = dict.fromkeys(_state.inflight, "running")
        for job in _state.queue:
            statuses[job.run_id] = "queued"
        for rid in _state.paused:
            statuses.setdefault(rid, "paused")
        return statuses


def _mark_cancelled(run_id: str) -> None:
    try:
        delete_checkpoint(run_id)
    except Exception:  # noqa: BLE001
        pass
    row = get_result(run_id)
    if row is not None:
        row["status"] = "cancelled"
        try:
            save_result(row)
        except Exception:  # noqa: BLE001
            pass


def _progress_model(src: dict[str, Any] | None) -> BenchProgress | None:
    if not src:
        return None
    return BenchProgress(**{k: src[k] for k in _PROGRESS_KEYS if src.get(k) is not None})


def _sample_sizes(suites: list[dict[str, Any]]) -> list[int | None]:
    out: list[int | None] = []
    for suite in suites:
        raw = suite.get("sample_size")
        if raw is None or raw == "":
            out.append(None)
            continue
        try:
            out.append(int(raw))
        except (TypeError, ValueError):
            out.append(None)
    return out


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _as_elapsed(raw: Any) -> float:
    try:
        return max(0.0, float(raw or 0))
    except (TypeError, ValueError):
        return 0.0


def _elapsed_base(job: BenchJob) -> float:
    ckpt = job.resume_checkpoint or {}
    raw = ckpt.get("elapsed_s")
    if raw is None:
        prior = get_result(job.run_id) or {}
        raw = prior.get("time_s")
    return _as_elapsed(raw)


def _ckpt_elapsed(ckpt: dict[str, Any]) -> float:
    raw = ckpt.get("elapsed_s")
    if raw is None:
        prior = get_result(str(ckpt.get("run_id") or "")) or {}
        raw = prior.get("time_s")
    return _as_elapsed(raw)


def _job_item(
    job: BenchJob,
    status: str,
    progress: dict[str, Any] | None = None,
) -> BenchQueueItem:
    if status == "running" and not job.started_at:
        job.started_at = _utc_now_iso()
        job.elapsed_s = _elapsed_base(job)
    return BenchQueueItem(
        run_id=job.run_id,
        model_id=job.model_id,
        suites=[str(s.get("suite_id") or "") for s in job.suites],
        sample_sizes=_sample_sizes(job.suites),
        status=status,  # type: ignore[arg-type]
        last_progress=_progress_model(progress),
        provider=job.provider,
        started_at=job.started_at if status == "running" else None,
        elapsed_s=job.elapsed_s if status == "running" else 0.0,
    )


def _disk_paused(*, exclude: set[str]) -> dict[str, dict[str, Any]]:
    """Paused/interrupted checkpoints that are not already queued or running."""
    out: dict[str, dict[str, Any]] = {}
    for ckpt in list_checkpoints():
        status = str(ckpt.get("status") or "")
        if status not in {"paused", "interrupted"}:
            continue
        rid = str(ckpt.get("run_id") or "")
        if rid and rid not in exclude:
            out[rid] = ckpt
    return out


def _ensure_paused_checkpoint(job: BenchJob) -> dict[str, Any]:
    """Keep a paused run resumable even if the suite never wrote a checkpoint."""
    ckpt = load_checkpoint(job.run_id)
    if ckpt is None:
        suite = (
            job.suites[min(job.suite_index, len(job.suites) - 1)]
            if job.suites
            else {}
        )
        ckpt = {
            "run_id": job.run_id,
            "status": "paused",
            "suite_id": str(suite.get("suite_id") or ""),
            "pack_id": suite.get("pack_id"),
            "matrix": suite.get("matrix"),
            "model_id": job.model_id,
            "provider": job.provider,
            "sample_size": suite.get("sample_size"),
            "project_name": job.project_name,
            "specialist_id": job.specialist_id,
            "thinking": job.thinking,
            "client_surface": job.client_surface,
            "concurrency": job.concurrency,
            "cleanup_sessions": job.cleanup_sessions,
            "completed_question_ids": [],
            "remaining_question_ids": [],
            "suite_index": job.suite_index,
        }
    else:
        ckpt = {**ckpt, "status": "paused"}
    try:
        save_checkpoint(ckpt)
    except Exception:  # noqa: BLE001
        logger.exception("failed to save pause checkpoint for %s", job.run_id)
    return ckpt


def _ckpt_item(ckpt: dict[str, Any]) -> BenchQueueItem:
    suite_id = str(ckpt.get("suite_id") or ckpt.get("benchmark") or "")
    sample = ckpt.get("sample_size")
    sample_sizes: list[int | None] = []
    if sample is not None and sample != "":
        try:
            sample_sizes = [int(sample)]
        except (TypeError, ValueError):
            sample_sizes = [None]
    return BenchQueueItem(
        run_id=str(ckpt.get("run_id") or ""),
        model_id=str(ckpt.get("model_id") or ""),
        suites=[suite_id] if suite_id else [],
        sample_sizes=sample_sizes,
        status="paused",
        last_progress=None,
        provider=str(ckpt.get("provider") or "") or None,
        started_at=None,
        elapsed_s=_ckpt_elapsed(ckpt),
    )


def _pump(deps: AppDeps) -> None:
    to_start: list[threading.Thread] = []
    with _state.lock:
        cap = max(1, _state.max_parallel)
        while _state.queue and len(_state.inflight) < cap:
            job = _state.queue.pop(0)
            _state.inflight[job.run_id] = job
            _state.phase = "loading"
            _state.cancel_ids.discard(job.run_id)
            if not job.resume_checkpoint:
                _state.pause_ids.discard(job.run_id)
            thread = threading.Thread(
                target=_job_thread,
                args=(deps, job),
                daemon=True,
                name=f"sandwalk-bench-{job.run_id[:8]}",
            )
            _state.job_threads[job.run_id] = thread
            to_start.append(thread)
    for thread in to_start:
        thread.start()


def _job_thread(deps: AppDeps, job: BenchJob) -> None:
    outcome = "error"
    try:
        outcome = _execute_job(deps, job)
    except Exception as exc:  # noqa: BLE001
        logger.exception("bench job failed: %s", exc)
        _emit(
            {
                "type": "error",
                "phase": "error",
                "model_id": job.model_id,
                "benchmark": "",
                "message": str(exc),
                "current": 0,
                "total": 0,
                "bench_current": 0,
                "bench_total": 0,
            },
            job.run_id,
        )
        outcome = "error"
    ckpt = _ensure_paused_checkpoint(job) if outcome == "paused" else None
    with _state.lock:
        _state.inflight.pop(job.run_id, None)
        _state.job_threads.pop(job.run_id, None)
        _state.cancel_ids.discard(job.run_id)
        _state.pause_ids.discard(job.run_id)
        if outcome == "paused" and ckpt is not None:
            _state.paused[job.run_id] = ckpt
        if not _state.inflight:
            if _state.paused and not _state.queue:
                _state.phase = "paused"
            elif not _state.queue:
                _state.phase = "idle"
    _pump(deps)


def _emit(progress: dict[str, Any], run_id: str | None = None) -> None:
    rid = run_id or progress.get("run_id")
    payload = dict(progress)
    if rid:
        payload["run_id"] = rid
    with _state.lock:
        if rid:
            _state.progress_by_run[str(rid)] = payload
        _state.last_progress = payload
        phase = str(payload.get("phase") or "")
        if _state.inflight:
            if phase in {"idle", "paused"} and len(_state.inflight) > 1:
                _state.phase = "running"
            elif phase and phase not in {"idle", "paused"}:
                _state.phase = phase
            else:
                _state.phase = "running"
        elif phase:
            _state.phase = phase
        _state.events.append(payload)
        if len(_state.events) > 500:
            _state.events = _state.events[-250:]


def _stop_reason(run_id: str) -> str | None:
    try:
        from agent_server.bench_service.runtime import is_bench_stopping

        if is_bench_stopping():
            return "pause"
    except Exception:  # noqa: BLE001
        pass
    with _state.lock:
        if run_id in _state.cancel_ids:
            return "cancel"
        if run_id in _state.pause_ids:
            return "pause"
        return None


def _execute_job(deps: AppDeps, job: BenchJob) -> str:
    """Run one stack. Tests assign ``_job_hook`` instead of patching this."""
    hook = _job_hook
    if hook is not None:
        return hook(deps, job)
    return _run_job(deps, job)


def _run_job(deps: AppDeps, job: BenchJob) -> str:
    suite_total = len(job.suites)
    start_idx = int(job.suite_index or 0)

    def stop_check() -> str | None:
        return _stop_reason(job.run_id)

    for s_idx in range(start_idx, suite_total):
        reason = stop_check()
        if reason == "cancel":
            return "cancelled"
        if reason == "pause":
            return "paused"
        suite = job.suites[s_idx]
        suite_id = str(suite["suite_id"])
        sample = suite.get("sample_size")
        _emit(
            {
                "type": "progress",
                "phase": "loading",
                "model_id": job.model_id,
                "benchmark": suite_id,
                "message": f"Starting {suite_id}...",
                "current": s_idx,
                "total": suite_total,
                "bench_current": 0,
                "bench_total": 0,
            },
            job.run_id,
        )
        pack_id = suite.get("pack_id")
        matrix = suite.get("matrix")
        if not pack_id:
            pack_id, matrix = _split_suite(suite_id)
        pinned = job.run_id if suite_total == 1 else (
            job.run_id if job.resume_checkpoint else None
        )
        if suite_total == 1:
            pinned = job.run_id
        resume = job.resume_checkpoint if s_idx == start_idx else None
        result = run_agent_suite(
            deps=deps,
            suite_id=suite_id,
            pack_id=str(pack_id),
            matrix=matrix,
            model_id=job.model_id,
            provider=job.provider,
            sample_size=int(sample) if sample else None,
            project_name=job.project_name,
            specialist_id=job.specialist_id,
            thinking=job.thinking,
            client_surface=job.client_surface,
            run_id=pinned,
            on_progress=lambda p, idx=s_idx: _emit(
                {**p, "current": idx, "total": suite_total},
                job.run_id,
            ),
            stop_check=stop_check,
            concurrency=job.concurrency,
            cleanup_sessions=job.cleanup_sessions,
            resume_checkpoint=resume,
        )
        status = str((result or {}).get("status") or "completed")
        if status == "paused":
            return "paused"
        if status == "cancelled":
            return "cancelled"
        job.resume_checkpoint = None
    return "completed"


def _split_suite(suite_id: str) -> tuple[str, str | None]:
    if suite_id in {
        "mmlu",
        "mmlu-pro",
        "arc-challenge",
        "mbpp",
        "livecodebench",
        "bixbench-verified-50",
    }:
        return suite_id, None
    if ":" in suite_id:
        pack, matrix = suite_id.split(":", 1)
        return pack, matrix
    return suite_id, None
