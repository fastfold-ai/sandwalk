import type {
  AccountSummary,
  AgentClient,
  AgentEvent,
  AgentMessage,
  AgentModel,
  AgentProject,
  AgentSession,
  UsageOverview,
  WidgetLayout,
  ProjectFolderFile,
  ProjectFolderListing,
  LibraryItem,
  LibraryItemList,
  LibraryKind,
  Specialist,
  CookbookSummary,
  DistillSessionResponse,
  GraphBranch,
  GraphEdge,
  GraphNode,
  GraphSnapshot,
  MemoryEntry,
  MemoryEntryList,
  MemoryOverview,
  MemorySettings,
  OmnigraphEngineStatus,
  PendingMemoryWrite,
  WikiPageDetail,
  WikiPageSummary,
  UseLibraryInChatResult,
  AgentCatalogLeaderboard,
  AgentCatalogLeaderboardView,
  AgentCatalogSkill,
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentSkill,
  ChatGPTAuthStart,
  ChatGPTAuthStatus,
  ExternalAgentKind,
  ExternalAgentsResponse,
  ExternalLaunchResult,
  HandoffResult,
  AgentSkillBatchAction,
  AgentSkillBatchResult,
  AgentSkillDepsInstallResult,
  AgentSkillDepsStatus,
  AgentSkillDetail,
  AgentSkillSource,
  HitlDecision,
  BackendHealth,
  CreateAgentModelInput,
  ModelPreferences,
  ToggleModelFavoriteInput,
  ToggleModelFavoriteResult,
  DatasetSummary,
  DatasetInstallResult,
  DoctorReport,
  EnvironmentPackageMutationResult,
  EnvironmentReport,
  FileProvider,
  FileWriteResult,
  IntegrationProvider,
  IntegrationSummary,
  IntegrationSetupResult,
  McpProvider,
  McpServer,
  McpCatalogEntry,
  McpJsonConfig,
  McpJsonDocument,
  ConnectMcpResult,
  ValidateMcpResult,
  McpToolDetail,
  ModelProfile,
  ModelProfileProbeResult,
  DiscoverModelEndpointInput,
  OnboardingSettings,
  ServerCacheInfo,
  ServerLifecycleResult,
  ServerStatusReport,
  StorageReport,
  ModelsProvider,
  RunCapacity,
  RuntimeSettings,
  SandboxProbeReport,
  SandboxSettings,
  SessionConnectorMute,
  SessionSandboxStatus,
  Site,
  SitePreviewTicket,
  SiteProvider,
  SettingsProvider,
  SlackAllowedUser,
  SlackConnectorStatus,
  SlackDirectory,
  SlackManifest,
  SlackParkedMessage,
  SlackSubscription,
  SlackWorkspace,
  SkillProvider,
  ToolBatchAction,
  ToolBatchResult,
  ToolCatalog,
  ToolSummary,
  UpsertModelProfileInput,
  PromptBudgetResponse,
  WorkspaceFile,
  WorkspaceFileContent,
  PtySessionInfo,
  TerminalSession,
  WorkspaceItem
} from '@sandwalk/agent-ui-core'

export type LocalAgentClientOptions = {
  baseUrl: string
  apiKey?: string
  /** Session cookie value from /auth/login (Tauri cannot store cross-origin Set-Cookie). */
  sessionToken?: string
}

const SESSION_COOKIE = 'sandwalk_session'

const sessionTokensByUrl = new Map<string, string>()

const LOCAL_API_BASE = 'http://127.0.0.1:8787'
const LOCAL_UI_DEV_ORIGIN =
  /^(https?:\/\/((127\.0\.0\.1|localhost):(1420|5173|8969)|tauri\.localhost)|tauri:)/i

function normalizeClientBaseUrl(url: string): string {
  const trimmed = url.replace(/\/+$/, '')
  if (!trimmed || LOCAL_UI_DEV_ORIGIN.test(trimmed)) {
    return LOCAL_API_BASE
  }
  return trimmed
}

function isHtmlBody(text: string) {
  return text.trimStart().startsWith('<')
}

function shouldRetryLocalApi(url: string) {
  if (url.startsWith(`${LOCAL_API_BASE}/`)) return false
  if (typeof window === 'undefined') return LOCAL_UI_DEV_ORIGIN.test(url)
  const port = window.location.port
  return port === '1420' || port === '8969' || port === '5173'
}

export function rememberSessionToken(baseUrl: string, token: string) {
  const key = normalizeClientBaseUrl(baseUrl)
  const trimmed = token.trim()
  if (!key || !trimmed) return
  sessionTokensByUrl.set(key, trimmed)
}

export function clearSessionToken(baseUrl: string) {
  sessionTokensByUrl.delete(normalizeClientBaseUrl(baseUrl))
}

export function readSessionToken(baseUrl: string): string | undefined {
  return sessionTokensByUrl.get(normalizeClientBaseUrl(baseUrl))
}

function parseApiJson<T>(text: string, request: string): T {
  const trimmed = text.trimStart()
  if (trimmed.startsWith('<')) {
    throw new Error(
      `FastFold Agent API returned a web page instead of JSON [${request}]. Restart the Sandwalk agent.`
    )
  }
  try {
    return JSON.parse(text) as T
  } catch (cause) {
    const hint = cause instanceof Error ? cause.message : 'invalid JSON'
    throw new Error(
      `FastFold Agent API returned invalid JSON (${hint}) [${request}]`
    )
  }
}

export type BenchSuiteCard = {
  id: string
  title: string
  description?: string
  lane: 'intelligence' | 'skills'
  runner: 'completion' | 'agent'
  packId?: string | null
  matrix?: string | null
  questionCount: number
  sampleSizes: number[]
  defaultSampleSize?: number | null
  available: boolean
  unavailableReason?: string | null
  author?: string | null
  authorAvatar?: string | null
  codeExec?: boolean
  installable?: boolean
  requiresHfToken?: boolean
  hfTokenConfigured?: boolean
  installing?: boolean
  installError?: string | null
  /** Human progress while installing, e.g. ``file 2/6 · 12.4 MB``. */
  installProgress?: string | null
  installBytesDone?: number | null
  installBytesTotal?: number | null
  /** True when a downloadable dataset is cached on disk (Remove is available). */
  installed?: boolean
  /** Bytes this suite occupies in the local bench cache. */
  installedBytes?: number | null
  /** Questions actually cached locally (may differ from the declared corpus). */
  installedCount?: number | null
  /** Set when the fast parquet download needs a reader that is not installed. */
  missingDependency?: string | null
  requiredSkills?: string[]
  requiredMcps?: string[]
  missingSkills?: string[]
  missingMcps?: string[]
}

export type BenchSuiteCatalog = {
  suites: BenchSuiteCard[]
  /** Total bytes used by every cached bench dataset. */
  cacheBytes: number
  cachePath?: string | null
}

export type BenchUninstallResult = {
  ok: boolean
  suiteId: string
  summary?: string
  freedBytes?: number
  removed?: string[]
}

export type BenchInstallResult = {
  ok: boolean
  suiteId: string
  path?: string | null
  summary?: string
  needsHfToken?: boolean
  status?: 'installing' | 'done' | 'error'
}

export type BenchProgress = {
  type?: string
  phase?: string
  modelId?: string
  benchmark?: string
  message?: string
  current?: number
  total?: number
  benchCurrent?: number
  benchTotal?: number
  inFlight?: number
  runId?: string | null
}

export type BenchQueueItem = {
  runId: string
  modelId: string
  suites: string[]
  sampleSizes?: Array<number | null>
  status?: 'queued' | 'running' | 'paused'
  lastProgress?: BenchProgress | null
  provider?: string | null
  startedAt?: string | null
  elapsedS?: number | null
}

export type BenchActiveStatus = {
  running: boolean
  phase: string
  currentModel?: string | null
  currentRunId?: string | null
  lastProgress?: BenchProgress | null
  queue: BenchQueueItem[]
  inflight?: BenchQueueItem[]
  paused?: BenchQueueItem[]
  parallelRuns?: number
  resumableRunId?: string | null
  projectId?: string | null
}

export type BenchResultSummary = {
  runId: string
  modelId: string
  benchmark: string
  accuracy: number
  correct: number
  answered?: number | null
  total: number
  timeS: number
  thinkingUsed?: boolean
  projectId?: string | null
  createdAt?: string | null
  status?: string | null
  reasoningEffort?: string | null
  reasoningFast?: boolean | null
  name?: string | null
  provider?: string | null
  lifetimeTokens?: number | null
  resumable?: boolean
  failedCount?: number
}

export type BenchResultPage = {
  data: BenchResultSummary[]
  nextCursor?: string | null
  total: number
  providers: string[]
}

export type ListBenchResultsOptions = {
  q?: string
  suite?: string
  status?: string
  provider?: string
  sort?: 'date_desc' | 'date_asc' | 'usage_desc' | 'usage_asc'
  cursor?: string
  limit?: number
  signal?: AbortSignal
}

function num(raw: Record<string, unknown>, camel: string, snake: string): number {
  const value = raw[camel] ?? raw[snake]
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function normalizeUsageOverview(raw: Record<string, unknown>): UsageOverview {
  const daysRaw = raw.days
  const modelsRaw = raw.topModels ?? raw.top_models
  const days = Array.isArray(daysRaw)
    ? daysRaw.flatMap(item => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) return []
        const row = item as Record<string, unknown>
        return [
          {
            day: String(row.day || ''),
            tokens: num(row, 'tokens', 'tokens'),
            inputTokens: num(row, 'inputTokens', 'input_tokens'),
            outputTokens: num(row, 'outputTokens', 'output_tokens'),
            cacheReadTokens: num(row, 'cacheReadTokens', 'cache_read_tokens'),
            cliTokens: num(row, 'cliTokens', 'cli_tokens'),
            uiTokens: num(row, 'uiTokens', 'ui_tokens'),
            slackTokens: num(row, 'slackTokens', 'slack_tokens'),
            unknownTokens: num(row, 'unknownTokens', 'unknown_tokens'),
            runs: num(row, 'runs', 'runs')
          }
        ]
      })
    : []
  const topModels = Array.isArray(modelsRaw)
    ? modelsRaw.flatMap(item => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) return []
        const row = item as Record<string, unknown>
        return [
          {
            modelId: String(row.modelId ?? row.model_id ?? 'unknown'),
            provider: String(row.provider ?? 'unknown'),
            tokens: num(row, 'tokens', 'tokens'),
            inputTokens: num(row, 'inputTokens', 'input_tokens'),
            outputTokens: num(row, 'outputTokens', 'output_tokens'),
            runs: num(row, 'runs', 'runs'),
            messages: num(row, 'messages', 'messages')
          }
        ]
      })
    : []
  const modelDaysRaw = raw.modelDays ?? raw.model_days
  const modelDays = Array.isArray(modelDaysRaw)
    ? modelDaysRaw.flatMap(item => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) return []
        const row = item as Record<string, unknown>
        return [
          {
            day: String(row.day || ''),
            modelId: String(row.modelId ?? row.model_id ?? 'Other'),
            provider: String(row.provider ?? 'unknown'),
            tokens: num(row, 'tokens', 'tokens')
          }
        ]
      })
    : []
  const chartModelsRaw = raw.chartModels ?? raw.chart_models
  const chartModels = Array.isArray(chartModelsRaw)
    ? chartModelsRaw.flatMap(item => {
        if (typeof item === 'string' && item) {
          return [{ modelId: item, provider: 'unknown' }]
        }
        if (!item || typeof item !== 'object' || Array.isArray(item)) return []
        const row = item as Record<string, unknown>
        const modelId = String(row.modelId ?? row.model_id ?? '').trim()
        if (!modelId) return []
        return [
          {
            modelId,
            provider: String(row.provider ?? 'unknown')
          }
        ]
      })
    : []
  return {
    lifetimeTokens: num(raw, 'lifetimeTokens', 'lifetime_tokens'),
    inputTokens: num(raw, 'inputTokens', 'input_tokens'),
    outputTokens: num(raw, 'outputTokens', 'output_tokens'),
    cacheReadTokens: num(raw, 'cacheReadTokens', 'cache_read_tokens'),
    peakDayTokens: num(raw, 'peakDayTokens', 'peak_day_tokens'),
    peakDay:
      typeof (raw.peakDay ?? raw.peak_day) === 'string'
        ? String(raw.peakDay ?? raw.peak_day)
        : null,
    modelsUsed: num(raw, 'modelsUsed', 'models_used'),
    runs: num(raw, 'runs', 'runs'),
    sessions: num(raw, 'sessions', 'sessions'),
    messages: num(raw, 'messages', 'messages'),
    avgTokensPerSession: num(raw, 'avgTokensPerSession', 'avg_tokens_per_session'),
    longestAgentSeconds: num(
      raw,
      'longestAgentSeconds',
      'longest_agent_seconds'
    ),
    longestStreakDays: num(raw, 'longestStreakDays', 'longest_streak_days'),
    currentStreakDays: num(raw, 'currentStreakDays', 'current_streak_days'),
    cliTokens: num(raw, 'cliTokens', 'cli_tokens'),
    uiTokens: num(raw, 'uiTokens', 'ui_tokens'),
    slackTokens: num(raw, 'slackTokens', 'slack_tokens'),
    unknownTokens: num(raw, 'unknownTokens', 'unknown_tokens'),
    cliShare: num(raw, 'cliShare', 'cli_share'),
    uiShare: num(raw, 'uiShare', 'ui_share'),
    days,
    topModels,
    modelDays,
    chartModels,
    backfilled: Boolean(raw.backfilled)
  }
}

export type LlamaCatalogModel = {
  id: string
  name: string
  brand: string
  repo: string
  quant: string | null
  size: string | null
  vision?: boolean
  installed: boolean
}

export type LlamaInstalledModel = {
  id: string
  context: number | null
  size: string | null
  vision: boolean
  state: string
  error?: string | null
}

export type LlamaCatalog = {
  installed: LlamaInstalledModel[]
  recommended: LlamaCatalogModel[]
}

export type LlamaRuntimeDebug = {
  command?: string
  exitCode?: number | null
  port?: number
  binary?: string | null
  searched?: string[]
  log?: string
}

export type LlamaRuntimeStatus = {
  baseUrl: string
  installed: boolean
  running: boolean
  version: string | null
  models: string[]
  phase: string
  detail: string
  /** Recent llama CLI lines, newest last. Present while a download is running. */
  log?: string[]
  /** The download currently running, so the row can stay pinned if the window closes. */
  install?: { repo: string; quant: string | null; spec: string } | null
  debug?: LlamaRuntimeDebug
}

export type ServiceProcess = {
  id: string
  name: string
  status: 'running' | 'stopped'
  pid: number | null
  port: number | null
  rssBytes: number | null
  cpuPercent: number | null
  command: string | null
  detail: string | null
}

export type ServicesReport = {
  processes: ServiceProcess[]
  logs: { name: string; tail: string }[]
  checkedAt: string
}

export class LocalAgentClient
  implements
    AgentClient,
    FileProvider,
    SkillProvider,
    IntegrationProvider,
    SettingsProvider,
    ModelsProvider,
    McpProvider,
    SiteProvider
{
  readonly baseUrl: string
  readonly apiKey?: string
  readonly sessionToken?: string

  constructor(options: LocalAgentClientOptions) {
    this.baseUrl = normalizeClientBaseUrl(options.baseUrl)
    this.apiKey = options.apiKey
    const token = options.sessionToken?.trim()
    this.sessionToken = token || readSessionToken(this.baseUrl)
    if (token) rememberSessionToken(this.baseUrl, token)
  }

  private headers(extra?: HeadersInit): Headers {
    const headers = new Headers(extra)
    headers.set('accept', 'application/json')
    headers.set('x-sandwalk-client', 'ui')
    if (this.apiKey) headers.set('authorization', `Bearer ${this.apiKey}`)
    const session =
      this.sessionToken?.trim() || readSessionToken(this.baseUrl) || ''
    if (session) headers.set('cookie', `${SESSION_COOKIE}=${session}`)
    return headers
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = this.headers(init.headers)
    const fetchOnce = (base: string) =>
      fetch(`${base}/v1${path}`, {
        ...init,
        credentials: 'include',
        headers
      })
    const firstUrl = `${this.baseUrl}/v1${path}`
    let url = firstUrl
    let response = await fetchOnce(this.baseUrl)
    let text = response.status === 204 ? '' : await response.text()
    if (isHtmlBody(text) && shouldRetryLocalApi(url)) {
      url = `${LOCAL_API_BASE}/v1${path}`
      response = await fetchOnce(LOCAL_API_BASE)
      text = response.status === 204 ? '' : await response.text()
    }
    if (!response.ok) {
      throw new Error(
        `FastFold Agent API ${response.status}: ${
          text || response.statusText
        } [${init.method || 'GET'} ${url}]`
      )
    }
    if (response.status === 204 || !text) {
      return undefined as T
    }
    return parseApiJson<T>(text, `${init.method || 'GET'} ${url}`)
  }

  private normalizeValidateMcp(
    raw: Record<string, unknown>
  ): ValidateMcpResult {
    const toolsRaw = raw.tools
    const tools = Array.isArray(toolsRaw)
      ? toolsRaw.map(item => String(item))
      : []
    const detailsRaw = raw.toolDetails ?? raw.tool_details
    const toolDetails: McpToolDetail[] = []
    if (Array.isArray(detailsRaw)) {
      for (const item of detailsRaw) {
        if (!item || typeof item !== 'object' || Array.isArray(item)) continue
        const row = item as Record<string, unknown>
        const name = String(row.name || '').trim()
        if (!name) continue
        const schema = row.inputSchema ?? row.input_schema
        toolDetails.push({
          name,
          title:
            typeof row.title === 'string' && row.title.trim()
              ? row.title.trim()
              : null,
          description:
            typeof row.description === 'string' && row.description.trim()
              ? row.description.trim()
              : null,
          inputSchema:
            schema && typeof schema === 'object' && !Array.isArray(schema)
              ? (schema as Record<string, unknown>)
              : null
        })
      }
    }
    return {
      ok: Boolean(raw.ok),
      toolCount: Number(raw.toolCount ?? raw.tool_count ?? tools.length) || 0,
      message: String(raw.message || ''),
      tools,
      toolDetails
    }
  }

  authStatus(signal?: AbortSignal): Promise<{
    authEnabled: boolean
    apiKeyConfigured: boolean
    authenticated?: boolean
  }> {
    return this.request('/auth/status', { signal })
  }

  // --- Sign in with ChatGPT (subscription-backed OpenAI) -------------------

  /**
   * Current ChatGPT connection. Pass the ``state`` from ``startChatGPTLogin``
   * to also learn whether that pending browser sign-in finished; a failed
   * attempt rejects with the server's error message.
   */
  getChatGPTAuthStatus(
    options?: { state?: string; signal?: AbortSignal }
  ): Promise<ChatGPTAuthStatus> {
    const query = options?.state
      ? `?state=${encodeURIComponent(options.state)}`
      : ''
    return this.request<ChatGPTAuthStatus>(`/auth/chatgpt/status${query}`, {
      signal: options?.signal
    })
  }

  /** Begin the browser sign-in. Open ``url`` externally, then poll status. */
  startChatGPTLogin(signal?: AbortSignal): Promise<ChatGPTAuthStart> {
    return this.request<ChatGPTAuthStart>('/auth/chatgpt/start', {
      method: 'POST',
      signal
    })
  }

  /** Revoke the refresh token at OpenAI and forget the local sign-in. */
  logoutChatGPT(signal?: AbortSignal): Promise<ChatGPTAuthStatus> {
    return this.request<ChatGPTAuthStatus>('/auth/chatgpt/logout', {
      method: 'POST',
      signal
    })
  }

  // --- Claude Code / Codex / OpenCode / fx interop ------------------------

  /** Installed agent CLIs plus their recent sessions (optionally for one folder). */
  listExternalAgents(options?: {
    cwd?: string | null
    kind?: ExternalAgentKind | null
    limit?: number
    /** `false` skips the session scan and only reports installed CLIs. */
    sessions?: boolean
    signal?: AbortSignal
  }): Promise<ExternalAgentsResponse> {
    const params = new URLSearchParams()
    if (options?.cwd) params.set('cwd', options.cwd)
    if (options?.kind) params.set('kind', options.kind)
    if (options?.limit) params.set('limit', String(options.limit))
    if (options?.sessions === false) params.set('sessions', 'false')
    const query = params.toString()
    return this.request<ExternalAgentsResponse>(
      `/external-agents${query ? `?${query}` : ''}`,
      { signal: options?.signal }
    )
  }

  /** Convert another CLI's session into a Sandwalk chat (history only). */
  importExternalSession(
    input: {
      kind: ExternalAgentKind
      sessionId: string
      projectId?: string | null
      workspacePath?: string | null
    },
    signal?: AbortSignal
  ): Promise<AgentSession> {
    return this.request<AgentSession>('/external-agents/import', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(input),
      signal
    })
  }

  /** Open a terminal running the agent CLI in a folder. */
  launchExternalAgent(
    input: {
      kind: ExternalAgentKind
      workspacePath?: string | null
      projectId?: string | null
      originChatId?: string | null
      prompt?: string | null
      resumeId?: string | null
      title?: string | null
    },
    signal?: AbortSignal
  ): Promise<ExternalLaunchResult> {
    return this.request<ExternalLaunchResult>('/external-agents/launch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(input),
      signal
    })
  }

  /** Hand a Sandwalk chat to another CLI: handoff file, optional native session, optional launch. */
  handoffSession(
    sessionId: string,
    input: {
      kind: ExternalAgentKind
      launch?: boolean
      native?: boolean
      projectId?: string | null
    },
    signal?: AbortSignal
  ): Promise<HandoffResult> {
    return this.request<HandoffResult>(
      `/sessions/${encodeURIComponent(sessionId)}/handoff`,
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(input),
        signal
      }
    )
  }

  async login(
    apiKey: string,
    options?: { remember?: boolean; signal?: AbortSignal }
  ): Promise<{ ok: boolean; authEnabled?: boolean; sessionToken?: string }> {
    const result = await this.request<{
      ok: boolean
      authEnabled?: boolean
      sessionToken?: string
    }>('/auth/login', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        apiKey,
        remember: Boolean(options?.remember)
      }),
      signal: options?.signal
    })
    const token = result?.sessionToken?.trim()
    if (token) rememberSessionToken(this.baseUrl, token)
    return result
  }

  async logout(signal?: AbortSignal): Promise<{ ok: boolean }> {
    try {
      return await this.request('/auth/logout', { method: 'POST', signal })
    } finally {
      clearSessionToken(this.baseUrl)
    }
  }

  health(signal?: AbortSignal): Promise<BackendHealth> {
    return this.request<BackendHealth>('/health', { signal })
  }

  getServerStatus(signal?: AbortSignal): Promise<ServerStatusReport> {
    return this.request<ServerStatusReport>('/status', { signal })
  }

  stopServer(signal?: AbortSignal): Promise<ServerLifecycleResult> {
    return this.request<ServerLifecycleResult>('/server/stop', {
      method: 'POST',
      signal
    })
  }

  restartServer(signal?: AbortSignal): Promise<ServerLifecycleResult> {
    return this.request<ServerLifecycleResult>('/server/restart', {
      method: 'POST',
      signal
    })
  }

  clearRuntimeCache(signal?: AbortSignal): Promise<ServerCacheInfo> {
    return this.request<ServerCacheInfo>('/storage/cache/clear', {
      method: 'POST',
      signal
    })
  }

  async listBenchSuites(signal?: AbortSignal): Promise<BenchSuiteCard[]> {
    const result = await this.request<{ data: BenchSuiteCard[] }>('/bench/packs', {
      signal
    })
    return result.data
  }

  /** Suite cards plus local dataset cache totals. */
  async getBenchCatalog(signal?: AbortSignal): Promise<BenchSuiteCatalog> {
    const result = await this.request<{
      data: BenchSuiteCard[]
      cacheBytes?: number
      cachePath?: string | null
    }>('/bench/packs', { signal })
    return {
      suites: result.data,
      cacheBytes: result.cacheBytes ?? 0,
      cachePath: result.cachePath ?? null
    }
  }

  installBenchSuite(
    suiteId: string,
    signal?: AbortSignal
  ): Promise<BenchInstallResult> {
    return this.request<BenchInstallResult>(
      `/bench/packs/${encodeURIComponent(suiteId)}/install`,
      { method: 'POST', signal }
    )
  }

  /** Delete a suite's cached dataset to reclaim disk space. */
  uninstallBenchSuite(
    suiteId: string,
    signal?: AbortSignal
  ): Promise<BenchUninstallResult> {
    return this.request<BenchUninstallResult>(
      `/bench/packs/${encodeURIComponent(suiteId)}/install`,
      { method: 'DELETE', signal }
    )
  }

  spawnBench(
    input: {
      suites: Array<{ suiteId: string; sampleSize?: number | null }>
      model?: string | null
      models?: string[]
      provider?: string | null
      projectName?: string | null
      specialistId?: string | null
      thinking?: boolean
      dryRun?: boolean
      concurrency?: number
      parallelRuns?: number
      cleanupSessions?: boolean
      clientSurface?: 'cli' | 'ui'
    },
    signal?: AbortSignal
  ): Promise<{ runIds: string[]; queued: number }> {
    return this.request('/bench/spawn', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        ...input,
        clientSurface: input.clientSurface ?? 'ui'
      }),
      signal
    })
  }

  getBenchActive(signal?: AbortSignal): Promise<BenchActiveStatus> {
    return this.request<BenchActiveStatus>('/bench/runs/active', { signal })
  }

  async listBenchResults(
    opts?: ListBenchResultsOptions
  ): Promise<BenchResultPage> {
    const params = new URLSearchParams()
    if (opts?.q) params.set('q', opts.q)
    if (opts?.suite) params.set('suite', opts.suite)
    if (opts?.status) params.set('status', opts.status)
    if (opts?.provider) params.set('provider', opts.provider)
    if (opts?.sort) params.set('sort', opts.sort)
    if (opts?.cursor) params.set('cursor', opts.cursor)
    if (opts?.limit) params.set('limit', String(opts.limit))
    const query = params.toString()
    const result = await this.request<{
      data: BenchResultSummary[]
      nextCursor?: string | null
      total?: number
      providers?: string[]
    }>(`/bench/runs${query ? `?${query}` : ''}`, { signal: opts?.signal })
    return {
      data: (result.data || []).map(row => {
        const raw = row as BenchResultSummary & {
          lifetime_tokens?: number
          failed_count?: number
        }
        const tokens = Number(raw.lifetimeTokens ?? raw.lifetime_tokens)
        const failed = Number(raw.failedCount ?? raw.failed_count)
        return {
          ...raw,
          lifetimeTokens: Number.isFinite(tokens) ? tokens : null,
          failedCount: Number.isFinite(failed) ? failed : 0
        }
      }),
      nextCursor: result.nextCursor ?? null,
      total: Number(result.total) || (result.data || []).length,
      providers: Array.isArray(result.providers) ? result.providers : []
    }
  }

  patchBenchRun(
    runId: string,
    body: { name: string },
    signal?: AbortSignal
  ): Promise<{ ok: boolean; runId?: string; name?: string | null }> {
    return this.request(`/bench/runs/${encodeURIComponent(runId)}`, {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      signal
    })
  }

  getBenchResult(
    runId: string,
    signal?: AbortSignal
  ): Promise<Record<string, unknown>> {
    return this.request(`/bench/runs/${encodeURIComponent(runId)}`, { signal })
  }

  cancelBenchRun(runId: string, signal?: AbortSignal): Promise<{ ok: boolean }> {
    return this.request(`/bench/runs/${encodeURIComponent(runId)}/cancel`, {
      method: 'POST',
      signal
    })
  }

  pauseBenchRun(runId: string, signal?: AbortSignal): Promise<{ ok: boolean }> {
    return this.request(`/bench/runs/${encodeURIComponent(runId)}/pause`, {
      method: 'POST',
      signal
    })
  }

  resumeBenchRun(runId: string, signal?: AbortSignal): Promise<{ ok: boolean }> {
    return this.request(`/bench/runs/${encodeURIComponent(runId)}/resume`, {
      method: 'POST',
      signal
    })
  }

  retryFailedBenchRun(
    runId: string,
    signalOrIds?: AbortSignal | { questionIds?: string[]; signal?: AbortSignal }
  ): Promise<{ ok: boolean }> {
    const opts =
      signalOrIds && typeof signalOrIds === 'object' && !('aborted' in signalOrIds)
        ? signalOrIds
        : { signal: signalOrIds as AbortSignal | undefined }
    const ids = opts.questionIds?.filter(Boolean) || []
    return this.request(
      `/bench/runs/${encodeURIComponent(runId)}/retry-failed`,
      {
        method: 'POST',
        headers: ids.length ? { 'content-type': 'application/json' } : undefined,
        body: ids.length ? JSON.stringify({ question_ids: ids }) : undefined,
        signal: opts.signal
      }
    )
  }

  deleteBenchResult(
    runId: string,
    signal?: AbortSignal
  ): Promise<{ ok: boolean }> {
    return this.request(`/bench/runs/${encodeURIComponent(runId)}`, {
      method: 'DELETE',
      signal
    })
  }

  resetBenchResults(
    signal?: AbortSignal
  ): Promise<{ ok: boolean; cleared: number; sessionsDeleted?: number }> {
    return this.request('/bench/results/reset', { method: 'POST', signal })
  }

  async downloadBenchExport(
    runId: string,
    signal?: AbortSignal
  ): Promise<{ blob: Blob; filename: string }> {
    const res = await fetch(
      `${this.baseUrl}/v1/bench/runs/${encodeURIComponent(runId)}/export`,
      {
        credentials: 'include',
        headers: this.apiKey
          ? { Authorization: `Bearer ${this.apiKey}` }
          : undefined,
        signal
      }
    )
    if (!res.ok) {
      throw new Error(`Export failed (${res.status})`)
    }
    const blob = await res.blob()
    const cd = res.headers.get('content-disposition') || ''
    const utf = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(cd)
    const quoted = /filename="([^"]+)"/i.exec(cd)
    const plain = /filename=([^;]+)/i.exec(cd)
    const raw = utf?.[1] || quoted?.[1] || plain?.[1] || `${runId}.json`
    let filename = raw.trim().replace(/^["']|["']$/g, '')
    try {
      filename = decodeURIComponent(filename)
    } catch {
      /* keep raw */
    }
    return { blob, filename }
  }

  runDoctor(
    signalOrOptions?:
      | AbortSignal
      | { scope?: 'full' | 'core'; signal?: AbortSignal },
    maybeSignal?: AbortSignal
  ): Promise<DoctorReport> {
    let scope: 'full' | 'core' = 'full'
    let signal: AbortSignal | undefined
    if (
      signalOrOptions &&
      typeof signalOrOptions === 'object' &&
      !('aborted' in signalOrOptions)
    ) {
      scope = signalOrOptions.scope === 'core' ? 'core' : 'full'
      signal = signalOrOptions.signal ?? maybeSignal
    } else {
      signal = (signalOrOptions as AbortSignal | undefined) ?? maybeSignal
    }
    const query = scope === 'core' ? '?scope=core' : ''
    return this.request<DoctorReport>(`/doctor${query}`, { signal })
  }

  getStorage(signal?: AbortSignal): Promise<StorageReport> {
    return this.request<StorageReport>('/storage', { signal })
  }

  getEnvironment(signal?: AbortSignal): Promise<EnvironmentReport> {
    return this.request<EnvironmentReport>('/environment', { signal })
  }

  getServices(signal?: AbortSignal): Promise<ServicesReport> {
    return this.request<ServicesReport>('/services', { signal })
  }

  installEnvironmentPackage(
    name: string,
    options?: { allowUnlisted?: boolean; signal?: AbortSignal }
  ): Promise<EnvironmentPackageMutationResult> {
    return this.request<EnvironmentPackageMutationResult>(
      '/environment/packages/install',
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          name,
          allowUnlisted: Boolean(options?.allowUnlisted)
        }),
        signal: options?.signal
      }
    )
  }

  uninstallEnvironmentPackage(
    name: string,
    signal?: AbortSignal
  ): Promise<EnvironmentPackageMutationResult> {
    return this.request<EnvironmentPackageMutationResult>(
      '/environment/packages/uninstall',
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name }),
        signal
      }
    )
  }

  async downloadDiagnostics(
    uiDiagnostics?: Record<string, unknown> | null,
    signal?: AbortSignal
  ): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch(`${this.baseUrl}/v1/doctor/diagnostics`, {
      method: 'POST',
      credentials: 'include',
      headers: this.headers({ 'content-type': 'application/json' }),
      body: JSON.stringify({ uiDiagnostics: uiDiagnostics ?? null }),
      signal
    })
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(
        `FastFold Agent API ${response.status}: ${
          detail || response.statusText
        }`
      )
    }
    const disposition = response.headers.get('content-disposition') || ''
    const match = disposition.match(/filename="?([^"]+)"?/i)
    const filename =
      match?.[1] ||
      `fastfold-diagnostics-${new Date()
        .toISOString()
        .replace(/[:.]/g, '')}.zip`
    return { blob: await response.blob(), filename }
  }

  async listSessions(options?: {
    projectId?: string | null
    signal?: AbortSignal
  }): Promise<AgentSession[]> {
    const params = new URLSearchParams()
    if (options?.projectId) params.set('projectId', options.projectId)
    const query = params.toString()
    const result = await this.request<{ data: AgentSession[] }>(
      `/sessions${query ? `?${query}` : ''}`,
      { signal: options?.signal }
    )
    return result.data
  }

  /**
   * Bulk metadata fetch for a specific set of session ids — used to hydrate
   * foreign chats (from other projects) that appear inside cross-project
   * split groups. Missing ids are silently skipped by the backend.
   */
  async listSessionsByIds(
    ids: string[],
    signal?: AbortSignal
  ): Promise<AgentSession[]> {
    const cleaned = ids.filter(Boolean)
    if (cleaned.length === 0) return []
    const params = new URLSearchParams({ ids: cleaned.join(',') })
    const result = await this.request<{ data: AgentSession[] }>(
      `/sessions?${params.toString()}`,
      { signal }
    )
    return result.data
  }

  // ─── Terminal-as-first-class-item (FAS-107) ───────────────────────────

  async listTerminals(options?: {
    projectId?: string | null
    signal?: AbortSignal
  }): Promise<TerminalSession[]> {
    const params = new URLSearchParams()
    if (options?.projectId) params.set('projectId', options.projectId)
    const query = params.toString()
    const result = await this.request<{ data: TerminalSession[] }>(
      `/terminals${query ? `?${query}` : ''}`,
      { signal: options?.signal }
    )
    return result.data
  }

  async getTerminal(
    id: string,
    signal?: AbortSignal
  ): Promise<TerminalSession> {
    return this.request<TerminalSession>(`/terminals/${id}`, { signal })
  }

  async createTerminal(input: {
    title?: string | null
    projectId?: string | null
    workspacePath?: string | null
    shell?: string | null
    originChatId?: string | null
    slotKey?: string | null
    cols?: number
    rows?: number
  }): Promise<TerminalSession> {
    return this.request<TerminalSession>('/terminals', {
      method: 'POST',
      body: JSON.stringify({
        title: input.title ?? null,
        projectId: input.projectId ?? null,
        workspacePath: input.workspacePath ?? null,
        shell: input.shell ?? null,
        originChatId: input.originChatId ?? null,
        slotKey: input.slotKey ?? null,
        cols: input.cols ?? 80,
        rows: input.rows ?? 24
      }),
      headers: { 'content-type': 'application/json' }
    })
  }

  async updateTerminal(
    id: string,
    patch: {
      title?: string | null
      projectId?: string | null
      organizeLabel?: string | null
    }
  ): Promise<TerminalSession> {
    return this.request<TerminalSession>(`/terminals/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
      headers: { 'content-type': 'application/json' }
    })
  }

  async deleteTerminal(id: string): Promise<void> {
    await this.request<void>(`/terminals/${id}`, { method: 'DELETE' })
  }

  async listWorkspaceItems(options?: {
    projectId?: string | null
    kinds?: Array<'chat' | 'terminal'>
    limit?: number
    signal?: AbortSignal
  }): Promise<WorkspaceItem[]> {
    const params = new URLSearchParams()
    if (options?.projectId) params.set('projectId', options.projectId)
    if (options?.kinds && options.kinds.length > 0) {
      params.set('kind', options.kinds.join(','))
    }
    if (options?.limit) params.set('limit', String(options.limit))
    const query = params.toString()
    const result = await this.request<{ data: WorkspaceItem[] }>(
      `/workspace-items${query ? `?${query}` : ''}`,
      { signal: options?.signal }
    )
    return result.data
  }

  async getSessionsRevision(signal?: AbortSignal): Promise<string> {
    const result = await this.request<{ revision: string }>(
      '/sessions/revision',
      {
        signal
      }
    )
    return result.revision
  }

  getSession(sessionId: string, signal?: AbortSignal): Promise<AgentSession> {
    return this.request<AgentSession>(
      `/sessions/${encodeURIComponent(sessionId)}`,
      { signal }
    )
  }

  async getCapySession(signal?: AbortSignal): Promise<AgentSession> {
    try {
      return await this.request<AgentSession>('/capy/session', { signal })
    } catch (cause) {
      const listed = await this.request<{ data: AgentSession[] }>(
        '/sessions?source=capy',
        { signal }
      )
      const found = listed.data.find(item => item.source === 'capy')
      if (found) return found
      throw cause
    }
  }

  async resetCapySession(signal?: AbortSignal): Promise<AgentSession> {
    return this.request<AgentSession>('/capy/session/reset', {
      method: 'POST',
      signal
    })
  }

  async setCapyScope(
    scope: { projectId?: string | null; sessionId?: string | null },
    signal?: AbortSignal
  ): Promise<{ projectId: string | null; sessionId: string | null }> {
    return this.request<{ projectId: string | null; sessionId: string | null }>(
      '/capy/scope',
      {
        method: 'PUT',
        body: JSON.stringify({
          projectId: scope.projectId ?? null,
          sessionId: scope.sessionId ?? null
        }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async listProjects(signal?: AbortSignal): Promise<AgentProject[]> {
    const result = await this.request<{ data: AgentProject[] }>('/projects', {
      signal
    })
    return result.data
  }

  async listSites(options?: {
    q?: string | null
    signal?: AbortSignal
  }): Promise<Site[]> {
    const params = new URLSearchParams()
    if (options?.q) params.set('q', options.q)
    const query = params.toString()
    const result = await this.request<{ data: Site[] } | Site[]>(
      `/sites${query ? `?${query}` : ''}`,
      { signal: options?.signal }
    )
    return Array.isArray(result) ? result : result.data
  }

  createSite(
    input: {
      name: string
      sourceSessionId?: string | null
      sourceProjectId?: string | null
      sourcePath?: string | null
      slug?: string | null
    },
    signal?: AbortSignal
  ): Promise<Site> {
    return this.request<Site>('/sites', {
      method: 'POST',
      body: JSON.stringify({
        name: input.name,
        session_id: input.sourceSessionId,
        project_id: input.sourceProjectId,
        path: input.sourcePath
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  getSite(siteId: string, signal?: AbortSignal): Promise<Site> {
    return this.request<Site>(`/sites/${encodeURIComponent(siteId)}`, {
      signal
    })
  }

  updateSite(
    siteId: string,
    input: { name?: string; slug?: string | null },
    signal?: AbortSignal
  ): Promise<Site> {
    return this.request<Site>(`/sites/${encodeURIComponent(siteId)}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  async deleteSite(siteId: string, signal?: AbortSignal): Promise<void> {
    await this.request<unknown>(`/sites/${encodeURIComponent(siteId)}`, {
      method: 'DELETE',
      signal
    })
  }

  refreshSite(siteId: string, signal?: AbortSignal): Promise<Site> {
    return this.request<Site>(
      `/sites/${encodeURIComponent(siteId)}/refresh`,
      { method: 'POST', signal }
    )
  }

  createSitePreviewTicket(
    siteId: string,
    signal?: AbortSignal
  ): Promise<SitePreviewTicket> {
    return this.request<SitePreviewTicket>(
      `/sites/${encodeURIComponent(siteId)}/preview-ticket`,
      { method: 'POST', signal }
    )
  }

  async publishSite(
    siteId: string,
    input?: { slug?: string | null },
    signal?: AbortSignal
  ): Promise<Site> {
    const result = await this.request<{ site: Site }>(
      `/sites/${encodeURIComponent(siteId)}/publish`,
      {
        method: 'POST',
        body: JSON.stringify({ slug: input?.slug }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
    return result.site
  }

  async listLibrary(options?: {
    kind?: LibraryKind | null
    q?: string | null
    projectId?: string | null
    page?: number
    perPage?: number
    signal?: AbortSignal
  }): Promise<LibraryItemList> {
    const params = new URLSearchParams()
    if (options?.kind) params.set('kind', options.kind)
    if (options?.q) params.set('q', options.q)
    if (options?.projectId) params.set('projectId', options.projectId)
    if (options?.page != null) params.set('page', String(options.page))
    if (options?.perPage != null)
      params.set('per_page', String(options.perPage))
    const query = params.toString()
    return this.request<LibraryItemList>(
      `/library${query ? `?${query}` : ''}`,
      { signal: options?.signal }
    )
  }

  async uploadLibraryFile(
    file: File,
    signal?: AbortSignal
  ): Promise<LibraryItem> {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(`${this.baseUrl}/v1/library/upload`, {
      method: 'POST',
      credentials: 'include',
      body: form,
      headers: this.headers(),
      signal
    })
    if (!response.ok) {
      throw new Error(
        `FastFold Agent API ${response.status}: ${await response.text()}`
      )
    }
    return (await response.json()) as LibraryItem
  }

  updateLibraryItem(
    itemId: string,
    input: { displayName: string },
    signal?: AbortSignal
  ): Promise<LibraryItem> {
    return this.request<LibraryItem>(`/library/${encodeURIComponent(itemId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ display_name: input.displayName }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  async deleteLibraryItem(itemId: string, signal?: AbortSignal): Promise<void> {
    await this.request<{ deleted: boolean }>(
      `/library/${encodeURIComponent(itemId)}`,
      { method: 'DELETE', signal }
    )
  }

  useLibraryInChat(
    input: {
      itemIds: string[]
      projectId?: string | null
      title?: string | null
    },
    signal?: AbortSignal
  ): Promise<UseLibraryInChatResult> {
    return this.request<UseLibraryInChatResult>('/library/use-in-chat', {
      method: 'POST',
      body: JSON.stringify({
        item_ids: input.itemIds,
        project_id: input.projectId,
        title: input.title
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  getLibraryContentUrl(itemId: string): string {
    return `${this.baseUrl}/v1/library/${encodeURIComponent(itemId)}/content`
  }

  async fetchLibraryContent(
    itemId: string,
    signal?: AbortSignal
  ): Promise<Blob> {
    const response = await fetch(this.getLibraryContentUrl(itemId), {
      method: 'GET',
      credentials: 'include',
      headers: this.headers(),
      signal
    })
    if (!response.ok) {
      throw new Error(
        `FastFold Agent API ${response.status}: ${await response.text()}`
      )
    }
    return response.blob()
  }

  readLibraryFile(
    itemId: string,
    signal?: AbortSignal
  ): Promise<WorkspaceFileContent> {
    return this.request<WorkspaceFileContent>(
      `/library/${encodeURIComponent(itemId)}/file`,
      { signal }
    )
  }

  writeLibraryFile(
    itemId: string,
    input: { content: string; encoding?: 'text' | 'base64' },
    signal?: AbortSignal
  ): Promise<WorkspaceFileContent> {
    return this.request<WorkspaceFileContent>(
      `/library/${encodeURIComponent(itemId)}/content`,
      {
        method: 'PUT',
        body: JSON.stringify({
          content: input.content,
          encoding: input.encoding || 'text'
        }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  // --- Slack connector ---------------------------------------------------

  getSlackStatus(signal?: AbortSignal): Promise<SlackConnectorStatus> {
    return this.request<SlackConnectorStatus>('/connectors/slack/status', {
      signal
    })
  }

  getSlackManifest(
    appName?: string,
    signal?: AbortSignal
  ): Promise<SlackManifest> {
    const query = appName ? `?app_name=${encodeURIComponent(appName)}` : ''
    return this.request<SlackManifest>(`/connectors/slack/manifest${query}`, {
      signal
    })
  }

  listSlackWorkspaces(
    signal?: AbortSignal
  ): Promise<{ data: SlackWorkspace[] }> {
    return this.request<{ data: SlackWorkspace[] }>(
      '/connectors/slack/workspaces',
      { signal }
    )
  }

  /** Ask FastFold Cloud for the Slack install URL to open in the browser. */
  startSlackOneClick(
    input?: { returnTo?: string },
    signal?: AbortSignal
  ): Promise<{ authUrl: string }> {
    return this.request<{ authUrl: string }>(
      '/connectors/slack/connect/one-click',
      {
        method: 'POST',
        body: JSON.stringify({ return_to: input?.returnTo ?? null }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  /**
   * Pick up an install completed in the browser.
   *
   * The desktop never sees the OAuth callback, so the UI polls this after
   * opening the install URL. Pass `reauthTeamId` when this is a reconnect for
   * a workspace we already have a (possibly stale) token for — that team's
   * fresh token overwrites the old one instead of being skipped.
   */
  importSlackOneClick(
    reauthTeamId?: string,
    signal?: AbortSignal
  ): Promise<{ data: SlackWorkspace[] }> {
    const query = reauthTeamId
      ? `?reauth_team_id=${encodeURIComponent(reauthTeamId)}`
      : ''
    return this.request<{ data: SlackWorkspace[] }>(
      `/connectors/slack/connect/one-click/import${query}`,
      { method: 'POST', signal }
    )
  }

  connectSlackManual(
    input: { botToken: string; appToken: string },
    signal?: AbortSignal
  ): Promise<SlackWorkspace> {
    return this.request<SlackWorkspace>('/connectors/slack/connect', {
      method: 'POST',
      body: JSON.stringify({
        bot_token: input.botToken,
        app_token: input.appToken
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  async disconnectSlackWorkspace(
    teamId: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request<{ ok: boolean }>(
      `/connectors/slack/workspaces/${encodeURIComponent(teamId)}`,
      { method: 'DELETE', signal }
    )
  }

  /** Pause/resume - keeps tokens and settings, unlike disconnect. */
  setSlackWorkspaceEnabled(
    teamId: string,
    enabled: boolean,
    signal?: AbortSignal
  ): Promise<SlackWorkspace> {
    return this.request<SlackWorkspace>(
      `/connectors/slack/workspaces/${encodeURIComponent(teamId)}/enabled`,
      {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  getSlackDirectory(
    teamId: string,
    options?: { refresh?: boolean; signal?: AbortSignal }
  ): Promise<SlackDirectory> {
    const query = options?.refresh ? '?refresh=true' : ''
    return this.request<SlackDirectory>(
      `/connectors/slack/workspaces/${encodeURIComponent(
        teamId
      )}/directory${query}`,
      { signal: options?.signal }
    )
  }

  listSlackPeople(
    teamId: string,
    signal?: AbortSignal
  ): Promise<{ data: SlackAllowedUser[] }> {
    return this.request<{ data: SlackAllowedUser[] }>(
      `/connectors/slack/workspaces/${encodeURIComponent(teamId)}/people`,
      { signal }
    )
  }

  allowSlackPerson(
    input: { teamId: string; slackUserId: string; displayName?: string | null },
    signal?: AbortSignal
  ): Promise<{ data: SlackAllowedUser[] }> {
    return this.request<{ data: SlackAllowedUser[] }>(
      '/connectors/slack/people',
      {
        method: 'POST',
        body: JSON.stringify({
          team_id: input.teamId,
          slack_user_id: input.slackUserId,
          display_name: input.displayName
        }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async disallowSlackPerson(
    teamId: string,
    slackUserId: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request<{ ok: boolean }>(
      `/connectors/slack/workspaces/${encodeURIComponent(teamId)}` +
        `/people/${encodeURIComponent(slackUserId)}`,
      { method: 'DELETE', signal }
    )
  }

  listSlackSubscriptions(
    sessionId?: string,
    signal?: AbortSignal
  ): Promise<{ data: SlackSubscription[] }> {
    const query = sessionId
      ? `?session_id=${encodeURIComponent(sessionId)}`
      : ''
    return this.request<{ data: SlackSubscription[] }>(
      `/connectors/slack/subscriptions${query}`,
      { signal }
    )
  }

  addSlackSubscription(
    input: { sessionId: string; channel: string },
    signal?: AbortSignal
  ): Promise<{ data: SlackSubscription[] }> {
    return this.request<{ data: SlackSubscription[] }>(
      '/connectors/slack/subscriptions',
      {
        method: 'POST',
        body: JSON.stringify({
          session_id: input.sessionId,
          channel: input.channel
        }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async removeSlackSubscription(
    sessionId: string,
    channel: string,
    signal?: AbortSignal
  ): Promise<void> {
    const params = new URLSearchParams({
      session_id: sessionId,
      channel
    })
    await this.request<{ ok: boolean }>(
      `/connectors/slack/subscriptions?${params}`,
      { method: 'DELETE', signal }
    )
  }

  listSlackParked(
    signal?: AbortSignal
  ): Promise<{ data: SlackParkedMessage[] }> {
    return this.request<{ data: SlackParkedMessage[] }>(
      '/connectors/slack/parked',
      { signal }
    )
  }

  async allowSlackParked(
    messageId: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request<{ ok: boolean }>(
      `/connectors/slack/parked/${encodeURIComponent(messageId)}/allow`,
      { method: 'POST', signal }
    )
  }

  async dismissSlackParked(
    messageId: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request<{ ok: boolean }>(
      `/connectors/slack/parked/${encodeURIComponent(messageId)}`,
      { method: 'DELETE', signal }
    )
  }

  getSessionSlackMute(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<SessionConnectorMute> {
    return this.request<SessionConnectorMute>(
      `/sessions/${encodeURIComponent(sessionId)}/connectors/slack`,
      { signal }
    )
  }

  setSessionSlackMute(
    sessionId: string,
    muted: boolean,
    signal?: AbortSignal
  ): Promise<SessionConnectorMute> {
    return this.request<SessionConnectorMute>(
      `/sessions/${encodeURIComponent(sessionId)}/connectors/slack`,
      {
        method: 'PUT',
        body: JSON.stringify({ muted }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  getProject(projectId: string, signal?: AbortSignal): Promise<AgentProject> {
    return this.request<AgentProject>(
      `/projects/${encodeURIComponent(projectId)}`,
      {
        signal
      }
    )
  }

  listProjectFolderFiles(
    projectId: string,
    signal?: AbortSignal
  ): Promise<ProjectFolderListing> {
    return this.request<ProjectFolderListing>(
      `/projects/${encodeURIComponent(projectId)}/folder-files`,
      { signal }
    )
  }

  readProjectFolderFile(
    projectId: string,
    path: string,
    signal?: AbortSignal
  ): Promise<WorkspaceFileContent> {
    const query = new URLSearchParams({ path })
    return this.request<WorkspaceFileContent>(
      `/projects/${encodeURIComponent(projectId)}/folder-files/content?${query}`,
      { signal }
    )
  }

  renameProjectFolderFile(
    projectId: string,
    path: string,
    name: string,
    signal?: AbortSignal
  ): Promise<ProjectFolderFile> {
    return this.request<ProjectFolderFile>(
      `/projects/${encodeURIComponent(projectId)}/folder-files`,
      {
        method: 'PATCH',
        body: JSON.stringify({ path, name }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  deleteProjectFolderFile(
    projectId: string,
    path: string,
    signal?: AbortSignal
  ): Promise<void> {
    const query = new URLSearchParams({ path })
    return this.request(
      `/projects/${encodeURIComponent(projectId)}/folder-files?${query}`,
      { method: 'DELETE', signal }
    ).then(() => undefined)
  }

  useProjectFolderInChat(
    projectId: string,
    input: { paths: string[]; title?: string | null },
    signal?: AbortSignal
  ): Promise<{ sessionId: string; paths: string[] }> {
    return this.request(
      `/projects/${encodeURIComponent(projectId)}/folder-files/use-in-chat`,
      {
        method: 'POST',
        body: JSON.stringify({
          paths: input.paths,
          title: input.title
        }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  createProject(
    input: {
      name: string
      description?: string | null
      agentContext?: string | null
      folderPath?: string | null
      icon?: string | null
      color?: string | null
      pinned?: boolean
      homeLayout?: WidgetLayout | null
    },
    signal?: AbortSignal
  ): Promise<AgentProject> {
    return this.request<AgentProject>('/projects', {
      method: 'POST',
      body: JSON.stringify({
        name: input.name,
        description: input.description,
        agentContext: input.agentContext,
        folderPath: input.folderPath,
        icon: input.icon,
        color: input.color,
        pinned: Boolean(input.pinned),
        homeLayout: input.homeLayout
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  updateProject(
    projectId: string,
    input: {
      name?: string
      description?: string | null
      agentContext?: string | null
      folderPath?: string | null
      icon?: string | null
      color?: string | null
      pinned?: boolean
      homeLayout?: WidgetLayout | null
    },
    signal?: AbortSignal
  ): Promise<AgentProject> {
    const body: Record<string, unknown> = {
      name: input.name,
      description: input.description,
      clearDescription: input.description === null,
      agentContext: input.agentContext,
      clearAgentContext: input.agentContext === null,
      icon: input.icon,
      color: input.color,
      pinned: input.pinned
    }
    // Only touch folder when the caller set folderPath. `null` clears; a string
    // sets. Omitting the field (e.g. pin toggle) must not wipe a linked folder.
    if (input.folderPath !== undefined) {
      if (input.folderPath === null || input.folderPath === '') {
        body.clearFolderPath = true
      } else {
        body.folderPath = input.folderPath
      }
    }
    if (input.homeLayout !== undefined) {
      if (input.homeLayout === null) {
        body.clearHomeLayout = true
      } else {
        body.homeLayout = input.homeLayout
      }
    }
    return this.request<AgentProject>(
      `/projects/${encodeURIComponent(projectId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify(body),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async getDashboardLayout(signal?: AbortSignal): Promise<WidgetLayout> {
    const raw = await this.request<{ layout: WidgetLayout }>(
      '/settings/dashboard-layout',
      { signal }
    )
    return raw.layout
  }

  async updateDashboardLayout(
    layout: WidgetLayout,
    signal?: AbortSignal
  ): Promise<WidgetLayout> {
    const raw = await this.request<{ layout: WidgetLayout }>(
      '/settings/dashboard-layout',
      {
        method: 'PUT',
        body: JSON.stringify({ layout }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
    return raw.layout
  }

  async deleteProject(projectId: string, signal?: AbortSignal): Promise<void> {
    await this.request<{ deleted: boolean }>(
      `/projects/${encodeURIComponent(projectId)}`,
      { method: 'DELETE', signal }
    )
  }

  async listSpecialists(signal?: AbortSignal): Promise<Specialist[]> {
    const result = await this.request<{ data: Specialist[] }>('/specialists', {
      signal
    })
    return result.data
  }

  getSpecialist(
    specialistId: string,
    signal?: AbortSignal
  ): Promise<Specialist> {
    return this.request<Specialist>(
      `/specialists/${encodeURIComponent(specialistId)}`,
      {
        signal
      }
    )
  }

  createSpecialist(
    input: {
      name: string
      slug?: string | null
      description?: string | null
      instructions?: string | null
      color?: string
      icon?: string
      roleLabel?: string | null
      avatarUrl?: string | null
      provider?: string | null
      model?: string | null
      openaiProfileId?: string | null
      cookbookId?: string | null
      priors?: string | null
      skillNames?: string[]
      toolNames?: string[]
      mcpServerIds?: string[]
      mcpCatalogIds?: string[]
      enabled?: boolean
    },
    signal?: AbortSignal
  ): Promise<Specialist> {
    return this.request<Specialist>('/specialists', {
      method: 'POST',
      body: JSON.stringify({
        name: input.name,
        slug: input.slug,
        description: input.description,
        instructions: input.instructions,
        color: input.color,
        icon: input.icon,
        role_label: input.roleLabel,
        avatar_url: input.avatarUrl,
        provider: input.provider,
        model: input.model,
        openai_profile_id: input.openaiProfileId,
        cookbook_id: input.cookbookId,
        priors: input.priors,
        skill_names: input.skillNames ?? [],
        tool_names: input.toolNames ?? [],
        mcp_server_ids: input.mcpServerIds ?? [],
        mcp_catalog_ids: input.mcpCatalogIds ?? [],
        enabled: input.enabled ?? true
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  updateSpecialist(
    specialistId: string,
    input: {
      name?: string
      slug?: string | null
      description?: string | null
      instructions?: string | null
      color?: string
      icon?: string
      roleLabel?: string | null
      avatarUrl?: string | null
      provider?: string | null
      model?: string | null
      openaiProfileId?: string | null
      clearLlm?: boolean
      cookbookId?: string | null
      priors?: string | null
      clearPriors?: boolean
      skillNames?: string[]
      toolNames?: string[]
      mcpServerIds?: string[]
      mcpCatalogIds?: string[]
      enabled?: boolean
    },
    signal?: AbortSignal
  ): Promise<Specialist> {
    return this.request<Specialist>(
      `/specialists/${encodeURIComponent(specialistId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          name: input.name,
          slug: input.slug,
          description: input.description,
          clear_description: input.description === null,
          instructions: input.instructions,
          clear_instructions: input.instructions === null,
          color: input.color,
          icon: input.icon,
          role_label: input.roleLabel,
          avatar_url: input.avatarUrl,
          provider: input.provider,
          model: input.model,
          openai_profile_id: input.openaiProfileId,
          clear_llm: input.clearLlm,
          cookbook_id: input.cookbookId,
          priors: input.priors,
          clear_priors: input.clearPriors || input.priors === null,
          skill_names: input.skillNames,
          tool_names: input.toolNames,
          mcp_server_ids: input.mcpServerIds,
          mcp_catalog_ids: input.mcpCatalogIds,
          enabled: input.enabled
        }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  getPromptBudget(
    options?: {
      specialistId?: string | null
      projectId?: string | null
      sampleQuery?: string | null
      tokenCountMethod?: 'tiktoken' | 'provider' | string | null
    },
    signal?: AbortSignal
  ): Promise<PromptBudgetResponse> {
    const params = new URLSearchParams()
    if (options?.specialistId) params.set('specialistId', options.specialistId)
    if (options?.projectId) params.set('projectId', options.projectId)
    if (options?.sampleQuery != null && options.sampleQuery !== '') {
      params.set('sampleQuery', options.sampleQuery)
    }
    if (options?.tokenCountMethod) {
      params.set('tokenCountMethod', String(options.tokenCountMethod))
    }
    const query = params.toString()
    return this.request<PromptBudgetResponse>(
      `/settings/prompt-budget${query ? `?${query}` : ''}`,
      { signal }
    )
  }

  async deleteSpecialist(
    specialistId: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request<{ deleted: boolean }>(
      `/specialists/${encodeURIComponent(specialistId)}`,
      { method: 'DELETE', signal }
    )
  }

  async searchSessions(
    query: string,
    signal?: AbortSignal
  ): Promise<AgentSession[]> {
    const params = new URLSearchParams({ q: query })
    const result = await this.request<{ data: AgentSession[] }>(
      `/sessions/search?${params}`,
      {
        signal
      }
    )
    return result.data
  }

  createSession(
    input: {
      title?: string
      workspacePath?: string | null
      projectId?: string | null
      specialistId?: string | null
      sandboxBackend?: 'builtin' | 'modal' | null
      clientSurface?: 'cli' | 'ui' | 'slack' | 'unknown'
      provider?: string | null
      model?: string | null
      openaiProfileId?: string | null
    },
    signal?: AbortSignal
  ): Promise<AgentSession> {
    return this.request<AgentSession>('/sessions', {
      method: 'POST',
      body: JSON.stringify({
        title: input.title,
        workspace_path: input.workspacePath,
        project_id: input.projectId,
        specialist_id: input.specialistId,
        sandbox_backend: input.sandboxBackend,
        client_surface: input.clientSurface ?? 'ui',
        provider: input.provider,
        model: input.model,
        openai_profile_id: input.openaiProfileId
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  /**
   * Clone a chat: same project, specialist, sandbox, model and the full
   * message history, in a new session with its own workspace.
   */
  duplicateSession(
    sessionId: string,
    input: { title?: string } = {},
    signal?: AbortSignal
  ): Promise<AgentSession> {
    return this.request<AgentSession>(
      `/sessions/${encodeURIComponent(sessionId)}/duplicate`,
      {
        method: 'POST',
        body: JSON.stringify({ title: input.title }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async getUsageOverview(
    signalOrOpts?:
      | AbortSignal
      | { projectId?: string | null; signal?: AbortSignal }
  ): Promise<UsageOverview> {
    const opts =
      signalOrOpts &&
      typeof signalOrOpts === 'object' &&
      !('aborted' in signalOrOpts)
        ? signalOrOpts
        : { signal: signalOrOpts as AbortSignal | undefined }
    const projectId = opts.projectId?.trim() || ''
    const query = projectId
      ? `?projectId=${encodeURIComponent(projectId)}`
      : ''
    const raw = await this.request<Record<string, unknown>>(
      `/usage/overview${query}`,
      { signal: opts.signal }
    )
    return normalizeUsageOverview(raw)
  }

  updateSession(
    sessionId: string,
    input: {
      title?: string
      organizeLabel?: 'pinned' | 'archive' | null
      projectId?: string | null
      specialistId?: string | null
      sandboxBackend?: 'builtin' | 'modal' | null
      provider?: string | null
      model?: string | null
      openaiProfileId?: string | null
      clearLlm?: boolean
    },
    signal?: AbortSignal
  ): Promise<AgentSession> {
    return this.request<AgentSession>(
      `/sessions/${encodeURIComponent(sessionId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          title: input.title,
          organize_label: input.organizeLabel ?? undefined,
          clear_organize_label: input.organizeLabel === null,
          project_id: input.projectId ?? undefined,
          clear_project_id: input.projectId === null,
          specialist_id: input.specialistId ?? undefined,
          clear_specialist_id: input.specialistId === null,
          sandbox_backend: input.sandboxBackend ?? undefined,
          clear_sandbox_backend: input.sandboxBackend === null,
          provider: input.provider === undefined ? undefined : input.provider,
          model: input.model === undefined ? undefined : input.model,
          openai_profile_id:
            input.openaiProfileId === undefined
              ? undefined
              : input.openaiProfileId,
          clear_llm: input.clearLlm === true
        }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  getSessionSandbox(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<SessionSandboxStatus> {
    return this.request<SessionSandboxStatus>(
      `/sessions/${encodeURIComponent(sessionId)}/sandbox`,
      { signal }
    )
  }

  sandboxStreamUrl(sessionId: string): string {
    const base = this.baseUrl.replace(/^http/, 'ws')
    const url = new URL(
      `${base}/v1/sessions/${encodeURIComponent(sessionId)}/sandbox/stream`
    )
    if (this.apiKey) url.searchParams.set('token', this.apiKey)
    return url.toString()
  }

  startSessionSandbox(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<SessionSandboxStatus> {
    return this.request<SessionSandboxStatus>(
      `/sessions/${encodeURIComponent(sessionId)}/sandbox/start`,
      { method: 'POST', signal }
    )
  }

  stopSessionSandbox(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<SessionSandboxStatus> {
    return this.request<SessionSandboxStatus>(
      `/sessions/${encodeURIComponent(sessionId)}/sandbox/stop`,
      { method: 'POST', signal }
    )
  }

  restartSessionSandbox(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<SessionSandboxStatus> {
    return this.request<SessionSandboxStatus>(
      `/sessions/${encodeURIComponent(sessionId)}/sandbox/restart`,
      { method: 'POST', signal }
    )
  }

  autoTitleSession(
    sessionId: string,
    input: { force?: boolean } = {},
    signal?: AbortSignal
  ): Promise<AgentSession> {
    return this.request<AgentSession>(
      `/sessions/${encodeURIComponent(sessionId)}/title/auto`,
      {
        method: 'POST',
        body: JSON.stringify({ force: Boolean(input.force) }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  compactSession(
    sessionId: string,
    input: { instructions?: string | null } = {},
    signal?: AbortSignal
  ): Promise<{ turnsBefore: number; turnsAfter: number; summary: string }> {
    return this.request<{
      turnsBefore: number
      turnsAfter: number
      summary: string
    }>(`/sessions/${encodeURIComponent(sessionId)}/compact`, {
      method: 'POST',
      body: JSON.stringify({
        instructions: input.instructions ?? null
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  async deleteSession(sessionId: string, signal?: AbortSignal): Promise<void> {
    await this.request<{ deleted: boolean }>(
      `/sessions/${encodeURIComponent(sessionId)}`,
      {
        method: 'DELETE',
        signal
      }
    )
  }

  async listMessages(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<AgentMessage[]> {
    const result = await this.request<{
      data: AgentMessage[]
      feedback?: Record<string, 'up' | 'down'>
    }>(`/sessions/${encodeURIComponent(sessionId)}/messages`, { signal })
    return result.data
  }

  async listEventHistory(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<AgentEvent[]> {
    const result = await this.request<{ data: AgentEvent[] }>(
      `/sessions/${encodeURIComponent(sessionId)}/events/history`,
      { signal }
    )
    return result.data
  }

  async getMessageFeedback(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<Record<string, 'up' | 'down'>> {
    const result = await this.request<{
      data: AgentMessage[]
      feedback?: Record<string, 'up' | 'down'>
    }>(`/sessions/${encodeURIComponent(sessionId)}/messages`, { signal })
    return result.feedback || {}
  }

  async setMessageFeedback(
    sessionId: string,
    messageId: string,
    reaction: 'up' | 'down' | null,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request(
      `/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(
        messageId
      )}/feedback`,
      {
        method: 'POST',
        body: JSON.stringify({ reaction }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  sendMessage(
    sessionId: string,
    content: string,
    signal?: AbortSignal
  ): Promise<{ runId: string }> {
    return this.request<{ runId: string }>(
      `/sessions/${encodeURIComponent(sessionId)}/messages`,
      {
        method: 'POST',
        body: JSON.stringify({ content }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async interrupt(sessionId: string, signal?: AbortSignal): Promise<boolean> {
    const result = await this.request<{ interrupted: boolean }>(
      `/sessions/${encodeURIComponent(sessionId)}/interrupt`,
      { method: 'POST', signal }
    )
    return result.interrupted
  }

  submitApprovals(
    sessionId: string,
    decisions: HitlDecision[],
    options?: { interruptId?: string | null; signal?: AbortSignal }
  ): Promise<{ accepted: boolean; interruptId?: string | null }> {
    return this.request<{ accepted: boolean; interruptId?: string | null }>(
      `/sessions/${encodeURIComponent(sessionId)}/approvals`,
      {
        method: 'POST',
        body: JSON.stringify({
          decisions,
          interruptId: options?.interruptId ?? null
        }),
        headers: { 'content-type': 'application/json' },
        signal: options?.signal
      }
    )
  }

  /**
   * Subscribe to the global session-lifecycle SSE stream (create / update /
   * delete / status_changed / run.*). Replaces the frontend's 2-second
   * `listSessions` poll + snapshot-diff for status transitions. One
   * connection covers every chat across every project.
   *
   * Same EventSource-first strategy as `streamEvents` (WKWebView buffer
   * quirk on the per-session SSE applies here too).
   */
  async streamGlobalSessionEvents(options: {
    signal?: AbortSignal
    onEvent: (event: {
      sequence: number
      type: string
      timestamp: number
      payload: Record<string, unknown>
    }) => void
  }): Promise<void> {
    if (typeof EventSource !== 'undefined') {
      const query = new URLSearchParams()
      if (this.apiKey) query.set('token', this.apiKey)
      const suffix = query.size ? `?${query}` : ''
      const url = `${this.baseUrl}/v1/session-events${suffix}`
      return new Promise<void>((resolve, reject) => {
        const source = new EventSource(url, { withCredentials: true })
        let opened = false
        const cleanup = () => {
          source.close()
          options.signal?.removeEventListener('abort', onAbort)
        }
        const onAbort = () => {
          cleanup()
          resolve()
        }
        if (options.signal?.aborted) {
          onAbort()
          return
        }
        options.signal?.addEventListener('abort', onAbort)
        source.onopen = () => {
          opened = true
        }
        source.onmessage = message => {
          try {
            options.onEvent(JSON.parse(message.data))
          } catch {
            // Ignore malformed frames; the stream keeps going.
          }
        }
        source.onerror = () => {
          if (source.readyState === EventSource.CLOSED) {
            cleanup()
            if (opened) resolve()
            else
              reject(
                new Error(
                  'FastFold Agent global session event stream failed to connect'
                )
              )
          }
        }
      })
    }
    // Fallback: fetch + ReadableStream (non-Tauri browsers without EventSource
    // are rare; the pattern mirrors `streamEvents`).
    const response = await fetch(`${this.baseUrl}/v1/session-events`, {
      credentials: 'include',
      headers: this.headers({ accept: 'text/event-stream' }),
      signal: options.signal
    })
    if (!response.ok || !response.body) {
      throw new Error(
        `FastFold Agent global session event stream failed with status ${response.status}`
      )
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        const data = frame
          .split('\n')
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).trim())
          .join('')
        if (data) options.onEvent(JSON.parse(data))
      }
    }
  }

  /**
   * One EventSource for sidebar lifecycle + visible chat transcripts.
   * Prefer this over N `/sessions/{id}/events` streams (HTTP/1.1 cap).
   */
  async streamMuxEvents(options: {
    sessionIds: string[]
    afterBySession?: Record<string, number>
    signal?: AbortSignal
    onFrame: (frame: {
      channel: 'transcript' | 'lifecycle'
      sessionId?: string
      event: Record<string, unknown>
    }) => void
  }): Promise<void> {
    const query = new URLSearchParams()
    if (options.sessionIds.length) {
      query.set('sessions', options.sessionIds.join(','))
    }
    const after = Object.entries(options.afterBySession || {})
      .filter(([, seq]) => Number(seq) > 0)
      .map(([id, seq]) => `${id}:${seq}`)
    if (after.length) query.set('after', after.join(','))
    if (this.apiKey) query.set('token', this.apiKey)
    const suffix = query.size ? `?${query}` : ''
    const url = `${this.baseUrl}/v1/events${suffix}`
    if (typeof EventSource !== 'undefined') {
      return new Promise<void>((resolve, reject) => {
        const source = new EventSource(url, { withCredentials: true })
        let opened = false
        const cleanup = () => {
          source.close()
          options.signal?.removeEventListener('abort', onAbort)
        }
        const onAbort = () => {
          cleanup()
          resolve()
        }
        if (options.signal?.aborted) {
          onAbort()
          return
        }
        options.signal?.addEventListener('abort', onAbort)
        source.onopen = () => {
          opened = true
        }
        source.onmessage = message => {
          try {
            const parsed = JSON.parse(message.data) as {
              channel?: string
              sessionId?: string
              event?: Record<string, unknown>
            }
            if (parsed.channel === 'transcript' && parsed.event) {
              options.onFrame({
                channel: 'transcript',
                sessionId: parsed.sessionId,
                event: parsed.event
              })
              return
            }
            if (parsed.channel === 'lifecycle' && parsed.event) {
              options.onFrame({
                channel: 'lifecycle',
                event: parsed.event
              })
            }
          } catch {
            // Ignore malformed frames; the stream keeps going.
          }
        }
        source.onerror = () => {
          if (source.readyState === EventSource.CLOSED) {
            cleanup()
            if (opened) resolve()
            else
              reject(
                new Error('FastFold Agent mux event stream failed to connect')
              )
          }
        }
      })
    }
    const response = await fetch(url, {
      credentials: 'include',
      headers: this.headers({ accept: 'text/event-stream' }),
      signal: options.signal
    })
    if (!response.ok || !response.body) {
      throw new Error(
        `FastFold Agent mux event stream failed with status ${response.status}`
      )
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        const data = frame
          .split('\n')
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).trim())
          .join('')
        if (!data) continue
        const parsed = JSON.parse(data) as {
          channel?: string
          sessionId?: string
          event?: Record<string, unknown>
        }
        if (parsed.channel === 'transcript' && parsed.event) {
          options.onFrame({
            channel: 'transcript',
            sessionId: parsed.sessionId,
            event: parsed.event
          })
        } else if (parsed.channel === 'lifecycle' && parsed.event) {
          options.onFrame({ channel: 'lifecycle', event: parsed.event })
        }
      }
    }
  }

  async streamEvents(
    sessionId: string,
    options: {
      afterSequence?: number
      signal?: AbortSignal
      onEvent: (event: AgentEvent) => void
    }
  ): Promise<void> {
    const query = new URLSearchParams()
    if (options.afterSequence)
      query.set('after_sequence', String(options.afterSequence))
    // Prefer native EventSource: WKWebView (Tauri) buffers fetch ReadableStream
    // chunks, delivering trailing frames (run.completed) seconds late. The
    // native SSE parser flushes per event and auto-reconnects with
    // Last-Event-ID, which the server maps back onto the event cursor.
    if (typeof EventSource !== 'undefined') {
      return this.streamEventsViaEventSource(sessionId, query, options)
    }
    const suffix = query.size ? `?${query}` : ''
    const response = await fetch(
      `${this.baseUrl}/v1/sessions/${encodeURIComponent(
        sessionId
      )}/events${suffix}`,
      {
        credentials: 'include',
        headers: this.headers({ accept: 'text/event-stream' }),
        signal: options.signal
      }
    )
    if (!response.ok || !response.body) {
      throw new Error(
        `FastFold Agent event stream failed with status ${response.status}`
      )
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''

      for (const frame of frames) {
        const data = frame
          .split('\n')
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).trim())
          .join('')
        if (data) options.onEvent(JSON.parse(data) as AgentEvent)
      }
    }
  }

  private streamEventsViaEventSource(
    sessionId: string,
    query: URLSearchParams,
    options: {
      signal?: AbortSignal
      onEvent: (event: AgentEvent) => void
    }
  ): Promise<void> {
    // EventSource cannot set headers; authenticate via query token
    // (same pattern as the sandbox/PTY WebSockets) plus cookies.
    if (this.apiKey) query.set('token', this.apiKey)
    const suffix = query.size ? `?${query}` : ''
    const url = `${this.baseUrl}/v1/sessions/${encodeURIComponent(
      sessionId
    )}/events${suffix}`
    return new Promise<void>((resolve, reject) => {
      const source = new EventSource(url, { withCredentials: true })
      let opened = false
      const cleanup = () => {
        source.close()
        options.signal?.removeEventListener('abort', onAbort)
      }
      const onAbort = () => {
        cleanup()
        resolve()
      }
      if (options.signal?.aborted) {
        onAbort()
        return
      }
      options.signal?.addEventListener('abort', onAbort)
      source.onopen = () => {
        opened = true
      }
      source.onmessage = message => {
        try {
          options.onEvent(JSON.parse(message.data) as AgentEvent)
        } catch {
          // Ignore malformed frames; the stream keeps going.
        }
      }
      source.onerror = () => {
        // Transient errors auto-reconnect (readyState CONNECTING); only a
        // CLOSED source is fatal.
        if (source.readyState === EventSource.CLOSED) {
          cleanup()
          if (opened) resolve()
          else
            reject(new Error('FastFold Agent event stream failed to connect'))
        }
      }
    })
  }

  async listFiles(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<WorkspaceFile[]> {
    const result = await this.request<{ data: WorkspaceFile[] }>(
      `/sessions/${encodeURIComponent(sessionId)}/files`,
      { signal }
    )
    return result.data
  }

  readFile(
    sessionId: string,
    path: string,
    signal?: AbortSignal
  ): Promise<WorkspaceFileContent> {
    const query = new URLSearchParams({ path })
    return this.request<WorkspaceFileContent>(
      `/sessions/${encodeURIComponent(sessionId)}/files/content?${query}`,
      { signal }
    )
  }

  async writeFile(
    sessionId: string,
    input: {
      path: string
      content: string
      encoding?: 'text' | 'base64'
      baseVersion?: string | null
    },
    signal?: AbortSignal
  ): Promise<FileWriteResult> {
    const response = await fetch(
      `${this.baseUrl}/v1/sessions/${encodeURIComponent(
        sessionId
      )}/files/content`,
      {
        method: 'PUT',
        credentials: 'include',
        body: JSON.stringify({
          path: input.path,
          content: input.content,
          encoding: input.encoding || 'text',
          base_version: input.baseVersion
        }),
        headers: this.headers({ 'content-type': 'application/json' }),
        signal
      }
    )
    if (response.status === 409) {
      const body = (await response.json()) as { current: WorkspaceFileContent }
      return { ok: false, conflict: true, current: body.current }
    }
    if (!response.ok) {
      throw new Error(
        `FastFold Agent API ${response.status}: ${await response.text()}`
      )
    }
    return {
      ok: true,
      content: (await response.json()) as WorkspaceFileContent
    }
  }

  async uploadFile(
    sessionId: string,
    file: File,
    relativeDirectory = 'uploads',
    signal?: AbortSignal
  ): Promise<WorkspaceFileContent> {
    const form = new FormData()
    form.append('file', file)
    if (relativeDirectory) form.append('relative_dir', relativeDirectory)
    const response = await fetch(
      `${this.baseUrl}/v1/sessions/${encodeURIComponent(
        sessionId
      )}/files/upload`,
      {
        method: 'POST',
        credentials: 'include',
        body: form,
        headers: this.headers(),
        signal
      }
    )
    if (!response.ok) {
      throw new Error(
        `FastFold Agent API ${response.status}: ${await response.text()}`
      )
    }
    return (await response.json()) as WorkspaceFileContent
  }

  async createFolder(
    sessionId: string,
    path: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request(
      `/sessions/${encodeURIComponent(sessionId)}/files/folders`,
      {
        method: 'POST',
        body: JSON.stringify({ path }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async moveFile(
    sessionId: string,
    sourcePath: string,
    targetPath: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request(
      `/sessions/${encodeURIComponent(sessionId)}/files/move`,
      {
        method: 'POST',
        body: JSON.stringify({
          source_path: sourcePath,
          target_path: targetPath
        }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async deleteFile(
    sessionId: string,
    path: string,
    recursive = false,
    signal?: AbortSignal
  ): Promise<void> {
    const query = new URLSearchParams({ path, recursive: String(recursive) })
    await this.request(
      `/sessions/${encodeURIComponent(sessionId)}/files?${query}`,
      {
        method: 'DELETE',
        signal
      }
    )
  }

  downloadUrl(sessionId: string, path: string): string {
    const query = new URLSearchParams({ path })
    return `${this.baseUrl}/v1/sessions/${encodeURIComponent(
      sessionId
    )}/files/download?${query}`
  }

  async listSkills(signal?: AbortSignal): Promise<AgentSkill[]> {
    const result = await this.request<{ data: AgentSkill[] }>('/skills', {
      signal
    })
    return result.data
  }

  async listSkillSources(signal?: AbortSignal): Promise<AgentSkillSource[]> {
    const result = await this.request<{ data: AgentSkillSource[] }>(
      '/skills/sources',
      { signal }
    )
    return result.data
  }

  async searchSkillCatalog(
    query: string,
    limit = 12,
    signal?: AbortSignal
  ): Promise<AgentCatalogSkill[]> {
    const params = new URLSearchParams({
      q: query,
      limit: String(limit)
    })
    const result = await this.request<{ data: AgentCatalogSkill[] }>(
      `/skills/catalog/search?${params.toString()}`,
      { signal }
    )
    return result.data
  }

  async listSkillCatalogLeaderboard(
    options?: {
      view?: AgentCatalogLeaderboardView
      page?: number
      perPage?: number
    },
    signal?: AbortSignal
  ): Promise<AgentCatalogLeaderboard> {
    const params = new URLSearchParams({
      view: options?.view || 'all-time',
      page: String(options?.page ?? 0),
      per_page: String(options?.perPage ?? 50)
    })
    return this.request<AgentCatalogLeaderboard>(
      `/skills/catalog/leaderboard?${params.toString()}`,
      { signal }
    )
  }

  getCatalogSkillDetail(
    source: string,
    skill: string,
    signal?: AbortSignal
  ): Promise<AgentCatalogSkillDetail> {
    const params = new URLSearchParams({ source, skill })
    return this.request<AgentCatalogSkillDetail>(
      `/skills/catalog/detail?${params.toString()}`,
      { signal }
    )
  }

  getCatalogSkillAudit(
    source: string,
    skill: string,
    signal?: AbortSignal
  ): Promise<AgentCatalogSkillAudit> {
    const params = new URLSearchParams({ source, skill })
    return this.request<AgentCatalogSkillAudit>(
      `/skills/catalog/audit?${params.toString()}`,
      { signal }
    )
  }

  bulkSkillAction(
    action: AgentSkillBatchAction,
    names: string[],
    signal?: AbortSignal
  ): Promise<AgentSkillBatchResult> {
    return this.request<AgentSkillBatchResult>('/skills/batch', {
      method: 'POST',
      body: JSON.stringify({ action, names }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  getSkill(name: string, signal?: AbortSignal): Promise<AgentSkillDetail> {
    return this.request<AgentSkillDetail>(
      `/skills/${encodeURIComponent(name)}`,
      { signal }
    )
  }

  getSkillDeps(
    name: string,
    signal?: AbortSignal
  ): Promise<AgentSkillDepsStatus> {
    return this.request<AgentSkillDepsStatus>(
      `/skills/${encodeURIComponent(name)}/deps`,
      { signal }
    )
  }

  doctorSkillDeps(
    name: string,
    signal?: AbortSignal
  ): Promise<AgentSkillDepsStatus> {
    return this.request<AgentSkillDepsStatus>(
      `/skills/${encodeURIComponent(name)}/deps/doctor`,
      { signal }
    )
  }

  installSkillDeps(
    name: string,
    options?: { force?: boolean },
    signal?: AbortSignal
  ): Promise<AgentSkillDepsInstallResult> {
    return this.request<AgentSkillDepsInstallResult>(
      `/skills/${encodeURIComponent(name)}/deps/install`,
      {
        method: 'POST',
        body: JSON.stringify({ force: Boolean(options?.force) }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  setSkillEnabled(
    name: string,
    enabled: boolean,
    signal?: AbortSignal
  ): Promise<AgentSkillDetail> {
    return this.request<AgentSkillDetail>(
      `/skills/${encodeURIComponent(name)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async installSkill(source: string, signal?: AbortSignal): Promise<string[]> {
    const result = await this.request<{ installed: string[] }>('/skills', {
      method: 'POST',
      body: JSON.stringify({ source }),
      headers: { 'content-type': 'application/json' },
      signal
    })
    return result.installed
  }

  async installSkillFile(file: File, signal?: AbortSignal): Promise<string[]> {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(`${this.baseUrl}/v1/skills/upload`, {
      method: 'POST',
      credentials: 'include',
      body: form,
      headers: this.headers(),
      signal
    })
    if (!response.ok) {
      throw new Error(
        `FastFold Agent API ${response.status}: ${await response.text()}`
      )
    }
    const result = (await response.json()) as { installed: string[] }
    return result.installed
  }

  async removeSkill(name: string, signal?: AbortSignal): Promise<void> {
    await this.request(`/skills/${encodeURIComponent(name)}`, {
      method: 'DELETE',
      signal
    })
  }

  async upgradeSkills(signal?: AbortSignal): Promise<string[]> {
    const result = await this.request<{ installed: string[] }>(
      '/skills/upgrade',
      {
        method: 'POST',
        signal
      }
    )
    return result.installed
  }

  async listIntegrations(signal?: AbortSignal): Promise<IntegrationSummary[]> {
    const result = await this.request<{ data: IntegrationSummary[] }>(
      '/integrations',
      { signal }
    )
    // Legacy global OpenAI-compatible key is redundant with per–Local LLM profile keys.
    return result.data.filter(item => item.key !== 'openai-compatible')
  }

  updateIntegration(
    key: string,
    values: Record<string, string>,
    signal?: AbortSignal
  ): Promise<IntegrationSummary> {
    return this.request<IntegrationSummary>(
      `/integrations/${encodeURIComponent(key)}`,
      {
        method: 'PUT',
        body: JSON.stringify({ values }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  /** Open Cloud allow page; poll importFastfoldOneClick until ready. */
  startFastfoldOneClick(
    signal?: AbortSignal
  ): Promise<{ authUrl: string }> {
    return this.request<{ authUrl: string }>(
      '/integrations/fastfold-cloud/one-click',
      { method: 'POST', signal }
    )
  }

  importFastfoldOneClick(signal?: AbortSignal): Promise<{
    ready: boolean
    provider?: IntegrationSummary | null
    teamId?: string | null
  }> {
    return this.request<{
      ready: boolean
      provider?: IntegrationSummary | null
      teamId?: string | null
    }>('/integrations/fastfold-cloud/one-click/import', {
      method: 'POST',
      signal
    })
  }

  removeIntegration(
    key: string,
    signal?: AbortSignal
  ): Promise<IntegrationSummary> {
    return this.request<IntegrationSummary>(
      `/integrations/${encodeURIComponent(key)}`,
      {
        method: 'DELETE',
        signal
      }
    )
  }

  autofillIntegration(
    key: string,
    signal?: AbortSignal
  ): Promise<IntegrationSummary> {
    return this.request<IntegrationSummary>(
      `/integrations/${encodeURIComponent(key)}/autofill`,
      {
        method: 'POST',
        signal
      }
    )
  }

  installIntegrationCapability(
    key: string,
    capabilityId: string,
    signal?: AbortSignal
  ): Promise<IntegrationSummary> {
    return this.request<IntegrationSummary>(
      `/integrations/${encodeURIComponent(
        key
      )}/capabilities/${encodeURIComponent(capabilityId)}/install`,
      {
        method: 'POST',
        signal
      }
    )
  }

  setupIntegration(
    key: string,
    workingDirectory?: string | null,
    signal?: AbortSignal
  ): Promise<IntegrationSetupResult> {
    const body =
      workingDirectory && workingDirectory.trim()
        ? JSON.stringify({ workingDirectory: workingDirectory.trim() })
        : undefined
    return this.request<IntegrationSetupResult>(
      `/integrations/${encodeURIComponent(key)}/setup`,
      {
        method: 'POST',
        body,
        headers: body ? { 'content-type': 'application/json' } : undefined,
        signal
      }
    )
  }

  async validateIntegration(
    key: string,
    signal?: AbortSignal
  ): Promise<{ ok: boolean; message: string }> {
    return this.request<{ ok: boolean; message: string }>(
      `/integrations/${encodeURIComponent(key)}/validate`,
      { method: 'POST', signal }
    )
  }

  /** Fetch the stored secret for local reveal/copy (user opt-in). */
  revealIntegrationSecret(
    key: string,
    signal?: AbortSignal
  ): Promise<{ configured: boolean; envVar: string; value: string }> {
    return this.request<{ configured: boolean; envVar: string; value: string }>(
      `/integrations/${encodeURIComponent(key)}/secret`,
      { signal }
    )
  }

  getRuntimeSettings(signal?: AbortSignal): Promise<RuntimeSettings> {
    return this.request<RuntimeSettings>('/settings/runtime', { signal })
  }

  updateRuntimeSettings(
    changes: Partial<RuntimeSettings>,
    signal?: AbortSignal
  ): Promise<RuntimeSettings> {
    return this.request<RuntimeSettings>('/settings/runtime', {
      method: 'PATCH',
      body: JSON.stringify({
        provider: changes.provider,
        model: changes.model,
        openai_base_url: changes.openaiBaseUrl,
        agent_profile: changes.agentProfile,
        tool_mode: changes.toolMode,
        knowledge_level: changes.knowledgeLevel,
        reasoning_effort: changes.reasoningEffort,
        reasoning_fast: changes.reasoningFast,
        recursion_limit: changes.recursionLimit,
        max_sdk_turns: changes.maxSdkTurns,
        group_tool_traces: changes.groupToolTraces,
        tool_trace_detail_limit: changes.toolTraceDetailLimit,
        background_watch_timeout_s: changes.backgroundWatchTimeoutS,
        interrupt_drain_timeout_s: changes.interruptDrainTimeoutS,
        parallel_max_threads: changes.parallelMaxThreads,
        tool_health_enabled: changes.toolHealthEnabled,
        tool_health_fail_threshold: changes.toolHealthFailThreshold,
        tool_health_suppress_seconds: changes.toolHealthSuppressSeconds,
        plan_mode: changes.planMode,
        file_access: changes.fileAccess,
        max_concurrent_runs: changes.maxConcurrentRuns,
        min_free_memory_mb: changes.minFreeMemoryMb
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  /** Agent runs executing / queued right now, and the memory headroom. */
  getRunCapacity(signal?: AbortSignal): Promise<RunCapacity> {
    return this.request<RunCapacity>('/settings/capacity', { signal })
  }

  getOnboardingSettings(signal?: AbortSignal): Promise<OnboardingSettings> {
    return this.request<OnboardingSettings>('/settings/onboarding', { signal })
  }

    updateOnboardingSettings(
    changes: Partial<OnboardingSettings>,
    signal?: AbortSignal
  ): Promise<OnboardingSettings> {
    return this.request<OnboardingSettings>('/settings/onboarding', {
      method: 'PATCH',
      body: JSON.stringify({
        completed: changes.completed,
        step: changes.step
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  resetAppSettings(signal?: AbortSignal): Promise<OnboardingSettings> {
    return this.request<OnboardingSettings>('/settings/reset', {
      method: 'POST',
      signal
    })
  }

  getSandboxSettings(signal?: AbortSignal): Promise<SandboxSettings> {
    return this.request<SandboxSettings>('/settings/sandbox', { signal })
  }

  updateSandboxSettings(
    changes: Partial<SandboxSettings>,
    signal?: AbortSignal
  ): Promise<SandboxSettings> {
    return this.request<SandboxSettings>('/settings/sandbox', {
      method: 'PATCH',
      body: JSON.stringify({
        backend: changes.backend,
        modal_app: changes.modalApp,
        cpu_image: changes.cpuImage,
        gpu_image: changes.gpuImage,
        pip_packages: changes.pipPackages,
        compute_type: changes.computeType,
        gpu_class: changes.gpuClass,
        cpu_cores: changes.cpuCores,
        ram_gb: changes.ramGb,
        idle_ttl_seconds: changes.idleTtlSeconds
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  probeSandboxSettings(signal?: AbortSignal): Promise<SandboxProbeReport> {
    return this.request<SandboxProbeReport>('/settings/sandbox/probe', {
      method: 'POST',
      signal
    })
  }

  getAccount(options?: {
    checkUpdates?: boolean
    signal?: AbortSignal
  }): Promise<AccountSummary> {
    const params = new URLSearchParams()
    if (options?.checkUpdates) params.set('check_updates', 'true')
    const query = params.toString()
    return this.request<AccountSummary>(`/account${query ? `?${query}` : ''}`, {
      signal: options?.signal
    })
  }

  logoutAccount(signal?: AbortSignal): Promise<AccountSummary> {
    return this.request<AccountSummary>('/account/logout', {
      method: 'POST',
      signal
    })
  }

  async listModels(options?: {
    enabledOnly?: boolean
    discover?: boolean
    signal?: AbortSignal
  }): Promise<AgentModel[]> {
    const params = new URLSearchParams()
    if (options?.enabledOnly) params.set('enabled_only', 'true')
    if (options?.discover === false) params.set('discover', 'false')
    const query = params.toString()
    const result = await this.request<{ data: AgentModel[] }>(
      `/models${query ? `?${query}` : ''}`,
      { signal: options?.signal }
    )
    return result.data
  }

  getModelPreferences(signal?: AbortSignal): Promise<ModelPreferences> {
    return this.request<ModelPreferences>('/models/preferences', { signal })
  }

  toggleModelFavorite(
    input: ToggleModelFavoriteInput,
    signal?: AbortSignal
  ): Promise<ToggleModelFavoriteResult> {
    return this.request<ToggleModelFavoriteResult>(
      '/models/preferences/favorite',
      {
        method: 'POST',
        body: JSON.stringify({
          model: input.model,
          ...(input.provider ? { provider: input.provider } : {}),
          ...(input.profileId ? { profileId: input.profileId } : {})
        }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  updateModelEnabled(
    modelId: string,
    enabled: boolean,
    signal?: AbortSignal,
    provider?: string | null
  ): Promise<AgentModel> {
    return this.request<AgentModel>(`/models/${encodeURIComponent(modelId)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        enabled,
        ...(provider ? { provider } : {})
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  createCustomModel(
    input: CreateAgentModelInput,
    signal?: AbortSignal
  ): Promise<AgentModel> {
    return this.request<AgentModel>('/models', {
      method: 'POST',
      body: JSON.stringify({
        id: input.id,
        provider: input.provider || 'openai',
        label: input.label
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  async deleteCustomModel(
    modelId: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request(`/models/${encodeURIComponent(modelId)}`, {
      method: 'DELETE',
      signal
    })
  }

  async listModelProfiles(options?: {
    includeCloud?: boolean
    signal?: AbortSignal
  }): Promise<ModelProfile[]> {
    const params = new URLSearchParams()
    if (options?.includeCloud === false) params.set('include_cloud', 'false')
    const query = params.toString()
    const result = await this.request<{ data: ModelProfile[] }>(
      `/model-profiles${query ? `?${query}` : ''}`,
      { signal: options?.signal }
    )
    return result.data
  }

  createModelProfile(
    input: UpsertModelProfileInput,
    signal?: AbortSignal
  ): Promise<ModelProfile> {
    return this.request<ModelProfile>('/model-profiles', {
      method: 'POST',
      body: JSON.stringify({
        id: input.id,
        label: input.label,
        backend: input.backend,
        base_url: input.baseUrl,
        api_key: input.apiKey,
        default_model: input.defaultModel,
        discovery: input.discovery,
        set_active: input.setActive,
        set_default: input.setDefault
      }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  updateModelProfile(
    profileId: string,
    input: UpsertModelProfileInput,
    signal?: AbortSignal
  ): Promise<ModelProfile> {
    return this.request<ModelProfile>(
      `/model-profiles/${encodeURIComponent(profileId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          id: profileId,
          label: input.label,
          backend: input.backend,
          base_url: input.baseUrl,
          api_key: input.apiKey,
          default_model: input.defaultModel,
          discovery: input.discovery,
          set_active: input.setActive,
          set_default: input.setDefault
        }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async deleteModelProfile(
    profileId: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request(`/model-profiles/${encodeURIComponent(profileId)}`, {
      method: 'DELETE',
      signal
    })
  }

  /** Fetch the stored Local LLM API key for reveal/copy (user opt-in). */
  revealModelProfileSecret(
    profileId: string,
    signal?: AbortSignal
  ): Promise<{ configured: boolean; value: string }> {
    return this.request<{ configured: boolean; value: string }>(
      `/model-profiles/${encodeURIComponent(profileId)}/secret`,
      { signal }
    )
  }

  probeModelProfile(
    profileId: string,
    signal?: AbortSignal
  ): Promise<ModelProfileProbeResult> {
    return this.request<ModelProfileProbeResult>(
      `/model-profiles/${encodeURIComponent(profileId)}/probe`,
      { method: 'POST', signal }
    )
  }

  llamaRuntimeStatus(signal?: AbortSignal): Promise<LlamaRuntimeStatus> {
    return this.request<LlamaRuntimeStatus>('/local-runtimes/llama', { signal })
  }

  llamaRuntimeEnsure(signal?: AbortSignal): Promise<LlamaRuntimeStatus> {
    return this.request<LlamaRuntimeStatus>('/local-runtimes/llama/ensure', {
      method: 'POST',
      signal
    })
  }

  llamaRuntimeCatalog(query = '', signal?: AbortSignal): Promise<LlamaCatalog> {
    const q = query.trim()
    const path = q
      ? `/local-runtimes/llama/catalog?q=${encodeURIComponent(q)}`
      : '/local-runtimes/llama/catalog'
    return this.request<LlamaCatalog>(path, { signal })
  }

  llamaRuntimeUpdate(signal?: AbortSignal): Promise<LlamaRuntimeStatus> {
    return this.request<LlamaRuntimeStatus>('/local-runtimes/llama/update', {
      method: 'POST',
      signal
    })
  }

  llamaRuntimeLoad(
    model: string,
    signal?: AbortSignal
  ): Promise<{ ok: boolean; state: string }> {
    return this.request('/local-runtimes/llama/load', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ model }),
      signal
    })
  }

  llamaRuntimeUnload(
    model: string,
    signal?: AbortSignal
  ): Promise<{ ok: boolean; state: string }> {
    return this.request('/local-runtimes/llama/unload', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ model }),
      signal
    })
  }

  llamaRuntimeMemory(
    model: string,
    signal?: AbortSignal
  ): Promise<{ tiers: Array<{ context: number; memory: string }> }> {
    return this.request(
      `/local-runtimes/llama/memory?model=${encodeURIComponent(model)}`,
      { signal }
    )
  }

  llamaRuntimeSetContext(
    model: string,
    context: number,
    signal?: AbortSignal
  ): Promise<{ ok: boolean; context: number }> {
    return this.request('/local-runtimes/llama/context', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ model, context }),
      signal
    })
  }

  llamaRuntimeInstall(
    repo: string,
    quant?: string | null,
    signal?: AbortSignal
  ): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>('/local-runtimes/llama/install', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ repo, quant: quant ?? null }),
      signal
    })
  }

  llamaRuntimeRemove(
    model: string,
    signal?: AbortSignal
  ): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>('/local-runtimes/llama/remove', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ model }),
      signal
    })
  }

  discoverModelEndpoint(
    input: DiscoverModelEndpointInput,
    signal?: AbortSignal
  ): Promise<ModelProfileProbeResult> {
    return this.request<ModelProfileProbeResult>('/model-profiles/discover', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        backend: input.backend ?? undefined,
        baseUrl: input.baseUrl,
        apiKey: input.apiKey ?? undefined
      }),
      signal
    })
  }

  async listDatasets(signal?: AbortSignal): Promise<DatasetSummary[]> {
    const result = await this.request<{ data: DatasetSummary[] }>('/datasets', {
      signal
    })
    return result.data
  }

  installDataset(
    datasetId: string,
    signal?: AbortSignal
  ): Promise<DatasetInstallResult> {
    return this.request<DatasetInstallResult>(
      `/datasets/${encodeURIComponent(datasetId)}/install`,
      { method: 'POST', signal }
    )
  }

  removeDataset(
    datasetId: string,
    signal?: AbortSignal
  ): Promise<DatasetInstallResult> {
    return this.request<DatasetInstallResult>(
      `/datasets/${encodeURIComponent(datasetId)}`,
      { method: 'DELETE', signal }
    )
  }

  async listTools(options?: {
    enabledOnly?: boolean
    signal?: AbortSignal
  }): Promise<ToolCatalog> {
    const params = new URLSearchParams()
    if (options?.enabledOnly) params.set('enabled_only', 'true')
    const query = params.toString()
    return this.request<ToolCatalog>(`/tools${query ? `?${query}` : ''}`, {
      signal: options?.signal
    })
  }

  updateToolEnabled(
    toolId: string,
    enabled: boolean,
    signal?: AbortSignal
  ): Promise<ToolSummary> {
    return this.request<ToolSummary>(`/tools/${encodeURIComponent(toolId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  batchUpdateTools(
    action: ToolBatchAction,
    ids: string[],
    signal?: AbortSignal
  ): Promise<ToolBatchResult> {
    return this.request<ToolBatchResult>('/tools/batch', {
      method: 'POST',
      body: JSON.stringify({ action, ids }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  async listMcpServers(signal?: AbortSignal): Promise<McpServer[]> {
    const result = await this.request<{ data: McpServer[] }>('/mcp-servers', {
      signal
    })
    return result.data
  }

  getMcpJsonConfig(signal?: AbortSignal): Promise<McpJsonConfig> {
    return this.request<McpJsonConfig>('/mcp-servers/config', { signal })
  }

  putMcpJsonConfig(
    document: McpJsonDocument,
    signal?: AbortSignal
  ): Promise<McpJsonConfig> {
    return this.request<McpJsonConfig>('/mcp-servers/config', {
      method: 'PUT',
      body: JSON.stringify({ document }),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  async listMcpCatalog(signal?: AbortSignal): Promise<McpCatalogEntry[]> {
    const result = await this.request<{ data: McpCatalogEntry[] }>(
      '/mcp-servers/catalog',
      { signal }
    )
    return result.data
  }

  installMcpCatalog(
    catalogId: string,
    options?: { force?: boolean; signal?: AbortSignal }
  ): Promise<McpServer> {
    const force = Boolean(options?.force)
    const qs = force ? '?force=true' : ''
    return this.request<McpServer>(
      `/mcp-servers/catalog/${encodeURIComponent(catalogId)}/install${qs}`,
      {
        method: 'POST',
        signal: options?.signal
      }
    )
  }

  /** Re-install every missing featured catalog template. */
  resetFeaturedMcpDefaults(signal?: AbortSignal): Promise<{
    installed: string[]
    errors: Array<{ id: string; error: string }>
  }> {
    return this.request('/mcp-servers/catalog/reset-defaults', {
      method: 'POST',
      signal
    })
  }

  connectMcpCatalog(
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string },
    signal?: AbortSignal
  ): Promise<ConnectMcpResult> {
    return this.request<ConnectMcpResult>(
      `/mcp-servers/catalog/${encodeURIComponent(catalogId)}/connect`,
      {
        method: 'POST',
        body: JSON.stringify(input),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  connectMcpServer(
    serverId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string },
    signal?: AbortSignal
  ): Promise<ConnectMcpResult> {
    return this.request<ConnectMcpResult>(
      `/mcp-servers/${encodeURIComponent(serverId)}/connect`,
      {
        method: 'POST',
        body: JSON.stringify(input),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  disconnectMcpCatalog(
    catalogId: string,
    signal?: AbortSignal
  ): Promise<ConnectMcpResult> {
    return this.request<ConnectMcpResult>(
      `/mcp-servers/catalog/${encodeURIComponent(catalogId)}/connect`,
      {
        method: 'DELETE',
        signal
      }
    )
  }

  setMcpCatalogEnabled(
    catalogId: string,
    enabled: boolean,
    signal?: AbortSignal
  ): Promise<ConnectMcpResult> {
    return this.request<ConnectMcpResult>(
      `/mcp-servers/catalog/${encodeURIComponent(catalogId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async validateMcpCatalog(
    catalogId: string,
    signal?: AbortSignal
  ): Promise<ValidateMcpResult> {
    const raw = await this.request<Record<string, unknown>>(
      `/mcp-servers/catalog/${encodeURIComponent(catalogId)}/validate`,
      {
        method: 'POST',
        signal
      }
    )
    return this.normalizeValidateMcp(raw || {})
  }

  async validateMcpServer(
    serverId: string,
    signal?: AbortSignal
  ): Promise<ValidateMcpResult> {
    const raw = await this.request<Record<string, unknown>>(
      `/mcp-servers/${encodeURIComponent(serverId)}/validate`,
      {
        method: 'POST',
        signal
      }
    )
    return this.normalizeValidateMcp(raw || {})
  }

  createMcpServer(
    input: Omit<McpServer, 'id' | 'createdAt' | 'updatedAt'>,
    signal?: AbortSignal
  ): Promise<McpServer> {
    return this.request<McpServer>('/mcp-servers', {
      method: 'POST',
      body: JSON.stringify(input),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  updateMcpServer(
    id: string,
    changes: Partial<
      Omit<McpServer, 'id' | 'transport' | 'createdAt' | 'updatedAt'>
    >,
    signal?: AbortSignal
  ): Promise<McpServer> {
    return this.request<McpServer>(`/mcp-servers/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  async deleteMcpServer(id: string, signal?: AbortSignal): Promise<void> {
    await this.request(`/mcp-servers/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      signal
    })
  }

  async listPtySessions(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<PtySessionInfo[]> {
    const result = await this.request<{ data: PtySessionInfo[] }>(
      `/sessions/${encodeURIComponent(sessionId)}/pty`,
      { signal }
    )
    return result.data
  }

  createPtySession(
    sessionId: string,
    input?: { title?: string; cols?: number; rows?: number; startup?: string },
    signal?: AbortSignal
  ): Promise<PtySessionInfo> {
    return this.request<PtySessionInfo>(
      `/sessions/${encodeURIComponent(sessionId)}/pty`,
      {
        method: 'POST',
        body: JSON.stringify(input || {}),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  updatePtySession(
    sessionId: string,
    ptyId: string,
    input: { title?: string; cols?: number; rows?: number },
    signal?: AbortSignal
  ): Promise<PtySessionInfo> {
    return this.request<PtySessionInfo>(
      `/sessions/${encodeURIComponent(sessionId)}/pty/${encodeURIComponent(
        ptyId
      )}`,
      {
        method: 'PUT',
        body: JSON.stringify(input),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async deletePtySession(
    sessionId: string,
    ptyId: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request(
      `/sessions/${encodeURIComponent(sessionId)}/pty/${encodeURIComponent(
        ptyId
      )}`,
      { method: 'DELETE', signal }
    )
  }

  ptyConnectUrl(sessionId: string, ptyId: string): string {
    const base = this.baseUrl.replace(/^http/, 'ws')
    const url = new URL(
      `${base}/v1/sessions/${encodeURIComponent(
        sessionId
      )}/pty/${encodeURIComponent(ptyId)}/connect`
    )
    if (this.apiKey) url.searchParams.set('token', this.apiKey)
    return url.toString()
  }

  /**
   * FAS-107 X4 Capa 2 · devuelve el "cuaderno visual" del terminal
   * como bytes crudos (Uint8Array). El backend absorbió cada byte que
   * el PTY escupió; ahora lo replay al xterm nuevo. El frontend hace
   * `xterm.resize(currentCols, currentRows)` y después `xterm.write(bytes)`
   * — xterm procesa cada byte con las dims actuales y aplica su reflow
   * interno correctamente, evitando el layout roto que producía el
   * approach anterior con `SerializeAddon`.
   *
   * Devuelve `null` si no hay snapshot (primer uso del terminal).
   */
  async getSessionSnapshot(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<Uint8Array | null> {
    const response = await this.request<{ data: string | null }>(
      `/sessions/${encodeURIComponent(sessionId)}/snapshot`,
      { method: 'GET', signal }
    )
    if (!response.data) return null
    // decode base64 → Uint8Array
    const binary = atob(response.data)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
    }
    return bytes
  }

  /**
   * FAS-107 X4 Capa 2 · fuerza al backend a persistir el `output_log`
   * actual del PTY vivo al disco. Llamado por el frontend al recibir
   * el evento Tauri `sandwalk:force-save-snapshots` (Cmd+Q). Es
   * best-effort — si no hay PTY vivo, no-op.
   */
  async flushSessionSnapshot(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<void> {
    await this.request(
      `/sessions/${encodeURIComponent(sessionId)}/snapshot/flush`,
      { method: 'POST', signal }
    )
  }

  getMemoryOverview(
    scope = 'global',
    signal?: AbortSignal
  ): Promise<MemoryOverview> {
    const params = new URLSearchParams({ scope })
    return this.request<MemoryOverview>(`/memory/overview?${params.toString()}`, {
      method: 'GET',
      signal
    })
  }

  getMemorySettings(signal?: AbortSignal): Promise<MemorySettings> {
    return this.request<MemorySettings>('/memory/settings', {
      method: 'GET',
      signal
    })
  }

  updateMemorySettings(
    changes: Partial<MemorySettings>,
    signal?: AbortSignal
  ): Promise<MemorySettings> {
    return this.request<MemorySettings>('/memory/settings', {
      method: 'PATCH',
      body: JSON.stringify(changes),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  listMemoryEntries(
    scope = 'global',
    includeUser = true,
    signal?: AbortSignal
  ): Promise<MemoryEntryList> {
    const params = new URLSearchParams({
      scope,
      includeUser: String(includeUser)
    })
    return this.request<MemoryEntryList>(`/memory/entries?${params.toString()}`, {
      method: 'GET',
      signal
    })
  }

  createMemoryEntry(
    input: {
      scope?: string
      target?: 'user' | 'memory' | 'project' | 'specialist'
      layer?: 'L1' | 'L2' | 'L3'
      content: string
      tags?: string[]
      pinned?: boolean
    },
    signal?: AbortSignal
  ): Promise<MemoryEntry> {
    return this.request<MemoryEntry>('/memory/entries', {
      method: 'POST',
      body: JSON.stringify(input),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  updateMemoryEntry(
    entryId: string,
    input: {
      content?: string
      tags?: string[]
      pinned?: boolean
    },
    signal?: AbortSignal
  ): Promise<MemoryEntry> {
    return this.request<MemoryEntry>(
      `/memory/entries/${encodeURIComponent(entryId)}`,
      {
        method: 'PATCH',
        body: JSON.stringify(input),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async deleteMemoryEntry(entryId: string, signal?: AbortSignal): Promise<void> {
    await this.request(`/memory/entries/${encodeURIComponent(entryId)}`, {
      method: 'DELETE',
      signal
    })
  }

  async listPendingMemoryWrites(
    scope?: string,
    signal?: AbortSignal
  ): Promise<PendingMemoryWrite[]> {
    const params = new URLSearchParams()
    if (scope) params.set('scope', scope)
    const suffix = params.toString() ? `?${params.toString()}` : ''
    const res = await this.request<{ data: PendingMemoryWrite[] }>(
      `/memory/pending${suffix}`,
      { method: 'GET', signal }
    )
    return res.data
  }

  approvePendingMemoryWrite(
    pendingId: string,
    signal?: AbortSignal
  ): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>(
      `/memory/pending/${encodeURIComponent(pendingId)}/approve`,
      { method: 'POST', signal }
    )
  }

  rejectPendingMemoryWrite(
    pendingId: string,
    signal?: AbortSignal
  ): Promise<{ rejected: boolean }> {
    return this.request<{ rejected: boolean }>(
      `/memory/pending/${encodeURIComponent(pendingId)}/reject`,
      { method: 'POST', signal }
    )
  }

  async listWikiPages(
    scope = 'global',
    signal?: AbortSignal
  ): Promise<WikiPageSummary[]> {
    const params = new URLSearchParams({ scope })
    const res = await this.request<{ data: WikiPageSummary[] }>(
      `/memory/wiki?${params.toString()}`,
      { method: 'GET', signal }
    )
    return res.data
  }

  getWikiPage(
    slug: string,
    scope = 'global',
    signal?: AbortSignal
  ): Promise<WikiPageDetail> {
    const params = new URLSearchParams({ scope })
    return this.request<WikiPageDetail>(
      `/memory/wiki/${encodeURIComponent(slug)}?${params.toString()}`,
      { method: 'GET', signal }
    )
  }

  writeWikiPage(
    slug: string,
    input: {
      scope?: string
      title: string
      content: string
      summary?: string | null
      tags?: string[]
    },
    signal?: AbortSignal
  ): Promise<WikiPageDetail> {
    return this.request<WikiPageDetail>(
      `/memory/wiki/${encodeURIComponent(slug)}`,
      {
        method: 'PUT',
        body: JSON.stringify(input),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  async deleteWikiPage(
    slug: string,
    scope = 'global',
    signal?: AbortSignal
  ): Promise<void> {
    const params = new URLSearchParams({ scope })
    await this.request(
      `/memory/wiki/${encodeURIComponent(slug)}?${params.toString()}`,
      { method: 'DELETE', signal }
    )
  }

  listCookbooks(
    scope = 'global',
    signal?: AbortSignal
  ): Promise<{ data: CookbookSummary[]; activeCookbookId: string }> {
    const params = new URLSearchParams({ scope })
    return this.request<{ data: CookbookSummary[]; activeCookbookId: string }>(
      `/memory/cookbooks?${params.toString()}`,
      { method: 'GET', signal }
    )
  }

  selectCookbook(
    input: {
      scope?: string
      cookbookId: string
      loadDemoSeed?: boolean
    },
    signal?: AbortSignal
  ): Promise<GraphSnapshot> {
    return this.request<GraphSnapshot>('/memory/cookbooks/select', {
      method: 'POST',
      body: JSON.stringify(input),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  getMemoryGraph(
    options?: {
      scope?: string
      branch?: string
      queryName?: string | null
    },
    signal?: AbortSignal
  ): Promise<GraphSnapshot> {
    const params = new URLSearchParams()
    if (options?.scope) params.set('scope', options.scope)
    if (options?.branch) params.set('branch', options.branch)
    if (options?.queryName) params.set('queryName', options.queryName)
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return this.request<GraphSnapshot>(`/memory/graph${suffix}`, {
      method: 'GET',
      signal
    })
  }

  upsertGraphNode(
    input: {
      scope?: string
      branch?: string
      nodeType: string
      slug?: string | null
      name: string
      summary?: string
      tags?: string[]
      sourceRef?: string | null
    },
    signal?: AbortSignal
  ): Promise<GraphNode> {
    return this.request<GraphNode>('/memory/graph/nodes', {
      method: 'POST',
      body: JSON.stringify(input),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  async deleteGraphNode(
    nodeId: string,
    scope = 'global',
    branch = 'main',
    signal?: AbortSignal
  ): Promise<void> {
    const params = new URLSearchParams({ scope, branch })
    await this.request(
      `/memory/graph/nodes/${encodeURIComponent(nodeId)}?${params.toString()}`,
      { method: 'DELETE', signal }
    )
  }

  createGraphClaim(
    input: {
      scope?: string
      branch?: string
      subjectId: string
      subjectType?: string
      subjectName?: string
      predicate: string
      objectId: string
      objectType?: string
      objectName?: string
      polarity: 'support' | 'contradict' | 'neutral'
      summary?: string
      sourceRef?: string | null
    },
    signal?: AbortSignal
  ): Promise<GraphEdge> {
    return this.request<GraphEdge>('/memory/graph/claims', {
      method: 'POST',
      body: JSON.stringify(input),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  manageGraphBranch(
    input: {
      scope?: string
      action: 'create' | 'merge' | 'delete'
      name: string
      targetBranch?: string
    },
    signal?: AbortSignal
  ): Promise<GraphBranch[]> {
    return this.request<GraphBranch[]>('/memory/graph/branches', {
      method: 'POST',
      body: JSON.stringify(input),
      headers: { 'content-type': 'application/json' },
      signal
    })
  }

  distillSession(
    sessionId: string,
    input?: {
      scope?: string | null
      includeWiki?: boolean
      includeGraph?: boolean
    },
    signal?: AbortSignal
  ): Promise<DistillSessionResponse> {
    return this.request<DistillSessionResponse>(
      `/memory/distill/${encodeURIComponent(sessionId)}`,
      {
        method: 'POST',
        body: JSON.stringify(input ?? {}),
        headers: { 'content-type': 'application/json' },
        signal
      }
    )
  }

  getOmnigraphStatus(
    scope = 'global',
    signal?: AbortSignal
  ): Promise<OmnigraphEngineStatus> {
    const params = new URLSearchParams({ scope })
    return this.request<OmnigraphEngineStatus>(
      `/memory/omnigraph/status?${params.toString()}`,
      { method: 'GET', signal }
    )
  }

  installOmnigraph(signal?: AbortSignal): Promise<OmnigraphEngineStatus> {
    return this.request<OmnigraphEngineStatus>('/memory/omnigraph/install', {
      method: 'POST',
      signal
    })
  }

  seedMemoryDemo(
    force = true,
    signal?: AbortSignal
  ): Promise<{ ok: boolean; seededSessions?: string[] }> {
    const params = new URLSearchParams({ force: force ? 'true' : 'false' })
    return this.request<{ ok: boolean; seededSessions?: string[] }>(
      `/memory/demo/seed?${params.toString()}`,
      {
        method: 'POST',
        signal
      }
    )
  }

  syncOmnigraph(
    scope = 'global',
    branch = 'main',
    signal?: AbortSignal
  ): Promise<{ ok: boolean }> {
    const params = new URLSearchParams({ scope, branch })
    return this.request<{ ok: boolean }>(
      `/memory/omnigraph/sync?${params.toString()}`,
      { method: 'POST', signal }
    )
  }
}
