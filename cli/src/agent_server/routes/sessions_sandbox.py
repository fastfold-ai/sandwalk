"""Session sandbox status/start/stop/restart routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.models import SessionSandboxStatus


def register_session_sandbox_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store

    @app.get(
        "/v1/sessions/{session_id}/sandbox",
        response_model=SessionSandboxStatus,
    )
    async def get_session_sandbox(session_id: str) -> SessionSandboxStatus:
        from agent_server.session_sandbox_service import SessionSandboxService

        try:
            return await asyncio.to_thread(
                SessionSandboxService(store).status, session_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post(
        "/v1/sessions/{session_id}/sandbox/start",
        response_model=SessionSandboxStatus,
    )
    async def start_session_sandbox(session_id: str) -> SessionSandboxStatus:
        from agent_server.session_sandbox_service import SessionSandboxService

        try:
            return await asyncio.to_thread(
                SessionSandboxService(store).start, session_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/v1/sessions/{session_id}/sandbox/stop",
        response_model=SessionSandboxStatus,
    )
    async def stop_session_sandbox(session_id: str) -> SessionSandboxStatus:
        from agent_server.session_sandbox_service import SessionSandboxService

        try:
            return await asyncio.to_thread(
                SessionSandboxService(store).stop, session_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.post(
        "/v1/sessions/{session_id}/sandbox/restart",
        response_model=SessionSandboxStatus,
    )
    async def restart_session_sandbox(session_id: str) -> SessionSandboxStatus:
        from agent_server.session_sandbox_service import SessionSandboxService

        try:
            return await asyncio.to_thread(
                SessionSandboxService(store).restart, session_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
