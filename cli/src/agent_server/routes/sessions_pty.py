"""Session PTY (terminal) CRUD routes."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket

from agent_server.app_deps import AppDeps
from agent_server.auth_settings import SESSION_COOKIE, key_matches, request_is_authenticated
from agent_server.models import CreatePtyRequest, PtySessionInfo, PtySessionList, UpdatePtyRequest

# Terminals opened outside an agent chat (draft home) — cwd is the user home.
HOST_TERMINAL_SESSION_ID = "host"


def register_pty_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store
    service = deps.service
    pty_manager = deps.pty_manager

    async def _require_agent_session(session_id: str) -> None:
        if session_id == HOST_TERMINAL_SESSION_ID:
            return
        # FAS-107: terminal ids are first-class here — accept the id when it
        # matches a terminal_sessions row, so the picker's "New terminal"
        # can pipe the live PTY through the same /v1/sessions/{id}/pty
        # transport the frontend already uses. Chat ids still hit the chat
        # validation below.
        if session_id.startswith("term_"):
            term = await asyncio.to_thread(store.get_terminal, session_id)
            if term is None:
                raise HTTPException(status_code=404, detail="Terminal not found.")
            return
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")

    def _pty_cwd(session_id: str) -> str:
        if session_id == HOST_TERMINAL_SESSION_ID:
            return str(Path.home().expanduser().resolve())
        if session_id.startswith("term_"):
            term = store.get_terminal(session_id)
            if term is None:
                raise HTTPException(status_code=404, detail="Terminal not found.")
            return term.workspace_path or str(Path.home().expanduser().resolve())
        session = service.ensure_workspace(session_id)
        if not session.workspace_path:
            raise HTTPException(status_code=409, detail="Session has no workspace.")
        return session.workspace_path

    @app.get("/v1/sessions/{session_id}/pty", response_model=PtySessionList)
    async def list_pty_sessions(session_id: str) -> PtySessionList:
        await _require_agent_session(session_id)
        return PtySessionList(
            data=[
                PtySessionInfo(**info.to_dict())
                for info in pty_manager.list(session_id)
            ]
        )

    @app.post(
        "/v1/sessions/{session_id}/pty",
        response_model=PtySessionInfo,
        status_code=201,
    )
    async def create_pty_session(
        session_id: str,
        payload: CreatePtyRequest | None = None,
    ) -> PtySessionInfo:
        await _require_agent_session(session_id)
        body = payload or CreatePtyRequest()
        info = await pty_manager.create(
            session_id=session_id,
            cwd=_pty_cwd(session_id),
            title=body.title,
            cols=body.cols,
            rows=body.rows,
        )
        return PtySessionInfo(**info.to_dict())

    @app.put(
        "/v1/sessions/{session_id}/pty/{pty_id}",
        response_model=PtySessionInfo,
    )
    async def update_pty_session(
        session_id: str,
        pty_id: str,
        payload: UpdatePtyRequest,
    ) -> PtySessionInfo:
        info = pty_manager.get(session_id, pty_id)
        if info is None:
            raise HTTPException(status_code=404, detail="Terminal not found.")
        if payload.title is not None:
            updated = await pty_manager.update_title(session_id, pty_id, payload.title)
            if updated is None:
                raise HTTPException(status_code=404, detail="Terminal not found.")
            info = updated
        if payload.cols is not None and payload.rows is not None:
            updated = await pty_manager.resize(
                session_id,
                pty_id,
                cols=payload.cols,
                rows=payload.rows,
            )
            if updated is None:
                raise HTTPException(status_code=404, detail="Terminal not found.")
            info = updated
        return PtySessionInfo(**info.to_dict())

    @app.delete("/v1/sessions/{session_id}/pty/{pty_id}", status_code=204)
    async def delete_pty_session(session_id: str, pty_id: str) -> None:
        deleted = await pty_manager.remove(session_id, pty_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Terminal not found.")

    @app.websocket("/v1/sessions/{session_id}/pty/{pty_id}/connect")
    async def connect_pty_session(
        websocket: WebSocket,
        session_id: str,
        pty_id: str,
    ) -> None:
        if deps.current_api_key():
            authorization = websocket.headers.get("authorization", "")
            scheme, _, candidate = authorization.partition(" ")
            query_token = websocket.query_params.get("token", "")
            cookie_token = ""
            try:
                cookie_token = websocket.cookies.get(SESSION_COOKIE, "") or ""
            except Exception:
                cookie_token = ""
            key = deps.current_api_key() or ""
            valid = request_is_authenticated(
                headers={"authorization": authorization, "x-api-key": websocket.headers.get("x-api-key", "")},
                cookies={SESSION_COOKIE: cookie_token},
                api_key=key,
                secret_key=deps.current_secret(),
                query_token=query_token,
            ) or (
                scheme.lower() == "bearer"
                and bool(candidate)
                and key_matches(candidate, key)
            )
            if not valid:
                await websocket.close(code=4401)
                return
        if session_id != HOST_TERMINAL_SESSION_ID:
            if session_id.startswith("term_"):
                if await asyncio.to_thread(store.get_terminal, session_id) is None:
                    await websocket.close(code=4404)
                    return
            elif await asyncio.to_thread(store.get_session, session_id) is None:
                await websocket.close(code=4404)
                return
        if pty_manager.get(session_id, pty_id) is None:
            await websocket.close(code=4404)
            return
        await websocket.accept()
        await pty_manager.attach(session_id, pty_id, websocket)
