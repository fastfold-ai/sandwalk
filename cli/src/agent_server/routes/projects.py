"""`/v1/projects/*` routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, Query

from agent_server.app_deps import AppDeps
from agent_server.models import (
    AgentProject,
    CreateProjectRequest,
    DeleteProjectFolderFileResponse,
    DeleteProjectResponse,
    ProjectFolderFile,
    ProjectFolderListing,
    ProjectList,
    RenameProjectFolderFileRequest,
    UpdateProjectRequest,
    UseLibraryInChatResponse,
    UseProjectFolderInChatRequest,
    WorkspaceFileContent,
)
from agent_server.project_folder_listing import (
    delete_project_folder_file,
    list_project_folder_files,
    read_project_folder_file,
    rename_project_folder_file,
    use_project_folder_in_chat,
)


def register_project_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store
    service = deps.service

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
                home_layout=payload.home_layout,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/projects/{project_id}", response_model=AgentProject)
    async def get_project(project_id: str) -> AgentProject:
        project = await asyncio.to_thread(store.get_project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return project

    @app.get(
        "/v1/projects/{project_id}/folder-files",
        response_model=ProjectFolderListing,
    )
    async def get_project_folder_files(project_id: str) -> ProjectFolderListing:
        """List files in the linked project folder (filesystem bridge, not Library)."""
        project = await asyncio.to_thread(store.get_project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        if not project.folder_path:
            raise HTTPException(
                status_code=404, detail="Project has no linked folder."
            )
        try:
            return await asyncio.to_thread(
                list_project_folder_files, project.folder_path
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/v1/projects/{project_id}/folder-files/content",
        response_model=WorkspaceFileContent,
    )
    async def get_project_folder_file_content(
        project_id: str,
        path: str = Query(..., min_length=1),
    ) -> WorkspaceFileContent:
        """Read a file under the linked project folder for preview."""
        project = await asyncio.to_thread(store.get_project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        if not project.folder_path:
            raise HTTPException(
                status_code=404, detail="Project has no linked folder."
            )
        try:
            return await asyncio.to_thread(
                read_project_folder_file, project.folder_path, path
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="File not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch(
        "/v1/projects/{project_id}/folder-files",
        response_model=ProjectFolderFile,
    )
    async def rename_project_folder_file_route(
        project_id: str,
        payload: RenameProjectFolderFileRequest,
    ) -> ProjectFolderFile:
        """Rename a file in the linked project folder (basename only)."""
        project = await asyncio.to_thread(store.get_project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        if not project.folder_path:
            raise HTTPException(
                status_code=404, detail="Project has no linked folder."
            )
        try:
            return await asyncio.to_thread(
                rename_project_folder_file,
                project.folder_path,
                payload.path,
                payload.name,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="File not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete(
        "/v1/projects/{project_id}/folder-files",
        response_model=DeleteProjectFolderFileResponse,
    )
    async def delete_project_folder_file_route(
        project_id: str,
        path: str = Query(..., min_length=1),
    ) -> DeleteProjectFolderFileResponse:
        """Delete a file from the linked project folder (real filesystem delete)."""
        project = await asyncio.to_thread(store.get_project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        if not project.folder_path:
            raise HTTPException(
                status_code=404, detail="Project has no linked folder."
            )
        try:
            await asyncio.to_thread(
                delete_project_folder_file, project.folder_path, path
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="File not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return DeleteProjectFolderFileResponse(deleted=True)

    @app.post(
        "/v1/projects/{project_id}/folder-files/use-in-chat",
        response_model=UseLibraryInChatResponse,
        status_code=201,
    )
    async def use_project_folder_in_chat_route(
        project_id: str,
        payload: UseProjectFolderInChatRequest,
    ) -> UseLibraryInChatResponse:
        """Open a new chat with project-folder files attached via ``project/...``."""
        project = await asyncio.to_thread(store.get_project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        if not project.folder_path:
            raise HTTPException(
                status_code=404, detail="Project has no linked folder."
            )
        try:
            return await asyncio.to_thread(
                use_project_folder_in_chat,
                agent_service=service,
                project_id=project_id,
                paths=payload.paths,
                folder_path=project.folder_path,
                title=payload.title,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="File not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
                home_layout=payload.home_layout,
                update_home_layout=payload.home_layout is not None
                or payload.clear_home_layout,
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
