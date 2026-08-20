"""Terminal-as-first-class-item CRUD routes (FAS-107).

Peer of ``/v1/sessions`` (chats). The live PTY IO stays at
``/v1/sessions/{session_id}/pty/*`` for now — those routes will be
refactored to use these persisted rows in Fase 7 (PTY persistence).
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.models import (
    CreateTerminalRequest,
    TerminalSession,
    TerminalSessionList,
    UpdateTerminalRequest,
)


def register_terminal_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get("/v1/terminals", response_model=TerminalSessionList)
    async def list_terminals(project_id: str | None = None) -> TerminalSessionList:
        rows = await asyncio.to_thread(
            store.list_terminals, project_id=project_id
        )
        return TerminalSessionList(data=rows)

    @app.get("/v1/terminals/{terminal_id}", response_model=TerminalSession)
    async def get_terminal(terminal_id: str) -> TerminalSession:
        row = await asyncio.to_thread(store.get_terminal, terminal_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Terminal not found.")
        return row

    @app.post("/v1/terminals", response_model=TerminalSession, status_code=201)
    async def create_terminal(payload: CreateTerminalRequest) -> TerminalSession:
        return await asyncio.to_thread(
            store.create_terminal,
            title=payload.title,
            project_id=payload.project_id,
            workspace_path=payload.workspace_path,
            shell=payload.shell,
            origin_chat_id=payload.origin_chat_id,
            slot_key=payload.slot_key,
        )

    @app.patch("/v1/terminals/{terminal_id}", response_model=TerminalSession)
    async def update_terminal(
        terminal_id: str, payload: UpdateTerminalRequest
    ) -> TerminalSession:
        updated = await asyncio.to_thread(
            store.update_terminal,
            terminal_id,
            title=payload.title,
            project_id=payload.project_id,
            organize_label=payload.organize_label,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Terminal not found.")
        return updated

    @app.delete("/v1/terminals/{terminal_id}", status_code=204)
    async def delete_terminal(terminal_id: str) -> None:
        deleted = await asyncio.to_thread(store.delete_terminal, terminal_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Terminal not found.")
