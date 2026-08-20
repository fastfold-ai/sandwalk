"""Workspace-items index route (FAS-107).

Single endpoint the tab strip / sidebar / split picker call to list every
pane-able thing in a project without UNIONing per kind. Detail (per-chat
messages, per-terminal cwd, etc.) is hydrated from the kind's own endpoint
on demand.
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI

from agent_server.app_deps import AppDeps
from agent_server.models import WorkspaceItemList


def register_workspace_item_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get("/v1/workspace-items", response_model=WorkspaceItemList)
    async def list_workspace_items(
        project_id: str | None = None,
        kind: str | None = None,
        limit: int = 200,
    ) -> WorkspaceItemList:
        kinds = None
        if kind:
            kinds = [k.strip() for k in kind.split(",") if k.strip()]  # type: ignore[assignment]
        rows = await asyncio.to_thread(
            store.list_workspace_items,
            project_id=project_id,
            kinds=kinds,
            limit=limit,
        )
        return WorkspaceItemList(data=rows)
