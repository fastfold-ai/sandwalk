"""Session CRUD, search, auto-title, and interrupt routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, Header, HTTPException, Query

from agent_server.app_deps import AppDeps
from agent_server.models import (
    AgentSession,
    AutoTitleSessionRequest,
    CompactSessionRequest,
    CompactSessionResponse,
    CreateSessionRequest,
    DeleteSessionResponse,
    InterruptRunResponse,
    SessionList,
    SessionRevision,
    SubmitApprovalsRequest,
    SubmitApprovalsResponse,
    UpdateSessionRequest,
)
from agent_server.service import SessionBusyError
from agent_server.usage_service.parse import resolve_client_surface


def register_session_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store
    service = deps.service

    @app.get("/v1/sessions", response_model=SessionList)
    async def list_sessions(
        project_id: str | None = Query(default=None, alias="projectId"),
    ) -> SessionList:
        return SessionList(
            data=await asyncio.to_thread(store.list_sessions, project_id=project_id)
        )

    @app.get("/v1/sessions/revision", response_model=SessionRevision)
    async def get_sessions_revision() -> SessionRevision:
        return SessionRevision(
            revision=await asyncio.to_thread(store.sessions_revision)
        )

    @app.get("/v1/sessions/search", response_model=SessionList)
    async def search_sessions(
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> SessionList:
        return SessionList(
            data=await asyncio.to_thread(store.search_sessions, q, limit=limit)
        )

    @app.post("/v1/sessions", response_model=AgentSession, status_code=201)
    async def create_session(
        payload: CreateSessionRequest,
        x_sandwalk_client: str | None = Header(default=None, alias="X-Sandwalk-Client"),
    ) -> AgentSession:
        surface = resolve_client_surface(
            body=payload.client_surface,
            header=x_sandwalk_client,
        )
        try:
            return await asyncio.to_thread(
                service.create_session,
                title=payload.title,
                workspace_path=payload.workspace_path,
                project_id=payload.project_id,
                specialist_id=payload.specialist_id,
                sandbox_backend=payload.sandbox_backend,
                client_surface=surface,
                provider=payload.provider,
                model=payload.model,
                openai_profile_id=payload.openai_profile_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/sessions/{session_id}", response_model=AgentSession)
    async def get_session(session_id: str) -> AgentSession:
        session = await asyncio.to_thread(store.get_session, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return session

    @app.patch("/v1/sessions/{session_id}", response_model=AgentSession)
    async def update_session(
        session_id: str,
        payload: UpdateSessionRequest,
    ) -> AgentSession:
        update_label = payload.organize_label is not None or payload.clear_organize_label
        update_project = payload.project_id is not None or payload.clear_project_id
        update_specialist = (
            payload.specialist_id is not None or payload.clear_specialist_id
        )
        update_sandbox = (
            payload.sandbox_backend is not None or payload.clear_sandbox_backend
        )
        update_llm = (
            payload.clear_llm
            or payload.provider is not None
            or payload.model is not None
            or payload.openai_profile_id is not None
        )
        try:
            return await asyncio.to_thread(
                service.update_session,
                session_id=session_id,
                title=payload.title,
                organize_label=payload.organize_label,
                update_organize_label=update_label,
                project_id=None if payload.clear_project_id else payload.project_id,
                update_project_id=update_project,
                specialist_id=None
                if payload.clear_specialist_id
                else payload.specialist_id,
                update_specialist_id=update_specialist,
                sandbox_backend=None
                if payload.clear_sandbox_backend
                else payload.sandbox_backend,
                update_sandbox_backend=update_sandbox,
                provider=None if payload.clear_llm else payload.provider,
                model=None if payload.clear_llm else payload.model,
                openai_profile_id=None
                if payload.clear_llm
                else payload.openai_profile_id,
                update_llm=update_llm,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/sessions/{session_id}/title/auto", response_model=AgentSession)
    async def auto_title_session(
        session_id: str,
        payload: AutoTitleSessionRequest | None = None,
    ) -> AgentSession:
        body = payload or AutoTitleSessionRequest()
        try:
            return await asyncio.to_thread(
                service.auto_title_session,
                session_id,
                force=body.force,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @app.delete("/v1/sessions/{session_id}", response_model=DeleteSessionResponse)
    async def delete_session(session_id: str) -> DeleteSessionResponse:
        if not await service.delete_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found.")
        return DeleteSessionResponse()

    @app.post(
        "/v1/sessions/{session_id}/interrupt",
        response_model=InterruptRunResponse,
    )
    async def interrupt_session(session_id: str) -> InterruptRunResponse:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return InterruptRunResponse(interrupted=service.interrupt(session_id))

    @app.post(
        "/v1/sessions/{session_id}/compact",
        response_model=CompactSessionResponse,
    )
    async def compact_session(
        session_id: str,
        payload: CompactSessionRequest | None = None,
    ) -> CompactSessionResponse:
        body = payload or CompactSessionRequest()
        try:
            return await asyncio.to_thread(
                service.compact_session,
                session_id,
                instructions=body.instructions,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except SessionBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/v1/sessions/{session_id}/approvals",
        response_model=SubmitApprovalsResponse,
    )
    async def submit_approvals(
        session_id: str,
        payload: SubmitApprovalsRequest,
    ) -> SubmitApprovalsResponse:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        decisions = [item.model_dump(exclude_none=True) for item in payload.decisions]
        try:
            result = await asyncio.to_thread(
                service.submit_approvals,
                session_id,
                decisions=decisions,
                interrupt_id=payload.interrupt_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        return SubmitApprovalsResponse(
            accepted=bool(result.get("accepted", True)),
            interrupt_id=result.get("interrupt_id"),
        )
