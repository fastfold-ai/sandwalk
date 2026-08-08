"""Bench catalog, spawn queue, progress, and results routes."""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from agent_server.app_deps import AppDeps
from agent_server.bench_service import (
    cancel_current,
    clear_results,
    enqueue,
    export_path,
    get_active_status,
    get_result,
    install_suite,
    list_results,
    list_suite_cards,
    remove_queued,
)
from agent_server.bench_service.dataset_install import BenchInstallError
from agent_server.models.bench import (
    BenchActiveStatus,
    BenchCancelResponse,
    BenchGradeRequest,
    BenchGradeResponse,
    BenchInstallResponse,
    BenchResetResponse,
    BenchResultList,
    BenchResultSummary,
    BenchSpawnRequest,
    BenchSpawnResponse,
    BenchSuiteList,
)


def register_bench_routes(app: FastAPI, deps: AppDeps) -> None:
    @app.get("/v1/bench/packs", response_model=BenchSuiteList)
    async def bench_packs() -> BenchSuiteList:
        return BenchSuiteList(
            data=await asyncio.to_thread(list_suite_cards, deps.store)
        )

    @app.post(
        "/v1/bench/packs/{suite_id}/install",
        response_model=BenchInstallResponse,
    )
    async def bench_pack_install(suite_id: str) -> BenchInstallResponse:
        try:
            return await asyncio.to_thread(install_suite, suite_id)
        except BenchInstallError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={
                    "message": str(exc),
                    "needsHfToken": exc.needs_hf_token,
                    "suiteId": suite_id,
                },
            ) from exc

    @app.post("/v1/bench/spawn", response_model=BenchSpawnResponse)
    async def bench_spawn(payload: BenchSpawnRequest) -> BenchSpawnResponse:
        if payload.dry_run:
            models = list(payload.models or [])
            if payload.model:
                models.insert(0, payload.model)
            if not models:
                from agent_server.settings_service import SettingsService

                models = [SettingsService.get().model]
            return BenchSpawnResponse(run_ids=["dry-run"], queued=len(models))
        try:
            run_ids = await asyncio.to_thread(enqueue, deps, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return BenchSpawnResponse(run_ids=run_ids, queued=len(run_ids))

    @app.get("/v1/bench/runs/active", response_model=BenchActiveStatus)
    async def bench_active() -> BenchActiveStatus:
        return await asyncio.to_thread(get_active_status)

    @app.get("/v1/bench/runs", response_model=BenchResultList)
    async def bench_runs() -> BenchResultList:
        rows = await asyncio.to_thread(list_results)
        data = [
            BenchResultSummary(
                run_id=str(r.get("run_id") or ""),
                model_id=str(r.get("model_id") or ""),
                benchmark=str(r.get("benchmark") or ""),
                accuracy=float(r.get("accuracy") or 0),
                correct=int(r.get("correct") or 0),
                total=int(r.get("total") or 0),
                time_s=float(r.get("time_s") or 0),
                thinking_used=bool(r.get("thinking_used")),
                project_id=r.get("project_id"),
                created_at=r.get("created_at"),
            )
            for r in rows
        ]
        return BenchResultList(data=data)

    @app.get("/v1/bench/runs/{run_id}")
    async def bench_run_detail(run_id: str) -> dict:
        row = await asyncio.to_thread(get_result, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        return row

    @app.get("/v1/bench/runs/{run_id}/export")
    async def bench_export(run_id: str) -> FileResponse:
        path = await asyncio.to_thread(export_path, run_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        row = await asyncio.to_thread(get_result, run_id) or {}
        model = str(row.get("model_id") or "model").replace("/", "_")
        bench = str(row.get("benchmark") or "bench").replace(":", "_").replace("/", "_")
        filename = f"{model}_{bench}.json"
        return FileResponse(path, filename=filename, media_type="application/json")

    @app.post("/v1/bench/runs/{run_id}/cancel", response_model=BenchCancelResponse)
    async def bench_cancel(run_id: str) -> BenchCancelResponse:
        # Cancel active regardless of id match (queue is single-active)
        rid = await asyncio.to_thread(cancel_current)
        return BenchCancelResponse(ok=True, run_id=rid or run_id)

    @app.delete("/v1/bench/queue/{index}")
    async def bench_queue_remove(index: int) -> dict:
        ok = await asyncio.to_thread(remove_queued, index)
        if not ok:
            raise HTTPException(status_code=404, detail="Queue index not found.")
        return {"ok": True}

    @app.post("/v1/bench/results/reset", response_model=BenchResetResponse)
    async def bench_reset() -> BenchResetResponse:
        n = await asyncio.to_thread(clear_results)
        return BenchResetResponse(ok=True, cleared=n)

    @app.post("/v1/bench/grade", response_model=BenchGradeResponse)
    async def bench_grade(payload: BenchGradeRequest) -> BenchGradeResponse:
        if payload.run_id:
            row = await asyncio.to_thread(get_result, payload.run_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Run not found.")
            return BenchGradeResponse(ok=True, detail="already graded", result=row)
        return BenchGradeResponse(ok=False, detail="session re-grade not implemented yet")

    @app.get("/v1/bench/runs/{run_id}/stream")
    async def bench_stream(run_id: str) -> StreamingResponse:
        async def gen():
            last = None
            idle_ticks = 0
            while idle_ticks < 1200:
                status = await asyncio.to_thread(get_active_status)
                prog = status.last_progress.model_dump(by_alias=True) if status.last_progress else None
                payload = {
                    "runId": status.current_run_id,
                    "running": status.running,
                    "phase": status.phase,
                    "progress": prog,
                }
                blob = json.dumps(payload)
                if blob != last:
                    yield f"data: {blob}\n\n"
                    last = blob
                if not status.running and status.current_run_id != run_id:
                    # finished or never started
                    if get_result(run_id) is not None:
                        yield f"data: {json.dumps({'type': 'done', 'runId': run_id})}\n\n"
                        return
                if not status.running:
                    idle_ticks += 1
                else:
                    idle_ticks = 0
                await asyncio.sleep(0.5)

        return StreamingResponse(gen(), media_type="text/event-stream")
