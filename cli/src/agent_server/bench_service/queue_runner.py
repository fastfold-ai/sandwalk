"""Server-side bench queue (sequential jobs, parallel cells)."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from agent_server.app_deps import AppDeps
from agent_server.bench_service.checkpoint import (
    find_resumable_checkpoint,
    load_checkpoint,
    save_checkpoint,
)
from agent_server.bench_service.results_store import new_run_id
from agent_server.bench_service.spawn_core import run_agent_suite
from agent_server.models.bench import (
    BenchActiveStatus,
    BenchProgress,
    BenchQueueItem,
    BenchSpawnRequest,
)
from agent_server.settings_service import SettingsService

logger = logging.getLogger(__name__)


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


@dataclass
class BenchQueueState:
    queue: list[BenchJob] = field(default_factory=list)
    current: BenchJob | None = None
    last_progress: dict[str, Any] | None = None
    phase: str = "idle"
    cancel_requested: bool = False
    pause_requested: bool = False
    resumable: dict[str, Any] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    worker: threading.Thread | None = None
    cond: asyncio.Condition | None = None
    events: list[dict[str, Any]] = field(default_factory=list)


_state = BenchQueueState()


def bootstrap_resumable() -> None:
    """On serve boot, advertise a paused/interrupted checkpoint if present."""
    with _state.lock:
        if _state.current is not None or _state.queue:
            return
        if _state.resumable is not None:
            return
        ckpt = find_resumable_checkpoint()
        if ckpt is None:
            return
        status = str(ckpt.get("status") or "")
        if status == "running":
            ckpt = {**ckpt, "status": "interrupted"}
            try:
                save_checkpoint(ckpt)
            except Exception:  # noqa: BLE001
                pass
        _state.resumable = ckpt
        _state.phase = "paused"
        _state.last_progress = {
            "type": "progress",
            "phase": "paused",
            "model_id": str(ckpt.get("model_id") or ""),
            "benchmark": str(ckpt.get("benchmark") or ckpt.get("suite_id") or ""),
            "message": "Paused — resume to continue",
            "current": 0,
            "total": 1,
            "bench_current": len(ckpt.get("completed_question_ids") or []),
            "bench_total": len(ckpt.get("completed_question_ids") or [])
            + len(ckpt.get("remaining_question_ids") or []),
        }


def get_active_status() -> BenchActiveStatus:
    with _state.lock:
        progress = None
        src = _state.last_progress
        if src:
            keys = (
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
            )
            progress = BenchProgress(
                **{k: src[k] for k in keys if src.get(k) is not None}
            )
        resumable = _state.resumable
        running = _state.current is not None
        phase = _state.phase
        current_model = _state.current.model_id if _state.current else None
        current_run_id = _state.current.run_id if _state.current else None
        if not running and resumable:
            phase = "paused"
            current_model = current_model or str(resumable.get("model_id") or "") or None
            current_run_id = current_run_id or str(resumable.get("run_id") or "") or None
        project_id = None
        if resumable and resumable.get("project_id"):
            project_id = str(resumable.get("project_id"))
        elif current_run_id:
            ckpt = load_checkpoint(current_run_id)
            if ckpt and ckpt.get("project_id"):
                project_id = str(ckpt.get("project_id"))
        return BenchActiveStatus(
            running=running,
            phase=phase,
            current_model=current_model,
            current_run_id=current_run_id,
            last_progress=progress,
            queue=[
                BenchQueueItem(
                    run_id=j.run_id,
                    model_id=j.model_id,
                    suites=[s.get("suite_id", "") for s in j.suites],
                )
                for j in _state.queue
            ],
            resumable_run_id=str(resumable["run_id"]) if resumable and resumable.get("run_id") else None,
            project_id=project_id,
        )


def enqueue(deps: AppDeps, req: BenchSpawnRequest) -> list[str]:
    settings = SettingsService.get()
    models = list(req.models or [])
    if req.model:
        models.insert(0, req.model)
    if not models:
        models = [settings.model]
    # dedupe preserve order
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

    run_ids: list[str] = []
    with _state.lock:
        for model_id in uniq:
            job = BenchJob(
                run_id=new_run_id(),
                model_id=model_id,
                provider=req.provider or settings.provider,
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
        _ensure_worker(deps)
    return run_ids


def cancel_current() -> str | None:
    from agent_server.bench_service.checkpoint import (
        delete_checkpoint,
        find_resumable_checkpoint,
    )
    from agent_server.bench_service.results_store import get_result, save_result

    with _state.lock:
        _state.cancel_requested = True
        _state.pause_requested = False
        rid = _state.current.run_id if _state.current else None
        if rid is None and _state.resumable:
            rid = str(_state.resumable.get("run_id") or "") or None
        if rid is None:
            ckpt = find_resumable_checkpoint()
            if ckpt and ckpt.get("run_id"):
                rid = str(ckpt["run_id"])
        # Always drop paused/resumable UI state — Cancel after Pause must clear
        # the card even when the in-memory resumable pointer was already None.
        was_paused = _state.phase == "paused" or _state.resumable is not None
        _state.resumable = None
        if _state.current is None:
            _state.phase = "idle"
            _state.last_progress = None
        _state.queue.clear()
        cancel_rid = rid

    if cancel_rid:
        try:
            delete_checkpoint(cancel_rid)
        except Exception:  # noqa: BLE001
            pass
        # If the run was already paused (no live worker), mark the partial
        # result cancelled so it does not look like an active suite.
        if was_paused:
            row = get_result(cancel_rid)
            if row is not None:
                row["status"] = "cancelled"
                try:
                    save_result(row)
                except Exception:  # noqa: BLE001
                    pass
    return cancel_rid


def pause_current() -> str | None:
    with _state.lock:
        if _state.current is None:
            return None
        _state.pause_requested = True
        _state.cancel_requested = False
        return _state.current.run_id


def resume_run(deps: AppDeps, run_id: str | None = None) -> str | None:
    """Resume a paused/interrupted checkpoint into the live queue."""
    with _state.lock:
        if _state.current is not None:
            raise ValueError("A bench run is already in progress")
        ckpt = _state.resumable
        if ckpt is None or (run_id and str(ckpt.get("run_id")) != run_id):
            ckpt = load_checkpoint(run_id) if run_id else find_resumable_checkpoint()
        if ckpt is None:
            raise ValueError("No resumable bench checkpoint found")
        rid = str(ckpt.get("run_id") or "")
        if not rid:
            raise ValueError("Checkpoint missing run_id")
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
        _state.resumable = None
        _state.pause_requested = False
        _state.cancel_requested = False
        _state.queue.insert(0, job)
        _state.phase = "loading"
        _ensure_worker(deps)
        return rid


def remove_queued(index: int) -> bool:
    with _state.lock:
        if 0 <= index < len(_state.queue):
            _state.queue.pop(index)
            return True
        return False


def _ensure_worker(deps: AppDeps) -> None:
    if _state.worker and _state.worker.is_alive():
        return
    t = threading.Thread(target=_worker_loop, args=(deps,), daemon=True, name="sandwalk-bench")
    _state.worker = t
    t.start()


def _emit(progress: dict[str, Any]) -> None:
    with _state.lock:
        _state.last_progress = progress
        _state.phase = str(progress.get("phase") or _state.phase)
        _state.events.append(progress)
        if len(_state.events) > 500:
            _state.events = _state.events[-250:]


def _stop_reason() -> str | None:
    with _state.lock:
        if _state.cancel_requested:
            return "cancel"
        if _state.pause_requested:
            return "pause"
        return None


def _worker_loop(deps: AppDeps) -> None:
    while True:
        with _state.lock:
            if not _state.queue:
                _state.current = None
                if _state.resumable is None:
                    _state.phase = "idle"
                else:
                    _state.phase = "paused"
                _state.cancel_requested = False
                _state.pause_requested = False
                _state.worker = None
                return
            job = _state.queue.pop(0)
            _state.current = job
            _state.phase = "loading"
            _state.cancel_requested = False
            # Keep pause_requested false when starting; resume clears it.
            if not job.resume_checkpoint:
                _state.pause_requested = False
            _state.resumable = None
        try:
            outcome = _run_job(deps, job)
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
                }
            )
            outcome = "error"
        with _state.lock:
            _state.current = None
            if outcome == "paused":
                ckpt = load_checkpoint(job.run_id)
                _state.resumable = ckpt
                _state.phase = "paused"
                _state.pause_requested = False
                # Keep remaining queued jobs; stop the worker until Resume.
                _state.worker = None
                return


def _run_job(deps: AppDeps, job: BenchJob) -> str:
    suite_total = len(job.suites)
    start_idx = int(job.suite_index or 0)
    for s_idx in range(start_idx, suite_total):
        reason = _stop_reason()
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
            }
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
                {**p, "current": idx, "total": suite_total}
            ),
            stop_check=_stop_reason,
            concurrency=job.concurrency,
            cleanup_sessions=job.cleanup_sessions,
            resume_checkpoint=resume,
        )
        status = str((result or {}).get("status") or "completed")
        if status == "paused":
            return "paused"
        if status == "cancelled":
            return "cancelled"
        # Only apply resume checkpoint to the first suite after resume.
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
