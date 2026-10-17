"""Versioned API models for the FastFold agent server.

This is a package so each domain (health, sessions, skills, MCP, settings,
etc.) can live in its own module. Import from ``agent_server.models`` as
before — this module re-exports the public API. ``ApiModel``/``to_camel``
live in :mod:`agent_server.models.base`.

Each ``from ... import ...`` line below is intentionally kept on one
(long) physical line — see ``ruff: I001`` ignore for this file in
pyproject.toml — so this aggregator stays under the 150-line cap despite
re-exporting ~140 model names.
"""

from __future__ import annotations

from agent_server.models.base import ApiModel, to_camel
from agent_server.models.account import AccountAbout, AccountOrganization, AccountSummary, AccountUser
from agent_server.models.auth import AuthLoginRequest, AuthSettingsResponse, AuthStatusResponse, ChatGPTAuthStart, ChatGPTAuthStatus, UpdateAuthSettingsRequest
from agent_server.models.bench import BenchActiveStatus, BenchCancelResponse, BenchGradeRequest, BenchGradeResponse, BenchInstallResponse, BenchProgress, BenchQueueItem, BenchResetResponse, BenchResultList, BenchResultSummary, BenchSpawnRequest, BenchSpawnResponse, BenchSuiteCard, BenchSuiteList, BenchSuiteRef
from agent_server.models.connectors import AddSlackSubscriptionRequest, AllowSlackUserRequest, ConnectSlackManualRequest, ConnectorActionResponse, ConnectorName, SessionConnectorMute, SetConnectorMuteRequest, SlackAllowedUser, SlackAllowedUserList, SlackConnectorStatus, SlackDirectory, SlackDirectoryChannel, SlackDirectoryPerson, SlackManifestResponse, SlackMode, SlackOneClickStart, SlackParkedMessage, SlackParkedMessageList, SlackSubscription, SlackSubscriptionList, SlackWorkspace, SlackWorkspaceList, StartSlackOneClickRequest
from agent_server.models.datasets_tools import DatasetInstallResponse, DatasetList, DatasetSummary, ToolBatchAction, ToolBatchActionRequest, ToolBatchActionResponse, ToolList, ToolSummary, UpdateToolRequest
from agent_server.models.doctor import DoctorCheckResult, DoctorDiagnosticsRequest, DoctorReport, DoctorSummary
from agent_server.models.environment import EnvironmentCorePackage, EnvironmentPackage, EnvironmentPackageGroup, EnvironmentPackageMutationResult, EnvironmentPackageRequest, EnvironmentReport
from agent_server.models.health import Capabilities, DiscoverResponse, HealthResponse, ServerCacheInfo, ServerLifecycleResult, ServerStatusReport, ServerSystemInfo, ServiceLogTail, ServiceProcess, ServicesReport
from agent_server.models.integrations import FastfoldOneClickImport, FastfoldOneClickStart, IntegrationField, IntegrationList, IntegrationProvider, IntegrationSecretResponse, IntegrationSetupRequest, IntegrationSetupResponse, IntegrationSetupStep, IntegrationUnlock, UpdateIntegrationRequest, ValidateIntegrationResponse
from agent_server.models.library import DeleteLibraryItemResponse, LibraryItem, LibraryItemList, LibraryKind, LibraryPagination, LibrarySyncResponse, UpdateLibraryItemRequest, UseLibraryInChatRequest, UseLibraryInChatResponse
from agent_server.models.mcp_catalog import ConnectMcpCatalogRequest, ConnectMcpCatalogResponse, McpCatalogEntryStatus, McpCatalogList, ResetFeaturedMcpError, ResetFeaturedMcpResponse, UpdateMcpCatalogRequest
from agent_server.models.mcp_json_config import McpJsonConfigRequest, McpJsonConfigResponse
from agent_server.models.mcp_servers import CreateMcpServerRequest, McpServer, McpServerList, McpToolDetail, UpdateMcpServerRequest, ValidateMcpResponse
from agent_server.models.model_profiles import DeleteModelProfileResponse, DiscoverModelEndpointRequest, ModelProfile, ModelProfileList, ModelProfileProbeResult, ModelProfileSecretResponse, UpsertModelProfileRequest
from agent_server.models.models_catalog import AgentModel, AgentModelList, CreateAgentModelRequest, ModelPreferences, ToggleModelFavoriteRequest, ToggleModelFavoriteResponse, UpdateAgentModelRequest
from agent_server.models.projects import AgentProject, CreateProjectRequest, DeleteProjectFolderFileResponse, DeleteProjectResponse, ProjectFolderFile, ProjectFolderListing, ProjectList, RenameProjectFolderFileRequest, UpdateProjectRequest, UseProjectFolderInChatRequest
from agent_server.models.sessions import AgentSession, AutoTitleSessionRequest, ClientSurface, CompactSessionRequest, CompactSessionResponse, CreateSessionRequest, DuplicateSessionRequest, DeleteSessionResponse, HitlDecision, InterruptRunResponse, OrganizeLabel, SandboxBackendChoice, SessionList, SessionRevision, SessionSandboxStatus, SessionSource, SessionStatus, SubmitApprovalsRequest, SubmitApprovalsResponse, TitleSource, UpdateSessionRequest
from agent_server.models.usage import (
    UsageBackfillResponse,
    UsageChartModel,
    UsageDayPoint,
    UsageModelDayPoint,
    UsageModelRow,
    UsageOverview,
)
from agent_server.models.sessions_messages import AgentMessage, EventEnvelope, EventList, MessageFeedbackRequest, MessageFeedbackResponse, MessageList, MessageRole, MessageSource, SendMessageRequest, StartRunResponse
from agent_server.models.sessions_pty import CreatePtyRequest, PtySessionInfo, PtySessionList, UpdatePtyRequest
from agent_server.models.terminals import CreateTerminalRequest, TerminalSession, TerminalSessionList, TerminalStatus, TerminalTitleSource, UpdateTerminalRequest
from agent_server.models.workspace_items import WorkspaceItem, WorkspaceItemKind, WorkspaceItemList
from agent_server.models.sessions_workspace import CreateWorkspaceFolderRequest, MoveWorkspaceFileRequest, WorkspaceFile, WorkspaceFileContent, WorkspaceFileList, WorkspaceMutationResponse, WriteWorkspaceFileRequest
from agent_server.models.settings import OnboardingSettings, PromptBudgetBucket, PromptBudgetResponse, PromptBudgetToolCounts, RunCapacity, RuntimeSettings, SandboxProbeReport, SandboxProbeStep, SandboxSettings, UpdateOnboardingSettingsRequest, UpdateRuntimeSettingsRequest, UpdateSandboxSettingsRequest
from agent_server.models.sites import DeleteSiteResponse, PublishSiteRequest, RegisterSiteRequest, RenameSiteRequest, Site, SiteList, SitePreview, SitePublishResult
from agent_server.models.skills import CatalogLeaderboard, CatalogSkill, CatalogSkillAudit, CatalogSkillAuditEntry, CatalogSkillDetail, CatalogSkillFile, CatalogSkillList, InstallSkillDepsRequest, InstallSkillRequest, SkillBatchAction, SkillBatchActionFailure, SkillBatchActionRequest, SkillBatchActionResponse, SkillDepCheck, SkillDepsInstallResponse, SkillDepsStatus, SkillDepSetupStep, SkillDetail, SkillList, SkillMutationResponse, SkillSource, SkillSourceList, SkillSummary, UpdateSkillRequest
from agent_server.models.specialists import CreateSpecialistRequest, DeleteSpecialistResponse, Specialist, SpecialistList, UpdateSpecialistRequest
from agent_server.models.storage import StorageCategory, StorageDatabaseProbe, StorageLocation, StorageReport
