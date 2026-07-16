"""Shared services/helpers wired into every agent_server route module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException

from agent_server.account_service import AccountService
from agent_server.auth_settings import load_settings, resolve_effective_api_key
from agent_server.datasets_service import DatasetsService
from agent_server.integrations_service import IntegrationsService
from agent_server.mcp_service import McpService
from agent_server.models_service import ModelsService
from agent_server.pty_manager import PtyManager
from agent_server.sandbox_settings_service import SandboxSettingsService
from agent_server.service import AgentService
from agent_server.settings_service import SettingsService
from agent_server.skills_service import SkillsService
from agent_server.specialists_service import SpecialistsService
from agent_server.store import AgentStore
from agent_server.tools_service import ToolsService
from agent_server.workspace import WorkspacePathError, WorkspaceService


@dataclass
class AppDeps:
    """Services and cross-cutting helpers shared by route registration functions."""

    app: FastAPI
    store: AgentStore
    service: AgentService
    skills_service: SkillsService
    specialists_service: SpecialistsService
    integrations_service: IntegrationsService
    settings_service: SettingsService
    sandbox_settings_service: SandboxSettingsService
    account_service: AccountService
    models_service: ModelsService
    datasets_service: DatasetsService
    tools_service: ToolsService
    pty_manager: PtyManager
    mcp_service: McpService
    backend_id: str
    cli_api_key: str | None

    def session_workspace(self, session_id: str) -> WorkspaceService:
        session = self.store.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        try:
            session = self.service.ensure_workspace(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        if not session.workspace_path:
            raise HTTPException(status_code=409, detail="Session has no workspace.")
        try:
            return WorkspaceService(Path(session.workspace_path))
        except WorkspacePathError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    def workspace_http_error(self, exc: Exception) -> HTTPException:
        if isinstance(exc, FileNotFoundError):
            return HTTPException(status_code=404, detail="Workspace path not found.")
        if isinstance(exc, FileExistsError):
            return HTTPException(status_code=409, detail="Workspace target already exists.")
        if isinstance(exc, (IsADirectoryError, NotADirectoryError, WorkspacePathError)):
            return HTTPException(status_code=400, detail=str(exc))
        return HTTPException(status_code=500, detail="Workspace operation failed.")

    def reload_auth_state(self) -> None:
        current = load_settings()
        self.app.state.auth_settings = current
        override = (self.cli_api_key or "").strip() or None
        key = resolve_effective_api_key(cli_api_key=override, settings=current)
        enforce = bool(override) or bool(current.auth_enabled and key)
        self.app.state.runtime_api_key = key if enforce else None

    def current_api_key(self) -> str | None:
        return getattr(self.app.state, "runtime_api_key", None)

    def current_secret(self) -> str:
        settings = getattr(self.app.state, "auth_settings", None) or load_settings()
        return settings.secret_key or ""
