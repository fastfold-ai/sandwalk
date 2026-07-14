"""Per-session sandbox status and lifecycle controls."""

from __future__ import annotations

from pathlib import Path

from agent.config import Config
from agent.sandbox_backend import (
    get_active_handle,
    resolve_deepagents_backend,
    sandbox_backend_from_config,
    unregister_handle,
)
from agent_server.models import SessionSandboxStatus
from agent_server.sandbox_events import sandbox_event_bus
from agent_server.sandbox_settings_service import SandboxSettingsService
from agent_server.store import AgentStore


def _effective_backend(session_backend: str | None, _global_backend: str | None = None) -> str:
    """Resolve the sandbox used for a chat.

    Chats default to Built-in. Modal is used only when the session explicitly
    selects it (composer toggle). Global ``sandbox.backend`` is not inherited.
    """
    if session_backend in {"builtin", "modal"}:
        return session_backend
    return "builtin"


class SessionSandboxService:
    def __init__(self, store: AgentStore) -> None:
        self.store = store

    def status(self, session_id: str) -> SessionSandboxStatus:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        settings = SandboxSettingsService.get()
        global_backend = (
            settings.backend if settings.backend in {"builtin", "modal"} else "builtin"
        )
        session_backend = session.sandbox_backend
        backend = _effective_backend(session_backend, global_backend)
        handle = get_active_handle(session_id)
        status = "ready"
        detail: str | None = None
        provider_name = None
        if backend == "modal":
            if not settings.modal_configured:
                status = "unavailable"
                detail = "Modal tokens are not configured."
            elif handle is not None and handle.kind == "modal":
                status = "running"
                provider_name = handle.provider_sandbox_name
            else:
                status = "stopped"
                detail = "Modal sandbox is not running for this chat."
        elif handle is not None and handle.kind == "builtin":
            status = "ready"
        return SessionSandboxStatus(
            session_id=session_id,
            backend=backend,  # type: ignore[arg-type]
            session_backend=session_backend,  # type: ignore[arg-type]
            global_backend=global_backend,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            provider_sandbox_name=provider_name,
            modal_configured=settings.modal_configured,
            compute_type=settings.compute_type,
            gpu_class=settings.gpu_class,
            cpu_cores=settings.cpu_cores,
            ram_gb=settings.ram_gb,
            cpu_image=settings.cpu_image,
            detail=detail,
        )

    def _publish(self, status: SessionSandboxStatus) -> None:
        try:
            sandbox_event_bus.publish(status)
        except Exception:  # noqa: BLE001
            # Status push must never fail the control path.
            pass

    def _transitional(
        self,
        session_id: str,
        *,
        status: str,
        detail: str | None,
    ) -> SessionSandboxStatus:
        current = self.status(session_id)
        return current.model_copy(
            update={
                "status": status,
                "detail": detail,
            }
        )

    def start(self, session_id: str) -> SessionSandboxStatus:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        settings = SandboxSettingsService.get()
        global_backend = (
            settings.backend if settings.backend in {"builtin", "modal"} else "builtin"
        )
        backend = _effective_backend(session.sandbox_backend, global_backend)
        if backend != "modal":
            raise ValueError("Start is only available when Modal is enabled for this chat.")
        if not settings.modal_configured:
            raise ValueError(
                "Modal sandbox requires compute.modal_token_id and "
                "compute.modal_token_secret (Integrations → Modal)."
            )
        workspace = session.workspace_path
        if not workspace:
            raise ValueError("Session workspace is not ready yet.")
        root = Path(workspace).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        from agent.deepagents_runtime import skill_source_dirs

        self._publish(
            self._transitional(
                session_id,
                status="starting",
                detail="Starting Modal sandbox…",
            )
        )
        config = Config.load()
        # Create/reuse the Modal sandbox and return immediately. Full workspace
        # + skills sync runs in the background so the UI can leave "Starting".
        resolve_deepagents_backend(
            config,
            session_id=session_id,
            workspace_root=str(root),
            skill_source_dirs=skill_source_dirs(),
            backend_override="modal",
            sync_workspace=True,
            background_sync=True,
        )
        result = self.status(session_id)
        self._publish(result)
        return result

    def stop(self, session_id: str) -> SessionSandboxStatus:
        session = self.store.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        self._publish(
            self._transitional(
                session_id,
                status="stopping",
                detail="Stopping Modal sandbox…",
            )
        )
        handle = get_active_handle(session_id)
        if handle is not None:
            handle.terminate()
            unregister_handle(session_id)
        result = self.status(session_id)
        self._publish(result)
        return result

    def restart(self, session_id: str) -> SessionSandboxStatus:
        self.stop(session_id)
        return self.start(session_id)


def effective_session_sandbox_backend(
    session_backend: str | None,
    *,
    config: object | None = None,
) -> str:
    cfg = config or Config.load()
    global_backend = sandbox_backend_from_config(cfg)
    return _effective_backend(session_backend, global_backend)
