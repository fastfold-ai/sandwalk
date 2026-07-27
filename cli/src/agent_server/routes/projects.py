"""`/v1/projects/*` routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.models import (
    AgentProject,
    CreateProjectRequest,
    DeleteProjectResponse,
    ProjectList,
    UpdateProjectRequest,
)


def register_project_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get("/v1/projects", response_model=ProjectList)
    async def list_projects() -> ProjectList:
        return ProjectList(data=await asyncio.to_thread(store.list_projects))

    @app.post("/v1/projects", response_model=AgentProject, status_code=201)
    async def create_project(payload: CreateProjectRequest) -> AgentProject:
        try:
            return await asyncio.to_thread(
                store.create_project,
                name=payload.name,
                description=payload.description,
                agent_context=payload.agent_context,
                folder_path=payload.folder_path,
                icon=payload.icon,
                color=payload.color,
                pinned=payload.pinned,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/projects/{project_id}", response_model=AgentProject)
    async def get_project(project_id: str) -> AgentProject:
        project = await asyncio.to_thread(store.get_project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return project

    @app.patch("/v1/projects/{project_id}", response_model=AgentProject)
    async def update_project(
        project_id: str,
        payload: UpdateProjectRequest,
    ) -> AgentProject:
        try:
            project = await asyncio.to_thread(
                store.update_project,
                project_id,
                name=payload.name,
                description=payload.description,
                update_description=payload.description is not None
                or payload.clear_description,
                agent_context=payload.agent_context,
                update_agent_context=payload.agent_context is not None
                or payload.clear_agent_context,
                folder_path=payload.folder_path,
                update_folder_path=payload.folder_path is not None
                or payload.clear_folder_path,
                icon=payload.icon,
                color=payload.color,
                pinned=payload.pinned,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return project

    @app.delete("/v1/projects/{project_id}", response_model=DeleteProjectResponse)
    async def delete_project(project_id: str) -> DeleteProjectResponse:
        deleted = await asyncio.to_thread(store.delete_project, project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found.")
        return DeleteProjectResponse(deleted=True)
