"""Builds the ``sandbox_status`` / ``sandbox_start`` / ``sandbox_stop`` tools."""

from __future__ import annotations

from typing import Any

from .context import SandboxControlContext


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

    ctx = SandboxControlContext(session_id, store=store)

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
        compute_type: str | None = Field(
            default=None,
            description=(
                "Optional Modal compute mode: 'cpu' or 'gpu'. Set to 'gpu' when "
                "the user asks for a GPU / CUDA / T4 (etc.) sandbox. CUDA comes "
                "from sandbox.gpu_image (default pytorch CUDA runtime)."
            ),
        )
        gpu_class: str | None = Field(
            default=None,
            description=(
                "Optional Modal GPU class when compute_type='gpu' "
                "(e.g. T4, A10G, A100, H100, L4, L40S)."
            ),
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
            coroutine=ctx.status_coro,
        ),
        StructuredTool(
            name="sandbox_start",
            description=(
                "Start or attach the Modal sandbox for this chat. Use when the user "
                "asks to start/boot/attach Modal, or when status is stopped and "
                "Modal compute is required. Can switch the chat from Built-in to "
                "Modal when enable_modal=true. When the user requests a GPU "
                "(T4/A10G/…), pass compute_type='gpu' and gpu_class so the CUDA "
                "base image is used — CPU images have no nvidia-smi."
            ),
            args_schema=StartArgs,
            func=_sync_unsupported,
            coroutine=ctx.start_coro,
        ),
        StructuredTool(
            name="sandbox_stop",
            description=(
                "Stop/terminate the Modal sandbox for this chat. Use when the user "
                "asks to stop, shut down, or detach the sandbox."
            ),
            args_schema=_EmptyArgs,
            func=_sync_unsupported,
            coroutine=ctx.stop_coro,
        ),
    ]
