"""LangChain tools for inspecting and controlling the chat sandbox.

Mirrors cloud agents-api ``check_thread_sandbox_status_tool`` /
``start_thread_sandbox_tool`` so the local agent can answer user requests like
"is my Modal sandbox running?" or "start/stop the sandbox".
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

SANDBOX_CONTROL_TOOL_NAMES = (
    "sandbox_status",
    "sandbox_start",
    "sandbox_stop",
)


def _status_payload(status: Any) -> dict[str, Any]:
    if hasattr(status, "model_dump"):
        data = status.model_dump()
    elif isinstance(status, dict):
        data = dict(status)
    else:
        data = {
            "session_id": getattr(status, "session_id", None),
            "backend": getattr(status, "backend", None),
            "status": getattr(status, "status", None),
            "detail": getattr(status, "detail", None),
        }
    return data


def _format_status(status: Any, *, summary: str) -> str:
    payload = _status_payload(status)
    return f"{summary}\nDetails: {json.dumps(payload, ensure_ascii=True)}"


def create_sandbox_control_tools(
    session_id: str,
    *,
    store: Any | None = None,
) -> list:
    """Build ``sandbox_status`` / ``sandbox_start`` / ``sandbox_stop`` tools.

    ``session_id`` is closed over so the model does not need to pass it.
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, ConfigDict, Field

    from agent_server.session_sandbox_service import SessionSandboxService
    from agent_server.store import AgentStore

    sid = str(session_id or "").strip()
    agent_store = store if store is not None else AgentStore()
    service = SessionSandboxService(agent_store)

    class _EmptyArgs(BaseModel):
        model_config = ConfigDict(extra="forbid")

    class StartArgs(BaseModel):
        model_config = ConfigDict(extra="forbid")
        enable_modal: bool = Field(
            default=True,
            description=(
                "If the chat is still on the Built-in host sandbox, switch it "
                "to Modal before starting. Set false only when Modal is already "
                "selected for this chat."
            ),
        )

    def _missing_session() -> str:
        return (
            "Cannot control sandbox because session_id is missing. "
            "Sandbox lifecycle tools are only available inside a chat session."
        )

    async def status_coro() -> str:
        if not sid:
            return _missing_session()
        try:
            status = service.status(sid)
        except KeyError:
            return f"Session `{sid}` was not found."
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
        return _format_status(status, summary=summary)

    async def start_coro(enable_modal: bool = True) -> str:
        if not sid:
            return _missing_session()
        try:
            status = service.status(sid)
        except KeyError:
            return f"Session `{sid}` was not found."
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
                agent_store.update_session(
                    sid,
                    sandbox_backend="modal",
                    update_sandbox_backend=True,
                )
            except Exception as exc:  # noqa: BLE001
                return f"Failed to switch chat to Modal: {exc}"

        try:
            result = service.start(sid)
        except ValueError as exc:
            return f"Failed to start sandbox: {exc}"
        except KeyError:
            return f"Session `{sid}` was not found."
        except Exception as exc:  # noqa: BLE001
            logger.warning("sandbox_start failed: %s", exc)
            return f"Failed to start sandbox: {exc}"

        state = str(getattr(result, "status", "") or "").lower()
        if state == "running":
            summary = (
                "Modal sandbox is running. Workspace sync may still finish in the "
                "background; prefer `/workspace` paths for Modal compute."
            )
        elif state == "starting":
            summary = "Modal sandbox start requested; wait briefly then re-check status."
        else:
            summary = f"Sandbox start finished with status `{state}`."
        return _format_status(result, summary=summary)

    async def stop_coro() -> str:
        if not sid:
            return _missing_session()
        try:
            result = service.stop(sid)
        except KeyError:
            return f"Session `{sid}` was not found."
        except Exception as exc:  # noqa: BLE001
            logger.warning("sandbox_stop failed: %s", exc)
            return f"Failed to stop sandbox: {exc}"
        return _format_status(
            result,
            summary="Sandbox stop completed. Built-in host tools remain available.",
        )

    def _sync_unsupported(**_kwargs: Any) -> str:
        raise RuntimeError("Sandbox control tools require async invocation")

    return [
        StructuredTool(
            name="sandbox_status",
            description=(
                "Inspect the current chat sandbox (Built-in vs Modal, running/stopped, "
                "compute profile). Use when the user asks about sandbox health/status "
                "or before Modal-only compute if unsure whether Modal is attached."
            ),
            args_schema=_EmptyArgs,
            func=_sync_unsupported,
            coroutine=status_coro,
        ),
        StructuredTool(
            name="sandbox_start",
            description=(
                "Start or attach the Modal sandbox for this chat. Use when the user "
                "asks to start/boot/attach Modal, or when status is stopped and "
                "Modal compute is required. Can switch the chat from Built-in to "
                "Modal when enable_modal=true."
            ),
            args_schema=StartArgs,
            func=_sync_unsupported,
            coroutine=start_coro,
        ),
        StructuredTool(
            name="sandbox_stop",
            description=(
                "Stop/terminate the Modal sandbox for this chat. Use when the user "
                "asks to stop, shut down, or detach the sandbox."
            ),
            args_schema=_EmptyArgs,
            func=_sync_unsupported,
            coroutine=stop_coro,
        ),
    ]
