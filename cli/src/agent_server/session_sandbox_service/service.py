"""Per-session sandbox status and lifecycle controls."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agent.config import Config
from agent.sandbox_backend import (
    get_active_handle,
    resolve_deepagents_backend,
    unregister_handle,
)
from agent.sandbox_backend.activity import SandboxActivity
from agent.sandbox_backend.handle import (
    SandboxStop,
    clear_last_stop,
    get_last_stop,
    modal_sandbox_finished,
    record_sandbox_stop,
)
from agent_server.models import SessionSandboxStatus
from agent_server.sandbox_events import sandbox_event_bus
from agent_server.sandbox_settings_service import SandboxSettingsService
from agent_server.session_sandbox_service.backend import effective_backend
from agent_server.store import AgentStore


def _duration(seconds: int) -> str:
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    if seconds >= 60:
        return f"{round(seconds / 60)} min"
    return f"{seconds} s"


def _stop_detail(stop: SandboxStop) -> str:
    if stop.reason == "idle" and stop.idle_timeout_seconds:
        return (
            "Modal stopped this sandbox after "
            f"{_duration(stop.idle_timeout_seconds)} without activity."
        )
    if stop.reason == "time_limit" and stop.max_lifetime_seconds:
        return (
            "This sandbox reached its "
            f"{_duration(stop.max_lifetime_seconds)} time limit."
        )
    if stop.reason == "timeout":
        return "Modal stopped this sandbox on a timeout."
    return "This sandbox ended on its own."


def _utc(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)


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
        backend = effective_backend(session_backend, global_backend)
        handle = get_active_handle(session_id)
        status = "ready"
        detail: str | None = None
        provider_name = None
        lifecycle: dict[str, object] = {}
        if backend == "modal":
            if not settings.modal_configured:
                status = "unavailable"
                detail = "Modal tokens are not configured."
            elif handle is not None and handle.kind == "modal":
                # The handle only says this server started a sandbox. Modal
                # ends it on its own (idle timeout, time limit), so ask.
                if modal_sandbox_finished(handle) is True:
                    record_sandbox_stop(handle)
                    unregister_handle(session_id)
                    status = "stopped"
                else:
                    status = "running"
                    provider_name = handle.provider_sandbox_name
                    lifecycle = self._running_lifecycle(handle)
            else:
                status = "stopped"
            if status == "stopped":
                stop = get_last_stop(session_id)
                if stop is None:
                    detail = "Modal sandbox is not running for this chat."
                else:
                    detail = _stop_detail(stop)
                    lifecycle = {
                        "stopped_at": _utc(stop.stopped_at),
                        "stop_reason": stop.reason,
                        "idle_timeout_seconds": stop.idle_timeout_seconds,
                        "max_lifetime_seconds": stop.max_lifetime_seconds,
                    }
        elif handle is not None and handle.kind == "builtin":
            status = "ready"
        compute_type = str(settings.compute_type or "cpu").strip().lower() or "cpu"
        cpu_image = str(
            getattr(settings, "cpu_image", None) or "python:3.12-slim"
        )
        gpu_image = str(
            getattr(settings, "gpu_image", None)
            or "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"
        )
        base_image = gpu_image if compute_type == "gpu" else cpu_image
        return SessionSandboxStatus(
            session_id=session_id,
            backend=backend,  # type: ignore[arg-type]
            session_backend=session_backend,  # type: ignore[arg-type]
            global_backend=global_backend,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            provider_sandbox_name=provider_name,
            modal_configured=settings.modal_configured,
            compute_type=compute_type,
            gpu_class=settings.gpu_class,
            cpu_cores=settings.cpu_cores,
            ram_gb=settings.ram_gb,
            cpu_image=cpu_image,
            gpu_image=gpu_image,
            base_image=base_image,
            detail=detail,
            configured_idle_timeout_seconds=getattr(settings, "idle_ttl_seconds", None),
            configured_max_lifetime_seconds=getattr(
                settings, "max_lifetime_seconds", None
            ),
            **lifecycle,  # type: ignore[arg-type]
        )

    @staticmethod
    def _running_lifecycle(handle: object) -> dict[str, object]:
        """Uptime and the lifetime rules of a running Modal sandbox."""
        out: dict[str, object] = {}
        started = getattr(handle, "started_at", None)
        extras = getattr(handle, "extras", None)
        if isinstance(started, (int, float)):
            out["started_at"] = _utc(started)
        if not isinstance(extras, dict):
            return out
        idle = extras.get("idle_timeout_seconds")
        limit = extras.get("max_lifetime_seconds")
        if isinstance(idle, int) and idle > 0:
            out["idle_timeout_seconds"] = idle
        if isinstance(limit, int) and limit > 0:
            out["max_lifetime_seconds"] = limit
            # A sandbox reattached by name was created earlier than we know.
            if extras.get("created_here") and isinstance(started, (int, float)):
                out["expires_at"] = _utc(started + limit)
        activity = extras.get("activity")
        if isinstance(activity, SandboxActivity):
            out["last_active_at"] = _utc(activity.last_active_at)
            out["busy"] = activity.busy
        return out

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
        backend = effective_backend(session.sandbox_backend, global_backend)
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
        # Create/reuse the Modal sandbox and return immediately. Workspace
        # sync (not skills) runs in the background so the UI can leave "Starting".
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
        # The user stopped it; there is nothing to explain afterwards.
        clear_last_stop(session_id)
        result = self.status(session_id)
        self._publish(result)
        return result

    def restart(self, session_id: str) -> SessionSandboxStatus:
        self.stop(session_id)
        return self.start(session_id)
