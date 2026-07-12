"""Versioned API models for the FastFold agent server."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


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
    service: str = "Sandwalk"
    version: str
    backend_id: str
    user_name: str | None = None
    capabilities: Capabilities = Field(default_factory=Capabilities)


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


class ServerCacheInfo(ApiModel):
    file_count: int = 0
    total_bytes: int = 0
    path: str


class ServerStatusReport(ApiModel):
    status: Literal["running", "degraded"] = "running"
    service: str = "Sandwalk"
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


SessionStatus = Literal["idle", "running", "interrupted", "error"]
OrganizeLabel = Literal["pinned", "archive"]


class AgentProject(ApiModel):
    id: str
    name: str
    description: str | None = None
    agent_context: str | None = None
    pinned: bool = False
    session_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreateProjectRequest(ApiModel):
    name: str = Field(min_length=1)
    description: str | None = None
    agent_context: str | None = None
    pinned: bool = False


class UpdateProjectRequest(ApiModel):
    name: str | None = None
    description: str | None = None
    agent_context: str | None = None
    pinned: bool | None = None
    clear_description: bool = False
    clear_agent_context: bool = False


class ProjectList(ApiModel):
    data: list[AgentProject]


class DeleteProjectResponse(ApiModel):
    deleted: bool = True


class AgentSession(ApiModel):
    id: str
    title: str
    status: SessionStatus = "idle"
    organize_label: OrganizeLabel | None = None
    project_id: str | None = None
    workspace_path: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateSessionRequest(ApiModel):
    title: str | None = None
    workspace_path: str | None = None
    project_id: str | None = None


class UpdateSessionRequest(ApiModel):
    title: str | None = None
    organize_label: OrganizeLabel | None = None
    clear_organize_label: bool = False
    project_id: str | None = None
    clear_project_id: bool = False


class AutoTitleSessionRequest(ApiModel):
    force: bool = False


MessageRole = Literal["user", "assistant", "system"]


class AgentMessage(ApiModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    created_at: datetime


class SendMessageRequest(ApiModel):
    content: str = Field(min_length=1)


class StartRunResponse(ApiModel):
    run_id: str


class EventEnvelope(ApiModel):
    schema_version: Literal[1] = 1
    id: str
    session_id: str
    run_id: str | None = None
    sequence: int
    timestamp: datetime
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionList(ApiModel):
    data: list[AgentSession]


class MessageList(ApiModel):
    data: list[AgentMessage]
    feedback: dict[str, Literal["up", "down"]] = Field(default_factory=dict)


class DeleteSessionResponse(ApiModel):
    deleted: bool = True


class InterruptRunResponse(ApiModel):
    interrupted: bool


class WorkspaceFile(ApiModel):
    path: str
    name: str
    type: Literal["file", "directory"]
    size: int | None = None
    mtime: datetime | None = None


class WorkspaceFileList(ApiModel):
    data: list[WorkspaceFile]


class WorkspaceFileContent(ApiModel):
    path: str
    content: str
    encoding: Literal["text", "base64"] = "text"
    mime_type: str
    version: str
    size: int
    mtime: datetime


class WriteWorkspaceFileRequest(ApiModel):
    path: str
    content: str
    encoding: Literal["text", "base64"] = "text"
    base_version: str | None = None


class CreateWorkspaceFolderRequest(ApiModel):
    path: str


class MoveWorkspaceFileRequest(ApiModel):
    source_path: str
    target_path: str


class WorkspaceMutationResponse(ApiModel):
    path: str


class SkillSummary(ApiModel):
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    source: str
    author: str
    version: str | None = None
    updated_at: str | None = None
    icon_src: str | None = None
    enabled: bool = True


class SkillList(ApiModel):
    data: list[SkillSummary]


class SkillDetail(SkillSummary):
    content: str
    directory: str | None = None


class InstallSkillRequest(ApiModel):
    source: str = Field(min_length=1)


class UpdateSkillRequest(ApiModel):
    enabled: bool | None = None


class SkillMutationResponse(ApiModel):
    ok: bool
    summary: str
    installed: list[str] = Field(default_factory=list)


SkillBatchAction = Literal["enable", "disable", "remove"]


class SkillBatchActionRequest(ApiModel):
    action: SkillBatchAction
    names: list[str] = Field(default_factory=list)


class SkillBatchActionFailure(ApiModel):
    name: str
    reason: str


class SkillBatchActionResponse(ApiModel):
    ok: bool
    action: SkillBatchAction
    requested: int
    succeeded: list[str] = Field(default_factory=list)
    failed: list[SkillBatchActionFailure] = Field(default_factory=list)
    summary: str


class SkillSource(ApiModel):
    provider: str
    source: str
    url: str
    description: str


class SkillSourceList(ApiModel):
    data: list[SkillSource]


class CatalogSkill(ApiModel):
    id: str
    slug: str
    name: str
    source: str
    installs: int = 0
    source_type: str = ""
    install_url: str | None = None
    url: str | None = None


class CatalogSkillList(ApiModel):
    data: list[CatalogSkill]
    query: str
    count: int = 0


class CatalogSkillFile(ApiModel):
    path: str
    contents: str


class CatalogSkillDetail(ApiModel):
    id: str
    source: str
    slug: str
    installs: int = 0
    hash: str | None = None
    files: list[CatalogSkillFile] | None = None


class CatalogSkillAuditEntry(ApiModel):
    provider: str
    slug: str
    status: str
    summary: str
    audited_at: str | None = None
    risk_level: str | None = None
    categories: list[str] = Field(default_factory=list)


class CatalogSkillAudit(ApiModel):
    id: str
    source: str
    slug: str
    audits: list[CatalogSkillAuditEntry] = Field(default_factory=list)


class IntegrationField(ApiModel):
    env_var: str
    label: str
    is_secret: bool = True
    configured: bool
    source: Literal["environment", "config", "none"]
    masked_preview: str | None = None


class IntegrationProvider(ApiModel):
    key: str
    name: str
    category: str
    description: str
    env_var: str
    configured: bool
    source: Literal["environment", "config", "none"]
    masked_preview: str | None = None
    setup_url: str | None = None
    free: bool = False
    fields: list[IntegrationField] = Field(default_factory=list)


class IntegrationList(ApiModel):
    data: list[IntegrationProvider]


class UpdateIntegrationRequest(ApiModel):
    value: str | None = None
    values: dict[str, str] = Field(default_factory=dict)


class ValidateIntegrationResponse(ApiModel):
    ok: bool
    configured: bool
    source: Literal["environment", "config", "none"]
    message: str


class IntegrationSetupStep(ApiModel):
    id: str
    label: str
    ok: bool
    detail: str


class IntegrationSetupResponse(ApiModel):
    ok: bool
    integration_key: str
    summary: str
    steps: list[IntegrationSetupStep] = Field(default_factory=list)


class IntegrationSetupRequest(ApiModel):
    working_directory: str | None = None


class RuntimeSettings(ApiModel):
    provider: str
    model: str
    openai_base_url: str | None = None
    agent_profile: str
    tool_mode: str


class UpdateRuntimeSettingsRequest(ApiModel):
    provider: str | None = None
    model: str | None = None
    openai_base_url: str | None = None
    agent_profile: str | None = None
    tool_mode: str | None = None


class AccountUser(ApiModel):
    id: str | None = None
    email: str | None = None
    username: str | None = None
    plan_code: str | None = None
    plan_label: str | None = None


class AccountOrganization(ApiModel):
    id: str | None = None
    name: str | None = None
    team_id: str | None = None


class AccountAbout(ApiModel):
    product: str = "FastFold Agent"
    version: str
    channel: str = "default"
    latest_version: str | None = None
    up_to_date: bool | None = None
    licenses_url: str | None = None


class AccountSummary(ApiModel):
    configured: bool = False
    user: AccountUser | None = None
    organization: AccountOrganization | None = None
    billing_url: str | None = None
    about: AccountAbout


class AgentModel(ApiModel):
    id: str
    label: str
    description: str | None = None
    provider: str
    source: Literal["cloud", "profile", "custom"]
    profile_id: str | None = None
    enabled: bool = True
    health: str | None = None


class AgentModelList(ApiModel):
    data: list[AgentModel] = Field(default_factory=list)
    count: int = 0


class DatasetSummary(ApiModel):
    id: str
    description: str
    status: Literal["complete", "partial", "missing", "on-demand"]
    files_found: int = 0
    files_expected: int = 0
    size_bytes: int | None = None
    size_display: str = "-"
    auto_download: bool = False
    path: str
    source: str | None = None
    note: str | None = None


class DatasetList(ApiModel):
    data: list[DatasetSummary] = Field(default_factory=list)
    count: int = 0


class DatasetInstallResponse(ApiModel):
    ok: bool
    id: str
    status: str
    summary: str
    dataset: DatasetSummary | None = None


class ToolSummary(ApiModel):
    id: str
    name: str
    category: str
    status: Literal["stable", "experimental", "guarded"]
    description: str
    requires_data: list[str] = Field(default_factory=list)
    enabled: bool = True


class ToolList(ApiModel):
    data: list[ToolSummary] = Field(default_factory=list)
    count: int = 0
    categories: list[str] = Field(default_factory=list)
    load_errors: dict[str, str] = Field(default_factory=dict)


class UpdateToolRequest(ApiModel):
    enabled: bool | None = None


ToolBatchAction = Literal["enable", "disable"]


class ToolBatchActionRequest(ApiModel):
    action: ToolBatchAction
    ids: list[str] = Field(default_factory=list)


class ToolBatchActionResponse(ApiModel):
    ok: bool
    action: ToolBatchAction
    requested: int
    succeeded: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    summary: str


class CreateAgentModelRequest(ApiModel):
    id: str
    provider: str = "openai"
    label: str | None = None


class UpdateAgentModelRequest(ApiModel):
    enabled: bool | None = None


class ModelProfile(ApiModel):
    id: str
    label: str
    backend: str
    base_url: str | None = None
    default_model: str | None = None
    discovery: list[str] = Field(default_factory=list)
    has_api_key: bool = False
    api_key_preview: str | None = None
    is_cloud: bool = False
    is_active: bool = False
    is_default: bool = False


class ModelProfileList(ApiModel):
    data: list[ModelProfile] = Field(default_factory=list)
    count: int = 0


class UpsertModelProfileRequest(ApiModel):
    id: str | None = None
    label: str | None = None
    backend: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    discovery: list[str] | None = None
    set_active: bool = False
    set_default: bool = False


class ModelProfileProbeResult(ApiModel):
    profile_id: str
    health: str
    models: list[str] = Field(default_factory=list)
    models_source: str | None = None
    error: str | None = None


class DeleteModelProfileResponse(ApiModel):
    ok: bool
    id: str


class McpServer(ApiModel):
    id: str
    name: str
    transport: Literal["stdio", "sse", "streamable_http"]
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    enabled: bool = True
    catalog_id: str | None = None
    description: str | None = None
    oauth_client_id: str | None = None
    oauth_server_url: str | None = None
    oauth_scopes: str | None = None
    headers_helper_command: str | None = None
    header_names: list[str] = Field(default_factory=list)
    headers_configured: bool = False
    created_at: datetime
    updated_at: datetime


class McpServerList(ApiModel):
    data: list[McpServer]


class McpCatalogEntryStatus(ApiModel):
    id: str
    name: str
    description: str
    url: str
    transport: Literal["stdio", "sse", "streamable_http"]
    auth_mode: str
    preferred_auth: str
    api_key_env_var: str | None = None
    docs_url: str | None = None
    setup_url: str | None = None
    integration_key: str | None = None
    default_enabled: bool = False
    configured: bool = False
    auth_method: str | None = None
    enabled: bool = False
    server_id: str | None = None
    connected: bool = False
    tool_count: int | None = None
    status_message: str | None = None


class McpCatalogList(ApiModel):
    data: list[McpCatalogEntryStatus]


class ConnectMcpCatalogRequest(ApiModel):
    method: Literal["oauth", "api_key"] = "oauth"
    api_key: str | None = None


class UpdateMcpCatalogRequest(ApiModel):
    enabled: bool


class ConnectMcpCatalogResponse(ApiModel):
    ok: bool = True
    authorize_url: str | None = None
    state: str | None = None
    redirect_uri: str | None = None
    catalog_id: str | None = None
    server_id: str | None = None
    enabled: bool | None = None
    tool_count: int | None = None
    message: str | None = None
    tools: list[str] = Field(default_factory=list)


class ValidateMcpResponse(ApiModel):
    ok: bool
    tool_count: int = 0
    message: str
    tools: list[str] = Field(default_factory=list)


class CreateMcpServerRequest(ApiModel):
    name: str = Field(min_length=1)
    transport: Literal["stdio", "sse", "streamable_http"]
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    enabled: bool = True
    catalog_id: str | None = None
    description: str | None = None
    oauth_client_id: str | None = None
    oauth_server_url: str | None = None
    oauth_scopes: str | None = None
    headers_helper_command: str | None = None
    headers: dict[str, str] | None = None


class UpdateMcpServerRequest(ApiModel):
    name: str | None = None
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    enabled: bool | None = None
    catalog_id: str | None = None
    description: str | None = None
    oauth_client_id: str | None = None
    oauth_server_url: str | None = None
    oauth_scopes: str | None = None
    headers_helper_command: str | None = None
    headers: dict[str, str] | None = None


class MessageFeedbackRequest(ApiModel):
    reaction: Literal["up", "down"] | None = None


class MessageFeedbackResponse(ApiModel):
    message_id: str
    reaction: Literal["up", "down"] | None = None


class PtySessionInfo(ApiModel):
    id: str
    session_id: str
    title: str
    cwd: str
    cols: int = 80
    rows: int = 24
    pid: int
    status: Literal["running", "exited"] = "running"


class PtySessionList(ApiModel):
    data: list[PtySessionInfo]


class CreatePtyRequest(ApiModel):
    title: str | None = None
    cols: int = Field(default=80, ge=1, le=500)
    rows: int = Field(default=24, ge=1, le=200)


class UpdatePtyRequest(ApiModel):
    title: str | None = None
    cols: int | None = Field(default=None, ge=1, le=500)
    rows: int | None = Field(default=None, ge=1, le=200)


class DoctorCheckResult(ApiModel):
    name: str
    status: Literal["ok", "warn", "error"]
    detail: str
    category: str = "general"
    fix: str | None = None


class DoctorSummary(ApiModel):
    ok: int = 0
    warn: int = 0
    error: int = 0
    total: int = 0


class DoctorReport(ApiModel):
    ok: bool
    checked_at: str
    summary: DoctorSummary
    checks: list[DoctorCheckResult] = Field(default_factory=list)


class DoctorDiagnosticsRequest(ApiModel):
    ui_diagnostics: dict[str, Any] | None = None


class StorageLocation(ApiModel):
    path: str
    label: str = "default location"
    bytes: int = 0


class StorageCategory(ApiModel):
    id: str
    label: str
    color: str
    bytes: int = 0
    path: str | None = None
    children: list["StorageCategory"] = Field(default_factory=list)


class StorageReport(ApiModel):
    location: StorageLocation
    categories: list[StorageCategory] = Field(default_factory=list)
    total_bytes: int = 0
    available_bytes: int = 0
    checked_at: str


class EnvironmentPackage(ApiModel):
    name: str
    version: str | None = None
    installed: bool = False
    removable: bool = True


class EnvironmentPackageGroup(ApiModel):
    id: str
    label: str
    description: str
    packages: list[EnvironmentPackage] = Field(default_factory=list)


class EnvironmentCorePackage(ApiModel):
    name: str
    version: str


class EnvironmentReport(ApiModel):
    python_path: str
    env_path: str | None = None
    env_bytes: int = 0
    groups: list[EnvironmentPackageGroup] = Field(default_factory=list)
    core: list[EnvironmentCorePackage] = Field(default_factory=list)
    checked_at: str


class EnvironmentPackageRequest(ApiModel):
    name: str = Field(min_length=1)
    # When true, allow installing packages outside the skill/tool catalog
    # (still never core FastFold dependencies).
    allow_unlisted: bool = False


class EnvironmentPackageMutationResult(ApiModel):
    ok: bool = True
    action: Literal["install", "uninstall"]
    name: str
    version: str | None = None
    installed: bool = False
    message: str = ""

