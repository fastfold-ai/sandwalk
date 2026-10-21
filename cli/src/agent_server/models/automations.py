"""API models for Automations (Cron & Event Schedules) and Remote-SSH Management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from agent_server.models.base import ApiModel

AutomationScheduleKind = Literal["once", "interval", "cron", "webhook"]
AutomationSessionMode = Literal["continue", "fresh", "no_agent"]
AutomationStatus = Literal["idle", "running", "succeeded", "failed", "paused", "completed"]
AutomationRunStatus = Literal["running", "succeeded", "failed", "skipped"]


class Automation(ApiModel):
    id: str
    name: str
    description: str | None = None
    prompt: str = ""
    command: str | None = None
    schedule_expr: str = "every 1h"
    schedule_kind: AutomationScheduleKind = "interval"
    schedule_label: str = "Every hour"
    session_mode: AutomationSessionMode = "fresh"
    origin_session_id: str | None = None
    specialist_id: str | None = None
    project_id: str | None = None
    workdir: str | None = None
    ssh_host_id: str | None = None
    remote_workdir: str | None = None
    skill_names: list[str] = []
    tool_names: list[str] = []
    mcp_server_ids: list[str] = []
    provider_pin: str | None = None
    model_pin: str | None = None
    continuity: bool = False
    context_from: list[str] = []
    wake_on_change_only: bool = False
    repeat_limit: int | None = None
    run_count: int = 0
    enabled: bool = True
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_status: AutomationStatus = "idle"
    last_error: str | None = None
    webhook_token: str | None = None
    template_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AutomationList(ApiModel):
    data: list[Automation]


class CreateAutomationRequest(ApiModel):
    name: str | None = None
    description: str | None = None
    prompt: str = ""
    command: str | None = None
    schedule_expr: str = "every 1h"
    session_mode: AutomationSessionMode = "fresh"
    origin_session_id: str | None = None
    specialist_id: str | None = None
    project_id: str | None = None
    workdir: str | None = None
    ssh_host_id: str | None = None
    remote_workdir: str | None = None
    skill_names: list[str] = []
    tool_names: list[str] = []
    mcp_server_ids: list[str] = []
    provider_pin: str | None = None
    model_pin: str | None = None
    continuity: bool = False
    context_from: list[str] = []
    wake_on_change_only: bool = False
    repeat_limit: int | None = None
    enabled: bool = True
    template_id: str | None = None


class UpdateAutomationRequest(ApiModel):
    name: str | None = None
    description: str | None = None
    prompt: str | None = None
    command: str | None = None
    clear_command: bool = False
    schedule_expr: str | None = None
    session_mode: AutomationSessionMode | None = None
    origin_session_id: str | None = None
    clear_origin_session_id: bool = False
    specialist_id: str | None = None
    clear_specialist_id: bool = False
    project_id: str | None = None
    clear_project_id: bool = False
    workdir: str | None = None
    clear_workdir: bool = False
    ssh_host_id: str | None = None
    clear_ssh_host_id: bool = False
    remote_workdir: str | None = None
    clear_remote_workdir: bool = False
    skill_names: list[str] | None = None
    tool_names: list[str] | None = None
    mcp_server_ids: list[str] | None = None
    provider_pin: str | None = None
    model_pin: str | None = None
    clear_model_pin: bool = False
    continuity: bool | None = None
    context_from: list[str] | None = None
    wake_on_change_only: bool | None = None
    repeat_limit: int | None = None
    clear_repeat_limit: bool = False
    enabled: bool | None = None


class AutomationRun(ApiModel):
    id: str
    automation_id: str
    automation_name: str | None = None
    session_id: str | None = None
    status: AutomationRunStatus = "running"
    trigger_source: str = "schedule"
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    output_excerpt: str | None = None
    output_path: str | None = None
    error: str | None = None
    was_catchup: bool = False


class AutomationRunList(ApiModel):
    data: list[AutomationRun]


class TriggerAutomationRequest(ApiModel):
    context: str | None = None
    wait: bool = False


class AutomationTemplate(ApiModel):
    id: str
    name: str
    category: Literal[
        "popular",
        "hpc_slurm",
        "bio_compchem",
        "memory_wiki",
        "code_ci",
        "environment",
    ]
    description: str
    schedule_expr: str
    schedule_label: str
    session_mode: AutomationSessionMode = "fresh"
    prompt: str
    command: str | None = None
    continuity: bool = False
    wake_on_change_only: bool = False
    recommended_specialist_slug: str | None = None
    skill_names: list[str] = []
    tool_names: list[str] = []
    badge: str = "Scheduled"


class AutomationTemplateList(ApiModel):
    data: list[AutomationTemplate]


class DeleteAutomationResponse(ApiModel):
    deleted: bool = True


# --- SSH Manager & Remote-SSH Bootstrap Models ---

SshHostSource = Literal["saved", "ssh_config"]
SshConnectionStatus = Literal["unknown", "online", "offline", "bootstrapping", "tunnel_active", "error"]


class SshHost(ApiModel):
    id: str
    alias: str
    host: str
    user: str | None = None
    port: int = 22
    identity_file: str | None = None
    proxy_jump: str | None = None
    remote_port: int = 8787
    default_workdir: str | None = None
    source: SshHostSource = "saved"
    status: SshConnectionStatus = "unknown"
    platform: str | None = None
    arch: str | None = None
    hostname: str | None = None
    gpu_summary: str | None = None
    slurm_available: bool = False
    sandwalk_installed: bool = False
    sandwalk_version: str | None = None
    daemon_running: bool = False
    tunnel_local_port: int | None = None
    tunnel_url: str | None = None
    last_connected_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class SshHostList(ApiModel):
    data: list[SshHost]


class CreateSshHostRequest(ApiModel):
    target: str
    alias: str | None = None
    port: int | None = None
    identity_file: str | None = None
    proxy_jump: str | None = None
    remote_port: int = 8787
    default_workdir: str | None = None


class UpdateSshHostRequest(ApiModel):
    alias: str | None = None
    host: str | None = None
    user: str | None = None
    port: int | None = None
    identity_file: str | None = None
    proxy_jump: str | None = None
    remote_port: int | None = None
    default_workdir: str | None = None


class SshProbeResult(ApiModel):
    host_id: str
    reachable: bool
    auth_required: bool = False
    hostname: str | None = None
    platform: str | None = None
    arch: str | None = None
    gpu_summary: str | None = None
    slurm_available: bool = False
    sandwalk_installed: bool = False
    sandwalk_version: str | None = None
    daemon_running: bool = False
    default_workdir: str | None = None
    detail: str | None = None


class SshBootstrapStep(ApiModel):
    step: str
    status: Literal["pending", "running", "completed", "failed"]
    detail: str | None = None


class SshConnectRequest(ApiModel):
    host_id_or_target: str
    alias: str | None = None
    password: str | None = None
    save_to_ssh_config: bool = False
    auto_install: bool = True
    start_daemon: bool = True
    open_tunnel: bool = True
    enable_watchdog: bool = True
    remote_port: int | None = None
    default_workdir: str | None = None


class SshConnectResponse(ApiModel):
    host: SshHost
    steps: list[SshBootstrapStep] = []
    auth_required: bool = False
    key_installed: bool = False
    local_url: str | None = None
    remote_api_key: str | None = None
    hostname: str | None = None
    platform: str | None = None
    daemon_persistence: str | None = None
    watchdog_installed: bool = False


class SshConfigFileResponse(ApiModel):
    path: str
    content: str


class UpdateSshConfigFileRequest(ApiModel):
    content: str


class SshExecRequest(ApiModel):
    host_id_or_target: str
    command: str
    workdir: str | None = None
    timeout_seconds: float = 60.0


class SshExecResponse(ApiModel):
    host_id: str
    command: str
    workdir: str | None = None
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class SshSyncRequest(ApiModel):
    host_id_or_target: str
    local_path: str
    remote_path: str
    direction: Literal["push", "pull"] = "push"
    delete: bool = False


class SshSyncResponse(ApiModel):
    host_id: str
    direction: Literal["push", "pull"]
    local_path: str
    remote_path: str
    exit_code: int
    summary: str
    duration_seconds: float


class DeleteSshHostResponse(ApiModel):
    deleted: bool = True


class SshSlurmQueueEntry(ApiModel):
    job_id: str
    partition: str
    name: str
    user: str
    state: str
    time_used: str
    nodes: str
    reason_or_nodelist: str


class SshSlurmStatusResponse(ApiModel):
    host_id: str
    slurm_available: bool
    jobs: list[SshSlurmQueueEntry] = []
    raw_output: str = ""
    extra: dict[str, Any] = {}
