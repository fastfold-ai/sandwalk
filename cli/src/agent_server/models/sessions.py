from __future__ import annotations

from datetime import datetime
from typing import Literal

from agent_server.models.base import ApiModel

SessionStatus = Literal["idle", "running", "interrupted", "error"]


OrganizeLabel = Literal["pinned", "archive"]


SandboxBackendChoice = Literal["builtin", "modal"]


class AgentSession(ApiModel):
    id: str
    title: str
    status: SessionStatus = "idle"
    organize_label: OrganizeLabel | None = None
    project_id: str | None = None
    specialist_id: str | None = None
    sandbox_backend: SandboxBackendChoice | None = None
    workspace_path: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateSessionRequest(ApiModel):
    title: str | None = None
    workspace_path: str | None = None
    project_id: str | None = None
    specialist_id: str | None = None
    sandbox_backend: SandboxBackendChoice | None = None


class UpdateSessionRequest(ApiModel):
    title: str | None = None
    organize_label: OrganizeLabel | None = None
    clear_organize_label: bool = False
    project_id: str | None = None
    clear_project_id: bool = False
    specialist_id: str | None = None
    clear_specialist_id: bool = False
    sandbox_backend: SandboxBackendChoice | None = None
    clear_sandbox_backend: bool = False


class AutoTitleSessionRequest(ApiModel):
    force: bool = False


class SessionSandboxStatus(ApiModel):
    session_id: str
    backend: SandboxBackendChoice
    session_backend: SandboxBackendChoice | None = None
    global_backend: SandboxBackendChoice = "builtin"
    status: Literal[
        "ready", "running", "stopped", "unavailable", "starting", "stopping"
    ] = "ready"
    provider_sandbox_name: str | None = None
    modal_configured: bool = False
    compute_type: str = "cpu"
    gpu_class: str = "T4"
    cpu_cores: float = 2.0
    ram_gb: float = 8.0
    cpu_image: str = "python:3.12-slim"
    gpu_image: str = "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"
    # Active base image for the current compute mode (CPU or GPU).
    base_image: str = "python:3.12-slim"
    detail: str | None = None


class SessionList(ApiModel):
    data: list[AgentSession]


class DeleteSessionResponse(ApiModel):
    deleted: bool = True


class InterruptRunResponse(ApiModel):
    interrupted: bool
