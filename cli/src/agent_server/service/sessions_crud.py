"""Session create/update/workspace-ensure mixin for AgentService."""

from __future__ import annotations

from pathlib import Path

from agent_server.models import AgentSession
from agent_server.service.fork_import import import_shared_fork_files


class _SessionCrudMixin:
    def ensure_workspace(self, session_id: str) -> AgentSession:
        """Ensure the session has a writable workspace directory on disk."""
        from agent_server import service
        from agent_server.project_folder import sync_project_folder_link

        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        workspace = service.resolve_session_workspace(session_id, store=self.store, persist=True)
        folder_path = None
        if session.project_id:
            project = self.store.get_project(session.project_id)
            if project is not None:
                folder_path = project.folder_path
        sync_project_folder_link(workspace, folder_path)
        import_shared_fork_files(session_id, workspace)
        updated = self.store.get_session(session_id)
        if updated is None:
            raise KeyError(session_id)
        return updated

    def create_session(
        self,
        *,
        title: str | None,
        workspace_path: str | None,
        project_id: str | None = None,
        specialist_id: str | None = None,
        sandbox_backend: str | None = None,
        source: str | None = None,
        source_label: str | None = None,
        client_surface: str | None = None,
    ) -> AgentSession:
        from agent_server import service

        normalized_workspace: str | None = None
        if workspace_path:
            workspace = Path(workspace_path).expanduser().resolve()
            if not workspace.is_dir():
                raise ValueError(f"Workspace directory does not exist: {workspace}")
            normalized_workspace = str(workspace)
        session = self.store.create_session(
            title=title,
            workspace_path=normalized_workspace,
            project_id=project_id,
            specialist_id=specialist_id,
            sandbox_backend=sandbox_backend,
            source=source,
            source_label=source_label,
            client_surface=client_surface,
        )
        if normalized_workspace is None:
            workspace = service.default_workspace_path(session.id)
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "uploads").mkdir(parents=True, exist_ok=True)
            (workspace / "outputs").mkdir(parents=True, exist_ok=True)
            session = self.store.set_workspace_path(session.id, str(workspace)) or session
        self.store.append_event(
            session_id=session.id,
            event_type="session.created",
            payload={"session": session.model_dump(mode="json", by_alias=True)},
        )
        return session

    def update_session(
        self,
        *,
        session_id: str,
        title: str | None,
        organize_label: str | None,
        update_organize_label: bool,
        project_id: str | None = None,
        update_project_id: bool = False,
        specialist_id: str | None = None,
        update_specialist_id: bool = False,
        sandbox_backend: str | None = None,
        update_sandbox_backend: bool = False,
    ) -> AgentSession:
        if update_sandbox_backend and sandbox_backend == "modal":
            from agent_server.sandbox_settings_service import SandboxSettingsService

            settings = SandboxSettingsService.get()
            if not settings.modal_configured:
                raise ValueError(
                    "Modal sandbox requires compute.modal_token_id and "
                    "compute.modal_token_secret (Integrations → Modal)."
                )
        session = self.store.update_session(
            session_id,
            title=title,
            organize_label=organize_label,
            update_organize_label=update_organize_label,
            project_id=project_id,
            update_project_id=update_project_id,
            specialist_id=specialist_id,
            update_specialist_id=update_specialist_id,
            sandbox_backend=sandbox_backend,
            update_sandbox_backend=update_sandbox_backend,
        )
        if session is None:
            raise KeyError(session_id)
        self.store.append_event(
            session_id=session.id,
            event_type="session.updated",
            payload={"session": session.model_dump(mode="json", by_alias=True)},
        )
        return session
