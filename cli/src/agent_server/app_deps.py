"""Shared services/helpers wired into every agent_server route module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException

from agent_server.account_service import AccountService
from agent_server.auth_settings import load_settings, resolve_effective_api_key
from agent_server.connectors.service import ConnectorService
from agent_server.datasets_service import DatasetsService
from agent_server.integrations_service import IntegrationsService
from agent_server.library import LibraryService
from agent_server.mcp_service import McpService
from agent_server.models_service import ModelsService
from agent_server.pty_manager import PtyManager
from agent_server.sandbox_settings_service import SandboxSettingsService
from agent_server.service import AgentService
from agent_server.settings_service import SettingsService
from agent_server.sites_service import SitesService
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
    sites_service: SitesService
    sandbox_settings_service: SandboxSettingsService
    account_service: AccountService
    models_service: ModelsService
    datasets_service: DatasetsService
    tools_service: ToolsService
    pty_manager: PtyManager
    mcp_service: McpService
    library_service: LibraryService
    connector_service: ConnectorService
    backend_id: str
    cli_api_key: str | None
    bench_store: AgentStore | None = None
    bench_service: AgentService | None = None

    def worker_store(self) -> AgentStore:
        return self.bench_store or self.store

    def worker_service(self) -> AgentService:
        return self.bench_service or self.service

    def store_for_session(self, session_id: str) -> AgentStore:
        """Chat store, or the bench store when the session lives there.

        Bench cells are written to a separate database so their event flood
        does not stall chat. Opening one from its project still has to find
        the row, messages, and transcript.
        """
        if self.store.get_session(session_id) is not None:
            return self.store
        bench = self.bench_store
        if (
            bench is not None
            and bench is not self.store
            and bench.get_session(session_id) is not None
        ):
            return bench
        return self.store

    def list_visible_sessions(self, project_id: str | None):
        """Project scope includes that project's bench cells."""
        rows = self.store.list_sessions(project_id=project_id)
        bench = self.bench_store
        if not project_id or bench is None or bench is self.store:
            return rows
        seen = {session.id for session in rows}
        extra = [
            session
            for session in bench.list_sessions(project_id=project_id)
            if session.id not in seen
        ]
        if not extra:
            return rows
        merged = [*rows, *extra]
        merged.sort(key=lambda session: (session.updated_at, session.id), reverse=True)
        return merged

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

    def accepted_api_keys(self) -> list[str]:
        """Keys that authorize Bearer / x-api-key (runtime override + settings).

        Settings key is only accepted while auth is enabled — otherwise
        ``sandwalk auth disable`` would keep enforcing the stored key.
        """
        from agent_server.auth_settings import normalize_api_keys

        settings = getattr(self.app.state, "auth_settings", None) or load_settings()
        settings_key = settings.api_key if settings.auth_enabled else None
        return normalize_api_keys(self.current_api_key(), settings_key)

    def current_secret(self) -> str:
        settings = getattr(self.app.state, "auth_settings", None) or load_settings()
        return settings.secret_key or ""
