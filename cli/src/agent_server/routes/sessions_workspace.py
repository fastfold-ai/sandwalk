"""Session workspace file list/read/write/download routes."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse

from agent_server.app_deps import AppDeps
from agent_server.models import WorkspaceFileContent, WorkspaceFileList, WriteWorkspaceFileRequest
from agent_server.workspace import WorkspaceConflictError


def register_workspace_routes(app: FastAPI, deps: AppDeps) -> None:
    @app.get(
        "/v1/sessions/{session_id}/files",
        response_model=WorkspaceFileList,
    )
    async def list_workspace_files(
        session_id: str,
        path: str = Query(default=""),
        recursive: bool = Query(default=True),
    ) -> WorkspaceFileList:
        workspace = deps.session_workspace(session_id)
        try:
            data = await asyncio.to_thread(workspace.list, path, recursive=recursive)
            return WorkspaceFileList(data=data)
        except Exception as exc:
            raise deps.workspace_http_error(exc) from exc

    @app.get(
        "/v1/sessions/{session_id}/files/content",
        response_model=WorkspaceFileContent,
    )
    async def read_workspace_file(
        session_id: str,
        path: str = Query(min_length=1),
    ) -> WorkspaceFileContent:
        workspace = deps.session_workspace(session_id)
        try:
            return await asyncio.to_thread(workspace.read, path)
        except Exception as exc:
            raise deps.workspace_http_error(exc) from exc

    @app.put(
        "/v1/sessions/{session_id}/files/content",
        response_model=WorkspaceFileContent,
    )
    async def write_workspace_file(
        session_id: str,
        payload: WriteWorkspaceFileRequest,
    ):
        workspace = deps.session_workspace(session_id)
        try:
            content = await asyncio.to_thread(
                workspace.write,
                payload.path,
                content=payload.content,
                encoding=payload.encoding,
                base_version=payload.base_version,
            )
        except WorkspaceConflictError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "detail": str(exc),
                    "current": exc.current.model_dump(mode="json", by_alias=True),
                },
            )
        except Exception as exc:
            raise deps.workspace_http_error(exc) from exc
        try:
            from agent.sandbox_backend import push_paths_for_session

            await asyncio.to_thread(
                push_paths_for_session,
                session_id,
                workspace.root,
                [payload.path],
            )
        except Exception as sync_exc:  # noqa: BLE001
            logging.getLogger("agent_server").warning(
                "Modal push after write failed: %s", sync_exc
            )
        return content

    @app.get("/v1/sessions/{session_id}/files/download")
    async def download_workspace_file(
        session_id: str,
        path: str = Query(min_length=1),
    ) -> FileResponse:
        workspace = deps.session_workspace(session_id)
        try:
            file_path = workspace.resolve(path, must_exist=True)
            if not file_path.is_file():
                raise IsADirectoryError(path)
            return FileResponse(file_path, filename=file_path.name)
        except Exception as exc:
            raise deps.workspace_http_error(exc) from exc
