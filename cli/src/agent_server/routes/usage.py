"""Usage overview + backfill routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, Query

from agent_server import ttl_cache
from agent_server.app_deps import AppDeps
from agent_server.models.usage import UsageBackfillResponse, UsageOverview
from agent_server.usage_service import build_usage_overview, run_backfill

_USAGE_OVERVIEW_TTL_S = 30.0
_USAGE_CACHE_KEY = "usage:overview"


def _cache_key(project_id: str | None) -> str:
    scoped = (project_id or "").strip()
    if scoped:
        return f"{_USAGE_CACHE_KEY}:project:{scoped}"
    return _USAGE_CACHE_KEY


def register_usage_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get("/v1/usage/overview", response_model=UsageOverview)
    async def usage_overview(
        project_id: str | None = Query(default=None, alias="projectId"),
    ) -> UsageOverview:
        scoped = (project_id or "").strip() or None

        def _build() -> UsageOverview:
            return ttl_cache.cached(
                _cache_key(scoped),
                _USAGE_OVERVIEW_TTL_S,
                lambda: build_usage_overview(store, project_id=scoped),
            )

        return await asyncio.to_thread(_build)

    @app.post("/v1/usage/backfill", response_model=UsageBackfillResponse)
    async def usage_backfill() -> UsageBackfillResponse:
        result = await asyncio.to_thread(run_backfill, store, force=True)
        ttl_cache.invalidate(_USAGE_CACHE_KEY)
        return result
