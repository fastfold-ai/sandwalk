"""Session-bound sandbox control context: status/start/stop coroutines."""

from __future__ import annotations

import logging
from typing import Any

from .formatting import format_status

logger = logging.getLogger(__name__)


class SandboxControlContext:
    """Holds the session/service state closed over by the control tools."""

    def __init__(self, session_id: str, *, store: Any | None = None):
        from agent_server.session_sandbox_service import SessionSandboxService
        from agent_server.store import AgentStore

        self.sid = str(session_id or "").strip()
        self.agent_store = store if store is not None else AgentStore()
        self.service = SessionSandboxService(self.agent_store)

    def _missing_session(self) -> str:
        return (
            "Cannot control sandbox because session_id is missing. "
            "Sandbox lifecycle tools are only available inside a chat session."
        )

    async def status_coro(self) -> str:
        if not self.sid:
            return self._missing_session()
        try:
            status = self.service.status(self.sid)
        except KeyError:
            return f"Session `{self.sid}` was not found."
        except Exception as exc:  # noqa: BLE001
            logger.warning("sandbox_status failed: %s", exc)
            return f"Failed to check sandbox status: {exc}"

        state = str(getattr(status, "status", "") or "").lower()
        backend = str(getattr(status, "backend", "") or "")
        if backend == "modal":
            if state == "running":
                summary = "Modal sandbox is running and attached for this chat."
            elif state == "starting":
                summary = "Modal sandbox is starting; wait before compute-only work."
            elif state == "unavailable":
                summary = (
                    "Modal is selected but not configured "
                    "(Integrations → Modal tokens)."
                )
            else:
                summary = (
                    "Modal is selected for this chat but the sandbox is stopped. "
                    "Call sandbox_start before Modal-only compute."
                )
        else:
            summary = (
                "This chat uses the Built-in host sandbox "
                "(local workspace + run_python/shell_run). "
                "Call sandbox_start with enable_modal=true if the user wants Modal."
            )
        return format_status(status, summary=summary)

    async def start_coro(
        self,
        enable_modal: bool = True,
        compute_type: str | None = None,
        gpu_class: str | None = None,
    ) -> str:
        if not self.sid:
            return self._missing_session()
        try:
            status = self.service.status(self.sid)
        except KeyError:
            return f"Session `{self.sid}` was not found."
        except Exception as exc:  # noqa: BLE001
            return f"Failed to inspect sandbox before start: {exc}"

        backend = str(getattr(status, "backend", "") or "")
        if backend != "modal":
            if not enable_modal:
                return (
                    "Start is only available when Modal is enabled for this chat. "
                    "Re-call sandbox_start with enable_modal=true (or ask the user "
                    "to toggle Modal in the composer)."
                )
            try:
                self.agent_store.update_session(
                    self.sid,
                    sandbox_backend="modal",
                    update_sandbox_backend=True,
                )
            except Exception as exc:  # noqa: BLE001
                return f"Failed to switch chat to Modal: {exc}"

        apply_error = self._apply_compute_request(
            compute_type=compute_type, gpu_class=gpu_class
        )
        if apply_error:
            return apply_error

        try:
            result = self.service.start(self.sid)
        except ValueError as exc:
            return f"Failed to start sandbox: {exc}"
        except KeyError:
            return f"Session `{self.sid}` was not found."
        except Exception as exc:  # noqa: BLE001
            logger.warning("sandbox_start failed: %s", exc)
            return f"Failed to start sandbox: {exc}"

        state = str(getattr(result, "status", "") or "").lower()
        if state == "running":
            summary = (
                "Modal sandbox is running. Workspace sync may still finish in the "
                "background; prefer `/workspace` paths for Modal compute."
            )
            if str(getattr(result, "compute_type", "")).lower() == "gpu":
                summary += (
                    f" GPU={getattr(result, 'gpu_class', 'T4')}; "
                    f"base image={getattr(result, 'base_image', '')}."
                )
        elif state == "starting":
            summary = "Modal sandbox start requested; wait briefly then re-check status."
        else:
            summary = f"Sandbox start finished with status `{state}`."
        return format_status(result, summary=summary)

    def _apply_compute_request(
        self,
        *,
        compute_type: str | None,
        gpu_class: str | None,
    ) -> str | None:
        """Persist optional compute_type/gpu_class before Modal start."""
        kind = str(compute_type or "").strip().lower() or None
        gpu = str(gpu_class or "").strip() or None
        if kind is None and gpu is None:
            return None
        if kind is None and gpu is not None:
            kind = "gpu"
        if kind not in {"cpu", "gpu"}:
            return "compute_type must be 'cpu' or 'gpu'."
        try:
            from agent_server.models.settings import UpdateSandboxSettingsRequest
            from agent_server.sandbox_settings_service import SandboxSettingsService

            SandboxSettingsService.update(
                UpdateSandboxSettingsRequest(
                    compute_type=kind,  # type: ignore[arg-type]
                    gpu_class=gpu,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return f"Failed to update sandbox compute settings: {exc}"
        return None

    async def stop_coro(self) -> str:
        if not self.sid:
            return self._missing_session()
        try:
            result = self.service.stop(self.sid)
        except KeyError:
            return f"Session `{self.sid}` was not found."
        except Exception as exc:  # noqa: BLE001
            logger.warning("sandbox_stop failed: %s", exc)
            return f"Failed to stop sandbox: {exc}"
        return format_status(
            result,
            summary="Sandbox stop completed. Built-in host tools remain available.",
        )
