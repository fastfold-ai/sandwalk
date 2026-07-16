"""`/v1/models` agent-model CRUD routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, Query

from agent_server.app_deps import AppDeps
from agent_server.models import (
    AgentModel,
    AgentModelList,
    CreateAgentModelRequest,
    UpdateAgentModelRequest,
)


def register_model_routes(app: FastAPI, deps: AppDeps) -> None:
    models_service = deps.models_service

    @app.get("/v1/models", response_model=AgentModelList)
    async def list_models(
        enabled_only: bool = Query(default=False),
        discover: bool = Query(default=True),
    ) -> AgentModelList:
        return await asyncio.to_thread(
            models_service.list_models,
            enabled_only=enabled_only,
            discover=discover,
        )

    @app.post("/v1/models", response_model=AgentModel, status_code=201)
    async def create_custom_model(payload: CreateAgentModelRequest) -> AgentModel:
        try:
            return await asyncio.to_thread(models_service.create_custom_model, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/v1/models/{model_id:path}", response_model=AgentModel)
    async def update_model(
        model_id: str,
        payload: UpdateAgentModelRequest,
    ) -> AgentModel:
        try:
            return await asyncio.to_thread(models_service.update_model, model_id, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/v1/models/{model_id:path}")
    async def delete_custom_model(model_id: str) -> dict[str, bool]:
        removed = await asyncio.to_thread(models_service.delete_custom_model, model_id)
        if not removed:
            raise HTTPException(
                status_code=404,
                detail=f"Custom model '{model_id}' was not found.",
            )
        return {"ok": True}
