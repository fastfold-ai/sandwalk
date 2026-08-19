"""Capy singleton session route."""

from __future__ import annotations

from fastapi import FastAPI

from agent_server.app_deps import AppDeps
from agent_server.capy.scope import get_capy_scope, set_capy_scope
from agent_server.capy.session import get_or_create_capy_session, reset_capy_session
from agent_server.models import AgentSession
from agent_server.models.base import ApiModel


class CapyScope(ApiModel):
    project_id: str | None = None
    session_id: str | None = None


def register_capy_routes(app: FastAPI, deps: AppDeps) -> None:
    @app.get("/v1/capy/session", response_model=AgentSession)
    async def capy_session() -> AgentSession:
        return get_or_create_capy_session(deps.store, deps.service)

    @app.post("/v1/capy/session/reset", response_model=AgentSession)
    async def capy_session_reset() -> AgentSession:
        return reset_capy_session(deps.store, deps.service)

    @app.get("/v1/capy/scope", response_model=CapyScope)
    async def capy_scope() -> CapyScope:
        data = get_capy_scope()
        return CapyScope(project_id=data.get("project_id"), session_id=data.get("session_id"))

    @app.put("/v1/capy/scope", response_model=CapyScope)
    async def capy_scope_put(payload: CapyScope) -> CapyScope:
        data = set_capy_scope(
            project_id=payload.project_id,
            session_id=payload.session_id,
        )
        return CapyScope(project_id=data.get("project_id"), session_id=data.get("session_id"))
