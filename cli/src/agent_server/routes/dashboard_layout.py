"""Dashboard Overview widget layout (host preference)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import Field

from agent_server.app_deps import AppDeps
from agent_server.models.base import ApiModel
from agent_server.widget_layout import (
    DASHBOARD_LAYOUT_META_KEY,
    resolve_overview_layout,
)


class DashboardLayoutResponse(ApiModel):
    layout: dict[str, Any]


class DashboardLayoutUpdate(ApiModel):
    layout: dict[str, Any] = Field(...)


def register_dashboard_layout_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get("/v1/settings/dashboard-layout", response_model=DashboardLayoutResponse)
    async def get_dashboard_layout() -> DashboardLayoutResponse:
        def _read() -> dict[str, Any]:
            raw = store.get_usage_meta(DASHBOARD_LAYOUT_META_KEY)
            return resolve_overview_layout(raw)

        return DashboardLayoutResponse(layout=await asyncio.to_thread(_read))

    @app.put("/v1/settings/dashboard-layout", response_model=DashboardLayoutResponse)
    async def put_dashboard_layout(
        payload: DashboardLayoutUpdate,
    ) -> DashboardLayoutResponse:
        layout = payload.layout
        if not isinstance(layout, dict) or not isinstance(layout.get("widgets"), list):
            raise HTTPException(
                status_code=400,
                detail="layout must be an object with a widgets array.",
            )
        normalized = {
            "version": int(layout.get("version") or 1),
            "widgets": layout["widgets"],
        }

        def _write() -> dict[str, Any]:
            store.set_usage_meta(
                DASHBOARD_LAYOUT_META_KEY,
                json.dumps(normalized, separators=(",", ":")),
            )
            return normalized

        return DashboardLayoutResponse(layout=await asyncio.to_thread(_write))
