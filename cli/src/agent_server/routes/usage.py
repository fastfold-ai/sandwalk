"""Usage overview + backfill routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI

from agent_server import ttl_cache
from agent_server.app_deps import AppDeps
from agent_server.models.usage import UsageBackfillResponse, UsageOverview
from agent_server.usage_service import build_usage_overview, run_backfill

_USAGE_OVERVIEW_TTL_S = 30.0
_USAGE_CACHE_KEY = "usage:overview"


def register_usage_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get("/v1/usage/overview", response_model=UsageOverview)
    async def usage_overview() -> UsageOverview:
        def _build() -> UsageOverview:
            return ttl_cache.cached(
                _USAGE_CACHE_KEY,
                _USAGE_OVERVIEW_TTL_S,
                lambda: build_usage_overview(store),
            )

        return await asyncio.to_thread(_build)

    @app.post("/v1/usage/backfill", response_model=UsageBackfillResponse)
    async def usage_backfill() -> UsageBackfillResponse:
        result = await asyncio.to_thread(run_backfill, store, force=True)
        ttl_cache.invalidate(_USAGE_CACHE_KEY)
        return result
