"""Server-side bench queue (sequential jobs)."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from agent_server.app_deps import AppDeps
from agent_server.bench_service.spawn_core import run_agent_suite
from agent_server.models.bench import (
    BenchActiveStatus,
    BenchProgress,
    BenchQueueItem,
    BenchSpawnRequest,
)
from agent_server.bench_service.results_store import new_run_id
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


@dataclass
class BenchQueueState:
    queue: list[BenchJob] = field(default_factory=list)
    current: BenchJob | None = None
    last_progress: dict[str, Any] | None = None
    phase: str = "idle"
    cancel_requested: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)
    worker: threading.Thread | None = None
    cond: asyncio.Condition | None = None
    events: list[dict[str, Any]] = field(default_factory=list)


_state = BenchQueueState()


def get_active_status() -> BenchActiveStatus:
    with _state.lock:
        progress = None
        if _state.last_progress:
            progress = BenchProgress(**{
                k: _state.last_progress.get(k)
                for k in (
                    "type",
                    "phase",
                    "model_id",
                    "benchmark",
                    "message",
                    "current",
                    "total",
                    "bench_current",
                    "bench_total",
                )
                if _state.last_progress.get(k) is not None
            })
        return BenchActiveStatus(
            running=_state.current is not None,
            phase=_state.phase,
            current_model=_state.current.model_id if _state.current else None,
            current_run_id=_state.current.run_id if _state.current else None,
            last_progress=progress,
            queue=[
                BenchQueueItem(
                    run_id=j.run_id,
                    model_id=j.model_id,
                    suites=[s.get("suite_id", "") for s in j.suites],
                )
                for j in _state.queue
            ],
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
            )
            _state.queue.append(job)
            run_ids.append(job.run_id)
        _ensure_worker(deps)
    return run_ids


def cancel_current() -> str | None:
    with _state.lock:
        _state.cancel_requested = True
        rid = _state.current.run_id if _state.current else None
        _state.queue.clear()
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


def _cancelled() -> bool:
    with _state.lock:
        return _state.cancel_requested


def _worker_loop(deps: AppDeps) -> None:
    while True:
        with _state.lock:
            if not _state.queue:
                _state.current = None
                _state.phase = "idle"
                _state.cancel_requested = False
                _state.worker = None
                return
            job = _state.queue.pop(0)
            _state.current = job
            _state.phase = "loading"
            _state.cancel_requested = False
        try:
            _run_job(deps, job)
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
        with _state.lock:
            _state.current = None


def _run_job(deps: AppDeps, job: BenchJob) -> None:
    suite_total = len(job.suites)
    for s_idx, suite in enumerate(job.suites):
        if _cancelled():
            return
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
        pack_id, matrix = _split_suite(suite_id)
        # One queue job may cover multiple suites; only pin run_id when
        # there is a single suite so spawn response ids match result files.
        pinned = job.run_id if suite_total == 1 else None
        run_agent_suite(
            deps=deps,
            suite_id=suite_id,
            pack_id=pack_id,
            matrix=matrix,
            model_id=job.model_id,
            provider=job.provider,
            sample_size=int(sample) if sample else None,
            project_name=job.project_name,
            specialist_id=job.specialist_id,
            run_id=pinned,
            on_progress=lambda p, idx=s_idx: _emit({**p, "current": idx, "total": suite_total}),
            cancel_check=_cancelled,
        )


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
