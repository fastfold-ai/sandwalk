export const AGENT_API_VERSION = 'v1' as const

export type BackendKind = 'local' | 'self-hosted' | 'cloud'

export type BackendDescriptor = {
  id: string
  name: string
  baseUrl: string
  kind: BackendKind
}

export type BackendCapabilities = {
  apiVersion: typeof AGENT_API_VERSION
  sessions: boolean
  eventReplay: boolean
  localFilesystem: boolean
  skills: boolean
  integrations: boolean
  mcp: boolean
  terminal: boolean
  executionBackends: string[]
}

export type BackendHealth = {
  status: 'ok' | 'degraded'
  service: string
  version: string
  backendId: string
  userName: string | null
  capabilities: BackendCapabilities
}

export type ServerSystemInfo = {
  label: string
  platform: string
  arch: string
  osVersion: string
  pythonVersion: string
  ramUsedBytes: number
  ramTotalBytes: number
  thermalState: string | null
  loadAverage: number[] | null
  chipName?: string | null
  gpuCores?: number | null
  gpuUtilizationPercent?: number | null
  gpuMemoryUsedBytes?: number | null
  gpuMemoryTotalBytes?: number | null
}

export type ServerCacheInfo = {
  fileCount: number
  totalBytes: number
  path: string
}

export type ServerStatusReport = {
  status: 'running' | 'degraded'
  service: string
  version: string
  message: string | null
  host: string | null
  port: number | null
  pid: number
  startedAt: string
  uptimeSeconds: number
  system: ServerSystemInfo
  cache: ServerCacheInfo
  checkedAt: string
}

export type ServerLifecycleResult = {
  ok: boolean
  action: 'stop' | 'restart'
  message: string
}

export type DoctorCheckStatus = 'ok' | 'warn' | 'error'

export type DoctorCheckResult = {
  name: string
  status: DoctorCheckStatus
  detail: string
  category: string
  fix: string | null
}

export type DoctorSummary = {
  ok: number
  warn: number
  error: number
  total: number
}

export type DoctorReport = {
  ok: boolean
  checkedAt: string
  summary: DoctorSummary
  checks: DoctorCheckResult[]
}

export type StorageLocation = {
  path: string
  label: string
  bytes: number
}

export type StorageCategory = {
  id: string
  label: string
  color: string
  bytes: number
  path?: string | null
  children?: StorageCategory[]
}

export type StorageReport = {
  location: StorageLocation
  categories: StorageCategory[]
  totalBytes: number
  availableBytes: number
  checkedAt: string
}

export type EnvironmentPackage = {
  name: string
  version: string | null
  installed: boolean
  removable: boolean
}

export type EnvironmentPackageGroup = {
  id: string
  label: string
  description: string
  packages: EnvironmentPackage[]
}

export type EnvironmentCorePackage = {
  name: string
  version: string
}

export type EnvironmentReport = {
  pythonPath: string
  envPath: string | null
  envBytes: number
  groups: EnvironmentPackageGroup[]
  core: EnvironmentCorePackage[]
  checkedAt: string
}

export type EnvironmentPackageMutationResult = {
  ok: boolean
  action: 'install' | 'uninstall'
  name: string
  version: string | null
  installed: boolean
  message: string
}

export type AgentSessionStatus = 'idle' | 'running' | 'interrupted' | 'error'

export type AgentProject = {
  id: string
  name: string
  description: string | null
  agentContext: string | null
  pinned: boolean
  sessionCount: number
  createdAt: string
  updatedAt: string
}

export type AgentSession = {
  id: string
  title: string
  status: AgentSessionStatus
  organizeLabel: 'pinned' | 'archive' | null
  projectId: string | null
  specialistId: string | null
  sandboxBackend?: 'builtin' | 'modal' | null
  workspacePath: string | null
  lastMessageAt: string | null
  createdAt: string
  updatedAt: string
}

export type SpecialistColor =
  | 'ink'
  | 'gray'
  | 'red'
  | 'orange'
  | 'amber'
  | 'green'
  | 'teal'
  | 'blue'
  | 'indigo'
  | 'violet'
  | 'pink'

export type SpecialistIcon =
  | 'agent'
  | 'organization'
  | 'chat'
  | 'lightning'
  | 'star'
  | 'signpost'
  | 'code'
  | 'database'
  | 'globe'
  | 'flask'
  | 'dna'
  | 'microscope'
  | 'book'
  | 'sparkles'
  | 'hard-hat'
  | 'git-branch'
  | 'target'
  | 'shield'
  | 'heart'
  | 'briefcase'
  | 'atom'

export type Specialist = {
  id: string
  name: string
  slug: string
  description: string | null
  instructions: string | null
  color: SpecialistColor | string
  icon: SpecialistIcon | string
  skillNames: string[]
  toolNames: string[]
  mcpServerIds: string[]
  mcpCatalogIds: string[]
  enabled: boolean
  createdAt: string
  updatedAt: string
}

export type AgentMessageRole = 'user' | 'assistant' | 'system'

export type AgentMessage = {
  id: string
  sessionId: string
  role: AgentMessageRole
  content: string
  createdAt: string
}

export type AgentTodo = {
  id: string
  content: string
  status: 'pending' | 'in_progress' | 'completed'
  activeForm?: string | null
}

type EventEnvelope<TType extends string, TPayload> = {
  schemaVersion: 1
  id: string
  sessionId: string
  runId: string | null
  sequence: number
  timestamp: string
  type: TType
  payload: TPayload
}

export type AgentEvent =
  | EventEnvelope<'session.created' | 'session.updated', { session: AgentSession }>
  | EventEnvelope<'run.started', { messageId: string }>
  | EventEnvelope<'assistant.delta', { delta: string }>
  | EventEnvelope<'assistant.message', { message: AgentMessage }>
  | EventEnvelope<'tool.started', { name: string; arguments: unknown; toolCallId: string }>
  | EventEnvelope<
      'tool.completed',
      {
        name: string
        output: unknown
        toolCallId: string
        isError: boolean
        durationSeconds: number
      }
    >
  | EventEnvelope<'run.progress', { text?: string }>
  | EventEnvelope<'todos.updated', { todos: AgentTodo[] }>
  | EventEnvelope<
      'run.usage',
      {
        inputTokens: number
        outputTokens: number
        cacheCreationInputTokens: number
        cacheReadInputTokens: number
      }
    >
  | EventEnvelope<'run.completed', { messageId: string }>
  | EventEnvelope<'run.failed', { error: string }>
  | EventEnvelope<'run.interrupted', { reason: string }>

export type IntegrationSummary = {
  key: string
  name: string
  category: string
  description: string
  envVar: string
  configured: boolean
  source: 'environment' | 'config' | 'profile' | 'none'
  maskedPreview: string | null
  setupUrl: string | null
  free: boolean
  fields: Array<{
    envVar: string
    label: string
    isSecret: boolean
    configured: boolean
    source: 'environment' | 'config' | 'none'
    maskedPreview: string | null
  }>
}

export type IntegrationSetupStep = {
  id: string
  label: string
  ok: boolean
  detail: string
}

export type IntegrationSetupResult = {
  ok: boolean
  integrationKey: string
  summary: string
  steps: IntegrationSetupStep[]
}

export interface IntegrationProvider {
  listIntegrations(signal?: AbortSignal): Promise<IntegrationSummary[]>
  updateIntegration(
    key: string,
    values: Record<string, string>,
    signal?: AbortSignal,
  ): Promise<IntegrationSummary>
  removeIntegration(key: string, signal?: AbortSignal): Promise<IntegrationSummary>
  autofillIntegration(key: string, signal?: AbortSignal): Promise<IntegrationSummary>
  setupIntegration(
    key: string,
    workingDirectory?: string | null,
    signal?: AbortSignal
  ): Promise<IntegrationSetupResult>
  validateIntegration(
    key: string,
    signal?: AbortSignal,
  ): Promise<{ ok: boolean; message: string }>
}

export type RuntimeSettings = {
  provider: string
  model: string
  openaiBaseUrl: string | null
  /** Active OpenAI-compatible profile id (local oMLX/Ollama/… or openai_cloud). */
  openaiProfileId?: string | null
  agentProfile: string
  toolMode: string
  /** Stored effort level: low | medium | high (Fast maps to API none). */
  reasoningEffort?: string
  /** When true, API reasoning_effort is none regardless of reasoningEffort. */
  reasoningFast?: boolean
  recursionLimit: number
  maxSdkTurns: number
  groupToolTraces: boolean
  toolTraceDetailLimit: number
  backgroundWatchTimeoutS: number
  interruptDrainTimeoutS: number
  parallelMaxThreads: number
  toolHealthEnabled: boolean
  toolHealthFailThreshold: number
  toolHealthSuppressSeconds: number
}

export type OnboardingSettings = {
  completed: boolean
  step: number
}

export type SandboxSettings = {
  backend: 'builtin' | 'modal' | string
  modalApp: string
  cpuImage: string
  gpuImage: string
  pipPackages: string
  computeType: 'cpu' | 'gpu' | string
  gpuClass: string
  cpuCores: number
  ramGb: number
  idleTtlSeconds: number
  modalConfigured: boolean
}

export type SandboxProbeStep = {
  name: string
  ok: boolean
  detail: string
}

export type SandboxProbeReport = {
  ok: boolean
  skipped: boolean
  steps: SandboxProbeStep[]
}

export type SessionSandboxStatus = {
  sessionId: string
  backend: 'builtin' | 'modal' | string
  sessionBackend: 'builtin' | 'modal' | null
  globalBackend: 'builtin' | 'modal' | string
  status: 'ready' | 'running' | 'stopped' | 'unavailable' | 'starting' | 'stopping' | string
  providerSandboxName: string | null
  modalConfigured: boolean
  computeType: string
  gpuClass: string
  cpuCores: number
  ramGb: number
  cpuImage: string
  detail: string | null
  type?: 'sandbox_status'
  ready?: boolean
}

export type AccountUser = {
  id: string | null
  email: string | null
  username: string | null
  planCode: string | null
  planLabel: string | null
}

export type AccountOrganization = {
  id: string | null
  name: string | null
  teamId: string | null
}

export type AccountAbout = {
  product: string
  version: string
  channel: string
  latestVersion: string | null
  upToDate: boolean | null
  licensesUrl: string | null
}

export type AccountSummary = {
  configured: boolean
  user: AccountUser | null
  organization: AccountOrganization | null
  billingUrl: string | null
  about: AccountAbout
}

export type AgentModel = {
  id: string
  label: string
  description: string | null
  provider: string
  source: 'cloud' | 'profile' | 'custom'
  profileId: string | null
  /** Local LLM backend id (ollama, unsloth, omlx, …); null/absent for cloud. */
  backend?: string | null
  enabled: boolean
  health: string | null
  /** True when Effort / Fast controls apply (OpenAI GPT-5 / o-series, etc.). */
  supportsReasoningEffort?: boolean
  reasoningEffortOptions?: string[]
  /** Per-model effort level (low|medium|high). */
  reasoningEffort?: string | null
  /** Per-model Fast toggle. */
  reasoningFast?: boolean
}

export type CreateAgentModelInput = {
  id: string
  provider?: string
  label?: string | null
}

export type ModelProfile = {
  id: string
  label: string
  backend: string
  baseUrl: string | null
  defaultModel: string | null
  discovery: string[]
  hasApiKey: boolean
  apiKeyPreview: string | null
  isCloud: boolean
  isActive: boolean
  isDefault: boolean
}

export type ModelProfileProbeResult = {
  profileId: string
  health: string
  models: string[]
  modelsSource: string | null
  error: string | null
}

export type DiscoverModelEndpointInput = {
  backend?: string | null
  baseUrl: string
  apiKey?: string | null
}

export type UpsertModelProfileInput = {
  id?: string | null
  label?: string | null
  backend?: string | null
  baseUrl?: string | null
  apiKey?: string | null
  defaultModel?: string | null
  discovery?: string[] | null
  setActive?: boolean
  setDefault?: boolean
}

export interface SettingsProvider {
  getRuntimeSettings(signal?: AbortSignal): Promise<RuntimeSettings>
  updateRuntimeSettings(
    changes: Partial<RuntimeSettings>,
    signal?: AbortSignal,
  ): Promise<RuntimeSettings>
  getOnboardingSettings?(signal?: AbortSignal): Promise<OnboardingSettings>
  updateOnboardingSettings?(
    changes: Partial<OnboardingSettings>,
    signal?: AbortSignal,
  ): Promise<OnboardingSettings>
  getSandboxSettings?(signal?: AbortSignal): Promise<SandboxSettings>
  updateSandboxSettings?(
    changes: Partial<SandboxSettings>,
    signal?: AbortSignal,
  ): Promise<SandboxSettings>
  probeSandboxSettings?(signal?: AbortSignal): Promise<SandboxProbeReport>
  getAccount?(
    options?: { checkUpdates?: boolean; signal?: AbortSignal },
  ): Promise<AccountSummary>
  logoutAccount?(signal?: AbortSignal): Promise<AccountSummary>
}

export type DatasetSummary = {
  id: string
  description: string
  status: 'complete' | 'partial' | 'missing' | 'on-demand'
  filesFound: number
  filesExpected: number
  sizeBytes: number | null
  sizeDisplay: string
  autoDownload: boolean
  path: string
  source: string | null
  note: string | null
}

export type DatasetInstallResult = {
  ok: boolean
  id: string
  status: string
  summary: string
  dataset: DatasetSummary | null
}

export type ToolSummary = {
  id: string
  name: string
  category: string
  status: 'stable' | 'experimental' | 'guarded'
  tier?: 'core' | 'extra'
  description: string
  requiresData: string[]
  enabled: boolean
}

export type PromptBudgetBucket = {
  id: string
  label: string
  tokens: number
  chars: number
  count?: number | null
  children: PromptBudgetBucket[]
}

export type PromptBudgetToolCounts = {
  domain: number
  mcp: number
  deepagents: number
  total: number
  openaiCap: number
}

export type PromptBudgetResponse = {
  totalTokens: number
  totalChars: number
  tokenizer: string
  toolMode: string
  provider: string | null
  model: string | null
  specialistId: string | null
  specialistName: string | null
  toolCounts: PromptBudgetToolCounts
  buckets: PromptBudgetBucket[]
  warnings: string[]
  sampleQuery: string
}

export type ToolCatalog = {
  data: ToolSummary[]
  count: number
  categories: string[]
  loadErrors: Record<string, string>
}

export interface DatasetsProvider {
  listDatasets(signal?: AbortSignal): Promise<DatasetSummary[]>
  installDataset(
    datasetId: string,
    signal?: AbortSignal,
  ): Promise<DatasetInstallResult>
  removeDataset(
    datasetId: string,
    signal?: AbortSignal,
  ): Promise<DatasetInstallResult>
}

export type ToolBatchAction = 'enable' | 'disable'

export type ToolBatchResult = {
  ok: boolean
  action: ToolBatchAction
  requested: number
  succeeded: string[]
  failed: string[]
  summary: string
}

export interface ToolsProvider {
  listTools(options?: {
    enabledOnly?: boolean
    signal?: AbortSignal
  }): Promise<ToolCatalog>
  updateToolEnabled(
    toolId: string,
    enabled: boolean,
    signal?: AbortSignal,
  ): Promise<ToolSummary>
  batchUpdateTools(
    action: ToolBatchAction,
    ids: string[],
    signal?: AbortSignal,
  ): Promise<ToolBatchResult>
}

export interface ModelsProvider {
  listModels(options?: {
    enabledOnly?: boolean
    discover?: boolean
    signal?: AbortSignal
  }): Promise<AgentModel[]>
  createCustomModel?(
    input: CreateAgentModelInput,
    signal?: AbortSignal,
  ): Promise<AgentModel>
  deleteCustomModel?(modelId: string, signal?: AbortSignal): Promise<void>
  updateModelEnabled(
    modelId: string,
    enabled: boolean,
    signal?: AbortSignal,
  ): Promise<AgentModel>
  listModelProfiles(options?: {
    includeCloud?: boolean
    signal?: AbortSignal
  }): Promise<ModelProfile[]>
  createModelProfile(
    input: UpsertModelProfileInput,
    signal?: AbortSignal,
  ): Promise<ModelProfile>
  updateModelProfile(
    profileId: string,
    input: UpsertModelProfileInput,
    signal?: AbortSignal,
  ): Promise<ModelProfile>
  deleteModelProfile(profileId: string, signal?: AbortSignal): Promise<void>
  probeModelProfile(
    profileId: string,
    signal?: AbortSignal,
  ): Promise<ModelProfileProbeResult>
  discoverModelEndpoint?(
    input: DiscoverModelEndpointInput,
    signal?: AbortSignal,
  ): Promise<ModelProfileProbeResult>
}

export type McpServer = {
  id: string
  name: string
  transport: 'stdio' | 'sse' | 'streamable_http'
  command: string | null
  args: string[]
  url: string | null
  enabled: boolean
  catalogId?: string | null
  description?: string | null
  oauthClientId?: string | null
  oauthServerUrl?: string | null
  oauthScopes?: string | null
  headersHelperCommand?: string | null
  headerNames?: string[]
  headersConfigured?: boolean
  /** Write-only on create/update — never returned by the API. */
  headers?: Record<string, string> | null
  createdAt: string
  updatedAt: string
}

export type McpCatalogEntry = {
  id: string
  name: string
  description: string
  url: string
  transport: 'stdio' | 'sse' | 'streamable_http'
  authMode: 'oauth' | 'api_key' | 'api_key_or_oauth'
  preferredAuth: 'oauth' | 'api_key'
  apiKeyEnvVar: string | null
  docsUrl: string | null
  setupUrl: string | null
  integrationKey: string | null
  /** Featured cards (dashboard / onboarding). Non-featured stay in the full MCP list. */
  featured?: boolean
  defaultEnabled: boolean
  configured: boolean
  authMethod: 'oauth' | 'api_key' | null
  enabled: boolean
  serverId: string | null
  connected: boolean
  toolCount?: number | null
  statusMessage?: string | null
}

export type McpToolDetail = {
  name: string
  title?: string | null
  description: string | null
  inputSchema: Record<string, unknown> | null
}

export type ConnectMcpResult = {
  ok: boolean
  authorizeUrl?: string | null
  state?: string | null
  redirectUri?: string | null
  catalogId?: string | null
  serverId?: string | null
  enabled?: boolean | null
  toolCount?: number | null
  message?: string | null
  tools?: string[]
}

export type ValidateMcpResult = {
  ok: boolean
  toolCount: number
  message: string
  tools: string[]
  toolDetails?: McpToolDetail[]
}

export type PtySessionInfo = {
  id: string
  sessionId: string
  title: string
  cwd: string
  cols: number
  rows: number
  pid: number
  status: 'running' | 'exited'
}

export interface McpProvider {
  listMcpServers(signal?: AbortSignal): Promise<McpServer[]>
  listMcpCatalog(signal?: AbortSignal): Promise<McpCatalogEntry[]>
  connectMcpCatalog(
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string },
    signal?: AbortSignal,
  ): Promise<ConnectMcpResult>
  disconnectMcpCatalog(catalogId: string, signal?: AbortSignal): Promise<ConnectMcpResult>
  setMcpCatalogEnabled(
    catalogId: string,
    enabled: boolean,
    signal?: AbortSignal,
  ): Promise<ConnectMcpResult>
  validateMcpCatalog(catalogId: string, signal?: AbortSignal): Promise<ValidateMcpResult>
  validateMcpServer(serverId: string, signal?: AbortSignal): Promise<ValidateMcpResult>
  createMcpServer(
    input: Omit<McpServer, 'id' | 'createdAt' | 'updatedAt'>,
    signal?: AbortSignal,
  ): Promise<McpServer>
  updateMcpServer(
    id: string,
    changes: Partial<Omit<McpServer, 'id' | 'transport' | 'createdAt' | 'updatedAt'>>,
    signal?: AbortSignal,
  ): Promise<McpServer>
  deleteMcpServer(id: string, signal?: AbortSignal): Promise<void>
}

export type WorkspaceFile = {
  path: string
  name: string
  type: 'file' | 'directory'
  size: number | null
  mtime: string | null
}

export type WorkspaceFileContent = {
  path: string
  content: string
  encoding: 'text' | 'base64'
  mimeType: string
  version: string
  size: number
  mtime: string
}

export type FileWriteResult =
  | { ok: true; content: WorkspaceFileContent }
  | { ok: false; conflict: true; current: WorkspaceFileContent }

export type AgentSkill = {
  name: string
  description: string
  tags: string[]
  source: string
  author: string
  version: string | null
  updatedAt: string | null
  iconSrc: string | null
  enabled: boolean
}

export type AgentSkillDetail = AgentSkill & {
  content: string
  directory: string | null
}

export type AgentSkillSource = {
  provider: string
  source: string
  url: string
  description: string
}

export type AgentCatalogSkill = {
  id: string
  slug: string
  name: string
  source: string
  installs: number
  sourceType: string
  installUrl: string | null
  url: string | null
}

export type AgentCatalogSkillFile = {
  path: string
  contents: string
}

export type AgentCatalogSkillDetail = {
  id: string
  source: string
  slug: string
  installs: number
  hash: string | null
  files: AgentCatalogSkillFile[] | null
}

export type AgentCatalogSkillAuditEntry = {
  provider: string
  slug: string
  status: string
  summary: string
  auditedAt: string | null
  riskLevel: string | null
  categories: string[]
}

export type AgentCatalogSkillAudit = {
  id: string
  source: string
  slug: string
  audits: AgentCatalogSkillAuditEntry[]
}

export type AgentSkillBatchAction = 'enable' | 'disable' | 'remove'

export type AgentSkillBatchFailure = {
  name: string
  reason: string
}

export type AgentSkillBatchResult = {
  ok: boolean
  action: AgentSkillBatchAction
  requested: number
  succeeded: string[]
  failed: AgentSkillBatchFailure[]
  summary: string
}

export interface SkillProvider {
  listSkills(signal?: AbortSignal): Promise<AgentSkill[]>
  listSkillSources(signal?: AbortSignal): Promise<AgentSkillSource[]>
  searchSkillCatalog(
    query: string,
    limit?: number,
    signal?: AbortSignal
  ): Promise<AgentCatalogSkill[]>
  getCatalogSkillDetail(
    source: string,
    skill: string,
    signal?: AbortSignal
  ): Promise<AgentCatalogSkillDetail>
  getCatalogSkillAudit(
    source: string,
    skill: string,
    signal?: AbortSignal
  ): Promise<AgentCatalogSkillAudit>
  bulkSkillAction(
    action: AgentSkillBatchAction,
    names: string[],
    signal?: AbortSignal
  ): Promise<AgentSkillBatchResult>
  getSkill(name: string, signal?: AbortSignal): Promise<AgentSkillDetail>
  setSkillEnabled(
    name: string,
    enabled: boolean,
    signal?: AbortSignal
  ): Promise<AgentSkillDetail>
  installSkill(source: string, signal?: AbortSignal): Promise<string[]>
  removeSkill(name: string, signal?: AbortSignal): Promise<void>
  upgradeSkills(signal?: AbortSignal): Promise<string[]>
}

export interface FileProvider {
  listFiles(sessionId: string, signal?: AbortSignal): Promise<WorkspaceFile[]>
  readFile(sessionId: string, path: string, signal?: AbortSignal): Promise<WorkspaceFileContent>
  writeFile(
    sessionId: string,
    input: {
      path: string
      content: string
      encoding?: 'text' | 'base64'
      baseVersion?: string | null
    },
    signal?: AbortSignal,
  ): Promise<FileWriteResult>
  uploadFile(
    sessionId: string,
    file: File,
    relativeDirectory?: string,
    signal?: AbortSignal,
  ): Promise<WorkspaceFileContent>
  createFolder(sessionId: string, path: string, signal?: AbortSignal): Promise<void>
  moveFile(
    sessionId: string,
    sourcePath: string,
    targetPath: string,
    signal?: AbortSignal,
  ): Promise<void>
  deleteFile(
    sessionId: string,
    path: string,
    recursive?: boolean,
    signal?: AbortSignal,
  ): Promise<void>
  downloadUrl(sessionId: string, path: string): string
}

export interface AgentClient {
  health(signal?: AbortSignal): Promise<BackendHealth>
  getServerStatus?(signal?: AbortSignal): Promise<ServerStatusReport>
  stopServer?(signal?: AbortSignal): Promise<ServerLifecycleResult>
  restartServer?(signal?: AbortSignal): Promise<ServerLifecycleResult>
  clearRuntimeCache?(signal?: AbortSignal): Promise<ServerCacheInfo>
  runDoctor?(
    signalOrOptions?:
      | AbortSignal
      | { scope?: 'full' | 'core'; signal?: AbortSignal },
  ): Promise<DoctorReport>
  getStorage?(signal?: AbortSignal): Promise<StorageReport>
  getEnvironment?(signal?: AbortSignal): Promise<EnvironmentReport>
  installEnvironmentPackage?(
    name: string,
    options?: { allowUnlisted?: boolean; signal?: AbortSignal },
  ): Promise<EnvironmentPackageMutationResult>
  uninstallEnvironmentPackage?(
    name: string,
    signal?: AbortSignal,
  ): Promise<EnvironmentPackageMutationResult>
  downloadDiagnostics?(
    uiDiagnostics?: Record<string, unknown> | null,
    signal?: AbortSignal,
  ): Promise<{ blob: Blob; filename: string }>
  listSessions(
    options?: { projectId?: string | null; signal?: AbortSignal },
  ): Promise<AgentSession[]>
  listProjects?(signal?: AbortSignal): Promise<AgentProject[]>
  listSpecialists?(signal?: AbortSignal): Promise<Specialist[]>
  getSpecialist?(specialistId: string, signal?: AbortSignal): Promise<Specialist>
  createSpecialist?(
    input: {
      name: string
      slug?: string | null
      description?: string | null
      instructions?: string | null
      color?: string
      icon?: string
      skillNames?: string[]
      toolNames?: string[]
      mcpServerIds?: string[]
      mcpCatalogIds?: string[]
      enabled?: boolean
    },
    signal?: AbortSignal,
  ): Promise<Specialist>
  updateSpecialist?(
    specialistId: string,
    input: {
      name?: string
      slug?: string | null
      description?: string | null
      instructions?: string | null
      color?: string
      icon?: string
      skillNames?: string[]
      toolNames?: string[]
      mcpServerIds?: string[]
      mcpCatalogIds?: string[]
      enabled?: boolean
    },
    signal?: AbortSignal,
  ): Promise<Specialist>
  getPromptBudget?(
    options?: {
      specialistId?: string | null
      projectId?: string | null
      sampleQuery?: string | null
    },
    signal?: AbortSignal,
  ): Promise<PromptBudgetResponse>
  deleteSpecialist?(specialistId: string, signal?: AbortSignal): Promise<void>
  createProject?(
    input: {
      name: string
      description?: string | null
      agentContext?: string | null
      pinned?: boolean
    },
    signal?: AbortSignal,
  ): Promise<AgentProject>
  updateProject?(
    projectId: string,
    input: {
      name?: string
      description?: string | null
      agentContext?: string | null
      pinned?: boolean
    },
    signal?: AbortSignal,
  ): Promise<AgentProject>
  deleteProject?(projectId: string, signal?: AbortSignal): Promise<void>
  searchSessions(query: string, signal?: AbortSignal): Promise<AgentSession[]>
  createSession(
    input: {
      title?: string
      workspacePath?: string | null
      projectId?: string | null
      specialistId?: string | null
      sandboxBackend?: 'builtin' | 'modal' | null
    },
    signal?: AbortSignal,
  ): Promise<AgentSession>
  updateSession(
    sessionId: string,
    input: {
      title?: string
      organizeLabel?: 'pinned' | 'archive' | null
      projectId?: string | null
      specialistId?: string | null
      sandboxBackend?: 'builtin' | 'modal' | null
    },
    signal?: AbortSignal,
  ): Promise<AgentSession>
  getSessionSandbox?(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionSandboxStatus>
  sandboxStreamUrl?(sessionId: string): string
  startSessionSandbox?(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionSandboxStatus>
  stopSessionSandbox?(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionSandboxStatus>
  restartSessionSandbox?(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<SessionSandboxStatus>
  autoTitleSession(
    sessionId: string,
    input?: { force?: boolean },
    signal?: AbortSignal,
  ): Promise<AgentSession>
  deleteSession(sessionId: string, signal?: AbortSignal): Promise<void>
  listMessages(sessionId: string, signal?: AbortSignal): Promise<AgentMessage[]>
  listEventHistory(sessionId: string, signal?: AbortSignal): Promise<AgentEvent[]>
  setMessageFeedback(
    sessionId: string,
    messageId: string,
    reaction: 'up' | 'down' | null,
    signal?: AbortSignal,
  ): Promise<void>
  sendMessage(sessionId: string, content: string, signal?: AbortSignal): Promise<{ runId: string }>
  interrupt(sessionId: string, signal?: AbortSignal): Promise<boolean>
  streamEvents(
    sessionId: string,
    options: {
      afterSequence?: number
      signal?: AbortSignal
      onEvent: (event: AgentEvent) => void
    },
  ): Promise<void>
}
