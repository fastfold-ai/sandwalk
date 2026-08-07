"""Usage overview + backfill routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI

from agent_server.app_deps import AppDeps
from agent_server.models.usage import UsageBackfillResponse, UsageOverview
from agent_server.usage_service import build_usage_overview, run_backfill


def register_usage_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get("/v1/usage/overview", response_model=UsageOverview)
    async def usage_overview() -> UsageOverview:
        return await asyncio.to_thread(build_usage_overview, store)

    @app.post("/v1/usage/backfill", response_model=UsageBackfillResponse)
    async def usage_backfill() -> UsageBackfillResponse:
        return await asyncio.to_thread(run_backfill, store, force=True)
