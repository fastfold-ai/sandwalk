"""Session workspace upload/folder/move/delete routes."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile

from agent_server.app_deps import AppDeps
from agent_server.models import (
    CreateWorkspaceFolderRequest,
    MoveWorkspaceFileRequest,
    WorkspaceFileContent,
    WorkspaceMutationResponse,
)
from agent_server.workspace import MAX_FILE_SIZE


def register_workspace_mutate_routes(app: FastAPI, deps: AppDeps) -> None:
    @app.post(
        "/v1/sessions/{session_id}/files/upload",
        response_model=WorkspaceFileContent,
    )
    async def upload_workspace_file(
        session_id: str,
        file: UploadFile = File(...),
        relative_dir: str = Form(default="uploads"),
    ) -> WorkspaceFileContent:
        workspace = deps.session_workspace(session_id)
        data = await file.read(MAX_FILE_SIZE + 1)
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds the 40MB limit.")
        relative_path = str(Path(relative_dir) / (file.filename or "upload.bin"))
        try:
            content = await asyncio.to_thread(workspace.upload, relative_path, data)
        except Exception as exc:
            raise deps.workspace_http_error(exc) from exc
        try:
            from agent.sandbox_backend import push_paths_for_session

            await asyncio.to_thread(
                push_paths_for_session,
                session_id,
                workspace.root,
                [relative_path],
            )
        except Exception as sync_exc:  # noqa: BLE001
            # Upload already succeeded locally; Modal push is best-effort.
            logging.getLogger("agent_server").warning(
                "Modal push after upload failed: %s", sync_exc
            )
        return content

    @app.post(
        "/v1/sessions/{session_id}/files/folders",
        response_model=WorkspaceMutationResponse,
    )
    async def create_workspace_folder(
        session_id: str,
        payload: CreateWorkspaceFolderRequest,
    ) -> WorkspaceMutationResponse:
        workspace = deps.session_workspace(session_id)
        try:
            path = await asyncio.to_thread(workspace.create_folder, payload.path)
            return WorkspaceMutationResponse(path=path)
        except Exception as exc:
            raise deps.workspace_http_error(exc) from exc

    @app.post(
        "/v1/sessions/{session_id}/files/move",
        response_model=WorkspaceMutationResponse,
    )
    async def move_workspace_file(
        session_id: str,
        payload: MoveWorkspaceFileRequest,
    ) -> WorkspaceMutationResponse:
        workspace = deps.session_workspace(session_id)
        try:
            path = await asyncio.to_thread(
                workspace.move,
                payload.source_path,
                payload.target_path,
            )
            return WorkspaceMutationResponse(path=path)
        except Exception as exc:
            raise deps.workspace_http_error(exc) from exc

    @app.delete(
        "/v1/sessions/{session_id}/files",
        response_model=WorkspaceMutationResponse,
    )
    async def delete_workspace_file(
        session_id: str,
        path: str = Query(min_length=1),
        recursive: bool = Query(default=False),
    ) -> WorkspaceMutationResponse:
        workspace = deps.session_workspace(session_id)
        try:
            await asyncio.to_thread(workspace.delete, path, recursive=recursive)
            return WorkspaceMutationResponse(path=path)
        except Exception as exc:
            raise deps.workspace_http_error(exc) from exc
