"""`/v1/specialists/*` routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.models import (
    CreateSpecialistRequest,
    DeleteSpecialistResponse,
    Specialist,
    SpecialistList,
    UpdateSpecialistRequest,
)


def register_specialist_routes(app: FastAPI, deps: AppDeps) -> None:
    specialists_service = deps.specialists_service

    @app.get("/v1/specialists", response_model=SpecialistList)
    async def list_specialists() -> SpecialistList:
        return SpecialistList(data=await asyncio.to_thread(specialists_service.list))

    @app.post("/v1/specialists", response_model=Specialist, status_code=201)
    async def create_specialist(payload: CreateSpecialistRequest) -> Specialist:
        try:
            return await asyncio.to_thread(
                specialists_service.create,
                name=payload.name,
                slug=payload.slug,
                description=payload.description,
                instructions=payload.instructions,
                color=payload.color,
                icon=payload.icon,
                skill_names=payload.skill_names,
                tool_names=payload.tool_names,
                mcp_server_ids=payload.mcp_server_ids,
                mcp_catalog_ids=payload.mcp_catalog_ids,
                enabled=payload.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/specialists/{specialist_id}", response_model=Specialist)
    async def get_specialist(specialist_id: str) -> Specialist:
        specialist = await asyncio.to_thread(specialists_service.get, specialist_id)
        if specialist is None:
            raise HTTPException(status_code=404, detail="Specialist not found.")
        return specialist

    @app.patch("/v1/specialists/{specialist_id}", response_model=Specialist)
    async def update_specialist(
        specialist_id: str,
        payload: UpdateSpecialistRequest,
    ) -> Specialist:
        try:
            specialist = await asyncio.to_thread(
                specialists_service.update,
                specialist_id,
                name=payload.name,
                slug=payload.slug,
                description=payload.description,
                update_description=payload.description is not None
                or payload.clear_description,
                instructions=payload.instructions,
                update_instructions=payload.instructions is not None
                or payload.clear_instructions,
                color=payload.color,
                icon=payload.icon,
                skill_names=payload.skill_names,
                tool_names=payload.tool_names,
                mcp_server_ids=payload.mcp_server_ids,
                mcp_catalog_ids=payload.mcp_catalog_ids,
                enabled=payload.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if specialist is None:
            raise HTTPException(status_code=404, detail="Specialist not found.")
        return specialist

    @app.delete("/v1/specialists/{specialist_id}", response_model=DeleteSpecialistResponse)
    async def delete_specialist(specialist_id: str) -> DeleteSpecialistResponse:
        deleted = await asyncio.to_thread(specialists_service.delete, specialist_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Specialist not found.")
        return DeleteSpecialistResponse(deleted=True)
