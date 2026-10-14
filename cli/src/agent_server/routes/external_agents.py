"""Claude Code / Codex / OpenCode / fx interop: list, import, launch, hand off."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import Field

from agent_server import external_agents_service as svc
from agent_server.app_deps import AppDeps
from agent_server.models import AgentSession
from agent_server.models.base import ApiModel


class ExternalAgentInfo(ApiModel):
    kind: str
    label: str
    installed: bool
    path: str | None = None


class ExternalAgentsResponse(ApiModel):
    agents: list[ExternalAgentInfo]
    sessions: list[dict[str, Any]] = Field(default_factory=list)


class ImportExternalRequest(ApiModel):
    kind: str
    session_id: str
    project_id: str | None = None
    workspace_path: str | None = None


class LaunchExternalRequest(ApiModel):
    kind: str
    workspace_path: str | None = None
    project_id: str | None = None
    origin_chat_id: str | None = None
    prompt: str | None = None
    resume_id: str | None = None
    title: str | None = None


class HandoffRequest(ApiModel):
    kind: str
    # Also open a terminal running the CLI on the handoff file.
    launch: bool = True
    # Claude Code / Codex: write their own session file and `resume` it
    # (experimental; falls back to the handoff prompt if that fails).
    native: bool = False
    project_id: str | None = None


def register_external_agent_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store
    service = deps.service
    pty_manager = deps.pty_manager

    def _bad(exc: Exception) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))

    @app.get("/v1/external-agents", response_model=ExternalAgentsResponse)
    async def list_external_agents(
        cwd: str | None = None,
        kind: str | None = None,
        limit: int = 30,
        sessions: bool = True,
    ) -> ExternalAgentsResponse:
        agents = await asyncio.to_thread(svc.list_installed)
        rows: list[dict[str, Any]] = []
        if sessions:
            try:
                rows = await asyncio.to_thread(svc.list_external, kind, cwd, max(1, min(100, limit)))
            except svc.ExternalAgentError as exc:
                raise _bad(exc) from exc
        return ExternalAgentsResponse(agents=[ExternalAgentInfo(**a) for a in agents], sessions=rows)

    @app.post("/v1/external-agents/import", response_model=AgentSession, status_code=201)
    async def import_external_session(payload: ImportExternalRequest) -> AgentSession:
        try:
            return await asyncio.to_thread(
                svc.import_session,
                service=service,
                store=store,
                kind=payload.kind,
                session_id=payload.session_id,
                project_id=payload.project_id,
                workspace_path=payload.workspace_path,
            )
        except svc.ExternalAgentError as exc:
            raise _bad(exc) from exc
        except ValueError as exc:
            raise _bad(exc) from exc

    @app.post("/v1/external-agents/launch")
    async def launch_external_agent(payload: LaunchExternalRequest) -> dict[str, Any]:
        workspace = payload.workspace_path
        if not workspace and payload.origin_chat_id:
            chat = await asyncio.to_thread(store.get_session, payload.origin_chat_id)
            workspace = chat.workspace_path if chat else None
        if not workspace and payload.project_id:
            project = await asyncio.to_thread(store.get_project, payload.project_id)
            workspace = getattr(project, "folder_path", None) if project else None
        try:
            return await svc.launch_terminal(
                store=store,
                pty_manager=pty_manager,
                kind=payload.kind,
                workspace_path=workspace,
                project_id=payload.project_id,
                origin_chat_id=payload.origin_chat_id,
                prompt=payload.prompt,
                resume_id=payload.resume_id,
                title=payload.title,
            )
        except svc.ExternalAgentError as exc:
            raise _bad(exc) from exc

    @app.post("/v1/sessions/{session_id}/handoff")
    async def handoff_session(session_id: str, payload: HandoffRequest) -> dict[str, Any]:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        try:
            result = await asyncio.to_thread(
                svc.export_handoff,
                service=service,
                store=store,
                session_id=session_id,
                kind=payload.kind,
                native=payload.native,
            )
        except svc.ExternalAgentError as exc:
            raise _bad(exc) from exc
        if payload.launch:
            resume_id = result.get("resumeId") if result.get("native") else None
            try:
                launched = await svc.launch_terminal(
                    store=store,
                    pty_manager=pty_manager,
                    kind=payload.kind,
                    workspace_path=result["workspacePath"],
                    project_id=payload.project_id,
                    origin_chat_id=session_id,
                    prompt=None if resume_id else result["prompt"],
                    resume_id=resume_id,
                )
            except svc.ExternalAgentError as exc:
                raise _bad(exc) from exc
            result.update(launched)
        return result
