"""`/v1/datasets/*` and `/v1/tools/*` routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, Query

from agent_server.app_deps import AppDeps
from agent_server.models import (
    DatasetInstallResponse,
    DatasetList,
    ToolBatchActionRequest,
    ToolBatchActionResponse,
    ToolList,
    ToolSummary,
    UpdateToolRequest,
)


def register_dataset_tool_routes(app: FastAPI, deps: AppDeps) -> None:
    datasets_service = deps.datasets_service
    tools_service = deps.tools_service

    @app.get("/v1/datasets", response_model=DatasetList)
    async def list_datasets() -> DatasetList:
        return await asyncio.to_thread(datasets_service.list_datasets)

    @app.post("/v1/datasets/{dataset_id}/install", response_model=DatasetInstallResponse)
    async def install_dataset(dataset_id: str) -> DatasetInstallResponse:
        try:
            return await asyncio.to_thread(datasets_service.install, dataset_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Unknown dataset '{dataset_id}'."
            ) from exc

    @app.delete("/v1/datasets/{dataset_id}", response_model=DatasetInstallResponse)
    async def remove_dataset(dataset_id: str) -> DatasetInstallResponse:
        try:
            return await asyncio.to_thread(datasets_service.remove, dataset_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Unknown dataset '{dataset_id}'."
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/tools", response_model=ToolList)
    async def list_tools(
        enabled_only: bool = Query(default=False),
    ) -> ToolList:
        return await asyncio.to_thread(
            tools_service.list_tools, enabled_only=enabled_only
        )

    @app.post("/v1/tools/batch", response_model=ToolBatchActionResponse)
    async def batch_tools(
        payload: ToolBatchActionRequest,
    ) -> ToolBatchActionResponse:
        return await asyncio.to_thread(
            tools_service.batch_action, payload.action, payload.ids
        )

    @app.patch("/v1/tools/{tool_id:path}", response_model=ToolSummary)
    async def update_tool(tool_id: str, payload: UpdateToolRequest) -> ToolSummary:
        try:
            return await asyncio.to_thread(tools_service.update_tool, tool_id, payload)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Unknown tool '{tool_id}'."
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
