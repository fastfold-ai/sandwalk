"""`/v1/library/*` routes."""

from __future__ import annotations

import asyncio
import base64
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from agent_server.app_deps import AppDeps
from agent_server.models.library import (
    DeleteLibraryItemResponse,
    LibraryFileContent,
    LibraryItem,
    LibraryItemList,
    LibrarySyncResponse,
    UpdateLibraryItemRequest,
    UseLibraryInChatRequest,
    UseLibraryInChatResponse,
    WriteLibraryContentRequest,
)

LibraryKindFilter = Literal["image", "document", "structure", "code", "other"]


def register_library_routes(app: FastAPI, deps: AppDeps) -> None:
    library = deps.library_service

    @app.get("/v1/library", response_model=LibraryItemList)
    async def list_library(
        kind: LibraryKindFilter | None = Query(default=None),
        q: str | None = Query(default=None),
        projectId: str | None = Query(default=None),
        page: int = Query(default=0, ge=0),
        per_page: int = Query(default=48, ge=1, le=500),
    ) -> LibraryItemList:
        return await asyncio.to_thread(
            library.list_items,
            kind=kind,
            query=q,
            project_id=projectId,
            page=page,
            per_page=per_page,
        )

    @app.post("/v1/library/sync", response_model=LibrarySyncResponse)
    async def sync_library_from_workspaces() -> LibrarySyncResponse:
        """Re-scan session workspaces (uploads/outputs/artifacts) into Library."""
        return await asyncio.to_thread(library.sync_from_workspaces)

    @app.post("/v1/library/upload", response_model=LibraryItem, status_code=201)
    async def upload_library_file(
        file: UploadFile = File(...),
    ) -> LibraryItem:
        data = await file.read()
        return await asyncio.to_thread(
            library.ingest_bytes,
            data,
            filename=file.filename or "upload.bin",
            mime=file.content_type,
        )

    @app.post("/v1/library/use-in-chat", response_model=UseLibraryInChatResponse)
    async def use_library_in_chat(
        payload: UseLibraryInChatRequest,
    ) -> UseLibraryInChatResponse:
        try:
            return await asyncio.to_thread(
                library.use_in_chat,
                payload.item_ids,
                project_id=payload.project_id,
                title=payload.title,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=f"Library item not found: {exc.args[0]}",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/library/{item_id}", response_model=LibraryItem)
    async def get_library_item(item_id: str) -> LibraryItem:
        item = await asyncio.to_thread(library.get_item, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Library item not found.")
        return item

    @app.patch("/v1/library/{item_id}", response_model=LibraryItem)
    async def update_library_item(
        item_id: str,
        payload: UpdateLibraryItemRequest,
    ) -> LibraryItem:
        try:
            item = await asyncio.to_thread(
                library.rename,
                item_id,
                payload.display_name,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if item is None:
            raise HTTPException(status_code=404, detail="Library item not found.")
        return item

    @app.delete("/v1/library/{item_id}", response_model=DeleteLibraryItemResponse)
    async def delete_library_item(item_id: str) -> DeleteLibraryItemResponse:
        deleted = await asyncio.to_thread(library.delete, item_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Library item not found.")
        return DeleteLibraryItemResponse(deleted=True)

    @app.get("/v1/library/{item_id}/content")
    async def get_library_content(item_id: str) -> FileResponse:
        item = await asyncio.to_thread(library.get_item, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Library item not found.")
        path = await asyncio.to_thread(library.content_path, item_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Library blob not found.")
        media = item.mime or "application/octet-stream"
        return FileResponse(
            path,
            media_type=media,
            filename=item.display_name or item.original_name,
        )

    @app.get("/v1/library/{item_id}/file", response_model=LibraryFileContent)
    async def get_library_file(item_id: str) -> LibraryFileContent:
        content = await asyncio.to_thread(library.read_file_content, item_id)
        if content is None:
            raise HTTPException(status_code=404, detail="Library item not found.")
        return content

    @app.put("/v1/library/{item_id}/content", response_model=LibraryFileContent)
    async def write_library_content(
        item_id: str,
        payload: WriteLibraryContentRequest,
    ) -> LibraryFileContent:
        try:
            if payload.encoding == "base64":
                data = base64.b64decode(payload.content, validate=True)
            else:
                data = payload.content.encode("utf-8")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Invalid file content.") from exc
        try:
            await asyncio.to_thread(library.write_content, item_id, data)
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail="Library item not found.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        content = await asyncio.to_thread(library.read_file_content, item_id)
        if content is None:
            raise HTTPException(status_code=404, detail="Library item not found.")
        return content
