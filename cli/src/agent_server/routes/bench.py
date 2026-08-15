"""Bench catalog, spawn queue, progress, and results routes."""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from agent_server.app_deps import AppDeps
from agent_server.bench_service import (
    apply_live_status,
    bootstrap_resumable,
    cancel_run,
    clear_results,
    delete_result,
    enqueue,
    export_path,
    get_active_status,
    get_result,
    list_results_page,
    list_suite_cards,
    pause_run,
    remove_queued,
    rename_result,
    resume_run,
    start_install,
)
from agent_server.bench_service.dataset_install import (
    BenchInstallError,
    cache_root,
    total_cache_bytes,
    uninstall_suite,
)
from agent_server.bench_service.results_store import _provider_from_row, slice_page
from agent_server.models.bench import (
    BenchActiveStatus,
    BenchCancelResponse,
    BenchGradeRequest,
    BenchGradeResponse,
    BenchInstallResponse,
    BenchPauseResponse,
    BenchResetResponse,
    BenchResultList,
    BenchResultSummary,
    BenchResumeResponse,
    BenchRunPatchRequest,
    BenchSpawnRequest,
    BenchSpawnResponse,
    BenchSuiteCard,
    BenchSuiteList,
    BenchUninstallResponse,
)


def _packs_payload(store: object) -> tuple[list[BenchSuiteCard], int, str | None]:
    """Suite cards plus cache totals, computed together off the event loop."""
    cards = list_suite_cards(store)
    root = cache_root()
    return cards, total_cache_bytes(), (str(root) if root is not None else None)


def register_bench_routes(app: FastAPI, deps: AppDeps) -> None:
    # Advertise any leftover checkpoint from a prior process.
    bootstrap_resumable()

    @app.get("/v1/bench/packs", response_model=BenchSuiteList)
    async def bench_packs() -> BenchSuiteList:
        cards, cache_bytes, cache_path = await asyncio.to_thread(
            _packs_payload, deps.store
        )
        return BenchSuiteList(
            data=cards, cache_bytes=cache_bytes, cache_path=cache_path
        )

    @app.post(
        "/v1/bench/packs/{suite_id}/install",
        response_model=BenchInstallResponse,
    )
    async def bench_pack_install(suite_id: str) -> BenchInstallResponse:
        # Start a daemon thread and return immediately so leaving the page
        # does not cancel the download.
        try:
            return await asyncio.to_thread(start_install, suite_id)
        except BenchInstallError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={
                    "message": str(exc),
                    "needsHfToken": exc.needs_hf_token,
                    "suiteId": suite_id,
                },
            ) from exc

    @app.delete(
        "/v1/bench/packs/{suite_id}/install",
        response_model=BenchUninstallResponse,
    )
    async def bench_pack_uninstall(suite_id: str) -> BenchUninstallResponse:
        try:
            return await asyncio.to_thread(uninstall_suite, suite_id)
        except BenchInstallError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"message": str(exc), "suiteId": suite_id},
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
    async def bench_runs(
        q: str | None = None,
        suite: str | None = None,
        status: str | None = None,
        provider: str | None = None,
        sort: str = "date_desc",
        cursor: str | None = None,
        limit: int = 25,
    ) -> BenchResultList:
        sort_key = (sort or "date_desc").strip().lower()
        usage_sort = sort_key in {"usage_desc", "usage_asc"}
        date_sort = "date_asc" if sort_key == "date_asc" else "date_desc"
        page = await asyncio.to_thread(
            list_results_page,
            limit=limit,
            cursor=None if usage_sort else cursor,
            q=q,
            suite=suite,
            status=status,
            provider=provider,
            sort=date_sort,
            paginate=not usage_sort,
        )
        ids = [
            str(row.get("project_id") or "")
            for row in page["data"]
            if row.get("project_id")
        ]
        tokens = await asyncio.to_thread(
            deps.store.lifetime_tokens_by_project, ids
        )
        rows = list(page["data"])
        if usage_sort:
            reverse = sort_key == "usage_desc"

            def usage_key(row: dict) -> tuple[int, str]:
                pid = str(row.get("project_id") or "")
                n = int(tokens.get(pid) or 0) if pid else 0
                return (n, str(row.get("run_id") or ""))

            rows.sort(key=usage_key, reverse=reverse)
            sliced = slice_page(rows, limit=limit, cursor=cursor)
            rows = sliced["data"]
            page["next_cursor"] = sliced["next_cursor"]
            page["total"] = sliced["total"]
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
                status=r.get("status"),
                reasoning_effort=(
                    str(r["reasoning_effort"])
                    if r.get("reasoning_effort") not in (None, "")
                    else None
                ),
                reasoning_fast=(
                    bool(r["reasoning_fast"])
                    if r.get("reasoning_fast") is not None
                    else None
                ),
                name=(str(r["name"]) if r.get("name") not in (None, "") else None),
                provider=(
                    str(r["provider"]) if r.get("provider") not in (None, "") else None
                ),
                lifetime_tokens=(
                    tokens.get(str(r.get("project_id") or ""))
                    if r.get("project_id")
                    else None
                ),
            )
            for r in rows
        ]
        return BenchResultList(
            data=data,
            next_cursor=page.get("next_cursor"),
            total=int(page.get("total") or 0),
            providers=list(page.get("providers") or []),
        )

    @app.get("/v1/bench/runs/{run_id}")
    async def bench_run_detail(run_id: str) -> dict:
        row = await asyncio.to_thread(get_result, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        live = apply_live_status(row)
        provider = _provider_from_row(live)
        if provider:
            live = {**live, "provider": provider}
        project_id = str(live.get("project_id") or "")
        if project_id:
            tokens = await asyncio.to_thread(
                deps.store.lifetime_tokens_by_project, [project_id]
            )
            live = {
                **live,
                "lifetime_tokens": tokens.get(project_id),
            }
        return live

    @app.patch("/v1/bench/runs/{run_id}")
    async def bench_run_patch(run_id: str, body: BenchRunPatchRequest) -> dict:
        if body.name is None:
            raise HTTPException(status_code=400, detail="Nothing to update.")
        row = await asyncio.to_thread(rename_result, run_id, body.name)
        if row is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        return {"ok": True, "runId": run_id, "name": row.get("name")}

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
        rid = await asyncio.to_thread(cancel_run, run_id)
        return BenchCancelResponse(ok=True, run_id=rid or run_id)

    @app.post("/v1/bench/runs/{run_id}/pause", response_model=BenchPauseResponse)
    async def bench_pause(run_id: str) -> BenchPauseResponse:
        rid = await asyncio.to_thread(pause_run, run_id)
        if rid is None:
            raise HTTPException(status_code=409, detail="No active run to pause.")
        return BenchPauseResponse(ok=True, run_id=rid)

    @app.post("/v1/bench/runs/{run_id}/resume", response_model=BenchResumeResponse)
    async def bench_resume(run_id: str) -> BenchResumeResponse:
        try:
            rid = await asyncio.to_thread(resume_run, deps, run_id if run_id != "active" else None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return BenchResumeResponse(ok=True, run_id=rid)

    @app.delete("/v1/bench/runs/{run_id}")
    async def bench_delete_run(run_id: str) -> dict:
        ok = await asyncio.to_thread(
            delete_result, run_id, store=deps.store, delete_sessions=True
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Run not found.")
        return {"ok": True}

    @app.delete("/v1/bench/queue/{index}")
    async def bench_queue_remove(index: int) -> dict:
        ok = await asyncio.to_thread(remove_queued, index)
        if not ok:
            raise HTTPException(status_code=404, detail="Queue index not found.")
        return {"ok": True}

    @app.post("/v1/bench/results/reset", response_model=BenchResetResponse)
    async def bench_reset() -> BenchResetResponse:
        cleared, sessions = await asyncio.to_thread(clear_results, store=deps.store)
        return BenchResetResponse(ok=True, cleared=cleared, sessions_deleted=sessions)

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
                    "resumableRunId": status.resumable_run_id,
                }
                blob = json.dumps(payload)
                if blob != last:
                    yield f"data: {blob}\n\n"
                    last = blob
                if not status.running and status.current_run_id != run_id:
                    # finished or never started
                    if get_result(run_id) is not None and status.phase != "paused":
                        yield f"data: {json.dumps({'type': 'done', 'runId': run_id})}\n\n"
                        return
                if not status.running:
                    idle_ticks += 1
                else:
                    idle_ticks = 0
                await asyncio.sleep(0.5)

        return StreamingResponse(gen(), media_type="text/event-stream")
