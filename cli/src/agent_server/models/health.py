from __future__ import annotations

from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class Capabilities(ApiModel):
    api_version: Literal["v1"] = "v1"
    sessions: bool = True
    event_replay: bool = True
    local_filesystem: bool = False
    skills: bool = False
    integrations: bool = False
    mcp: bool = False
    terminal: bool = False
    execution_backends: list[str] = Field(default_factory=lambda: ["local"])


class HealthResponse(ApiModel):
    status: Literal["ok", "degraded"] = "ok"
    service: str = "sandwalk"
    version: str
    backend_id: str
    user_name: str | None = None
    capabilities: Capabilities = Field(default_factory=Capabilities)


class DiscoverResponse(ApiModel):
    """Auth-exempt LAN probe payload (keep small — no RAM/GPU/pid)."""

    service: Literal["sandwalk"] = "sandwalk"
    version: str
    hostname: str
    platform: str
    arch: str
    device_label: str
    auth_required: bool = False


class ServerSystemInfo(ApiModel):
    label: str
    platform: str
    arch: str
    os_version: str
    python_version: str
    ram_used_bytes: int = 0
    ram_total_bytes: int = 0
    thermal_state: str | None = None
    load_average: list[float] | None = None
    chip_name: str | None = None
    gpu_cores: int | None = None
    gpu_utilization_percent: float | None = None
    gpu_memory_used_bytes: int | None = None
    gpu_memory_total_bytes: int | None = None


class ServerCacheInfo(ApiModel):
    file_count: int = 0
    total_bytes: int = 0
    path: str


class ServerStatusReport(ApiModel):
    status: Literal["running", "degraded"] = "running"
    service: str = "sandwalk"
    version: str
    message: str | None = None
    host: str | None = None
    port: int | None = None
    pid: int
    started_at: str
    uptime_seconds: float = 0
    system: ServerSystemInfo
    cache: ServerCacheInfo
    checked_at: str


class ServerLifecycleResult(ApiModel):
    ok: bool = True
    action: Literal["stop", "restart"]
    message: str = ""
