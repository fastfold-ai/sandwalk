"""Session PTY (terminal) CRUD routes."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel

from agent_server.app_deps import AppDeps
from agent_server.auth_settings import SESSION_COOKIE, key_matches, request_is_authenticated
from agent_server.models import CreatePtyRequest, PtySessionInfo, PtySessionList, UpdatePtyRequest
from agent_server.pty_manager.snapshot_store import (
    delete_snapshot,
    read_snapshot,
    write_snapshot,
)


class PtySnapshotResponse(BaseModel):
    """FAS-107 X4 Capa 2 · raw PTY output log (base64 wrapped for JSON).

    El campo `data` es base64 del stream crudo del PTY. El frontend lo
    decodifica a Uint8Array y hace `xterm.write(bytes)` DESPUÉS de
    resize a las dims actuales — xterm procesa cada byte con las dims
    correctas y aplica su reflow interno.
    """

    data: str | None

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
        # FAS-107 X4 Capa 2: al eliminar el terminal, borrar su snapshot
        # para que no quede huérfano en disco.
        delete_snapshot(session_id)

    @app.get(
        "/v1/sessions/{session_id}/snapshot",
        response_model=PtySnapshotResponse,
    )
    async def get_session_snapshot(session_id: str) -> PtySnapshotResponse:
        """Devuelve el raw byte log del PTY del session_id (base64).

        FAS-107 X4 Capa 2 · llamado por el frontend justo antes de
        conectar el WebSocket, cuando el terminal se remonta después de
        un Cmd+Q → reopen.

        Prioridad:
        1. Si hay un PTY vivo con `output_log` en memoria (raro tras
           reopen, pero posible en tab switches internos) → devolver
           ese log.
        2. Fallback al snapshot persistido en disco.
        """
        await _require_agent_session(session_id)
        # Buscar un PTY vivo con log en memoria.
        for info in pty_manager.list(session_id):
            session = pty_manager.get_session(session_id, info.id)
            if session and session.output_log:
                return PtySnapshotResponse(
                    data=base64.b64encode(bytes(session.output_log)).decode(
                        "ascii"
                    )
                )
        # Fallback a disco.
        persisted = read_snapshot(session_id)
        if persisted is None:
            return PtySnapshotResponse(data=None)
        return PtySnapshotResponse(
            data=base64.b64encode(persisted).decode("ascii")
        )

    @app.post(
        "/v1/sessions/{session_id}/snapshot/flush",
        status_code=204,
    )
    async def flush_session_snapshot(session_id: str) -> None:
        """Persiste el `output_log` actual del PTY vivo al disco.

        FAS-107 X4 Capa 2 · llamado por el frontend justo antes de
        Cmd+Q (via evento Tauri `sandwalk:force-save-snapshots`). Es
        best-effort: si no hay PTY vivo o no hay log, no-op.
        """
        await _require_agent_session(session_id)
        for info in pty_manager.list(session_id):
            session = pty_manager.get_session(session_id, info.id)
            if session and session.output_log:
                write_snapshot(session_id, bytes(session.output_log))
                return

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
