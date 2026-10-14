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
  eventMux?: boolean
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

export type StorageDatabaseProbe = {
  path: string
  exists: boolean
  bytes: number
  walBytes: number
  shmBytes: number
  integrity: string
  pageCount?: number | null
  pageSize?: number | null
  journalMode?: string | null
  sessionCount?: number | null
  messageCount?: number | null
  backupPath?: string | null
  backupBytes: number
  backupIntegrity?: string | null
  autoHealEnabled: boolean
  quarantineCount: number
}

export type StorageReport = {
  location: StorageLocation
  categories: StorageCategory[]
  totalBytes: number
  availableBytes: number
  checkedAt: string
  database?: StorageDatabaseProbe | null
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

export type AgentSessionStatus =
  | 'idle'
  | 'running'
  | 'awaiting_approval'
  | 'interrupted'
  | 'error'

export type HitlDecisionType = 'approve' | 'edit' | 'reject' | 'respond'

export type HitlActionRequest = {
  name: string
  args: Record<string, unknown>
  description?: string | null
}

export type HitlReviewConfig = {
  actionName: string
  allowedDecisions: HitlDecisionType[]
  description?: string | null
}

export type HitlDecision = {
  type: HitlDecisionType
  message?: string
  /** Auto-approve matching skill install/remove calls for the rest of this run. */
  scope?: 'remaining' | 'once'
  editedAction?: {
    name: string
    args: Record<string, unknown>
  }
}

export type PendingHitlApproval = {
  interruptId: string
  runId: string | null
  actionRequests: HitlActionRequest[]
  reviewConfigs: HitlReviewConfig[]
}

export type WidgetSize = 'sm' | 'md' | 'lg'

export type WidgetLayoutItem = {
  id: string
  type: string
  size: WidgetSize
}

export type WidgetLayout = {
  version: number
  widgets: WidgetLayoutItem[]
}

export type AgentProject = {
  id: string
  name: string
  description: string | null
  agentContext: string | null
  folderPath: string | null
  icon: string
  color: string
  pinned: boolean
  homeLayout?: WidgetLayout | null
  sessionCount: number
  createdAt: string
  updatedAt: string
}

export type LibraryKind = 'image' | 'document' | 'structure' | 'code' | 'other'

/** Filesystem file under a project's linked folder (not a Library blob). */
export type ProjectFolderFile = {
  path: string
  name: string
  kind: LibraryKind | string
  size: number | null
  mtime: string | null
}

export type ProjectFolderListing = {
  folderPath: string
  truncated: boolean
  data: ProjectFolderFile[]
}

export type LibraryItem = {
  id: string
  sha256: string
  bytes: number
  mime: string | null
  originalName: string
  displayName: string
  kind: LibraryKind
  originSessionId: string | null
  createdAt: string
  updatedAt: string
}

export type LibraryPagination = {
  page: number
  perPage: number
  total: number
  hasMore: boolean
}

export type LibraryItemList = {
  data: LibraryItem[]
  pagination: LibraryPagination
  /** Sum of `bytes` for the filtered Library set (all pages). */
  totalBytes?: number
}

export type UseLibraryInChatResult = {
  sessionId: string
  paths: string[]
}

export type SiteStatus =
  | 'draft'
  | 'ready'
  | 'publishing'
  | 'published'
  | 'error'

export type SiteDeployment = {
  id: string
  status: 'publishing' | 'published' | 'error'
  slug: string
  publicUrl: string | null
  sizeBytes: number | null
  createdAt: string
  updatedAt: string
  publishedAt: string | null
}

export type Site = {
  id: string
  name: string
  slug: string | null
  status: SiteStatus
  sourceSessionId: string | null
  sourceProjectId: string | null
  sourcePath: string | null
  sizeBytes: number | null
  deployment: SiteDeployment | null
  createdAt: string
  updatedAt: string
}

export type CreateSiteInput = {
  name: string
  sourceSessionId?: string | null
  sourceProjectId?: string | null
  sourcePath?: string | null
  slug?: string | null
}

export type UpdateSiteInput = {
  name?: string
  slug?: string | null
}

export type SitePreviewTicket = {
  url: string
  expiresAt: string | null
}

export interface SiteProvider {
  listSites(options?: {
    q?: string | null
    signal?: AbortSignal
  }): Promise<Site[]>
  createSite(input: CreateSiteInput, signal?: AbortSignal): Promise<Site>
  getSite(siteId: string, signal?: AbortSignal): Promise<Site>
  updateSite(
    siteId: string,
    input: UpdateSiteInput,
    signal?: AbortSignal
  ): Promise<Site>
  deleteSite(siteId: string, signal?: AbortSignal): Promise<void>
  refreshSite(siteId: string, signal?: AbortSignal): Promise<Site>
  createSitePreviewTicket(
    siteId: string,
    signal?: AbortSignal
  ): Promise<SitePreviewTicket>
  publishSite(
    siteId: string,
    input?: { slug?: string | null },
    signal?: AbortSignal
  ): Promise<Site>
}

/** Where an inbound message came from. Display only — the model sees `content`. */
export type MessageSource = {
  connector: 'slack'
  channelId: string
  channelName: string | null
  senderId: string
  senderName: string | null
  senderAvatarUrl?: string | null
  /** Raw text, without the reply-handle framing added for the model. */
  text: string
  permalink?: string | null
}

export type SessionTitleSource = 'pending' | 'auto' | 'user'

/** Coding-agent CLIs Sandwalk can read from, launch, and hand off to. */
export type ExternalAgentKind = 'claude' | 'codex' | 'opencode' | 'fx'

export type SessionSource = 'slack' | 'bench' | 'capy' | ExternalAgentKind

export type ExternalAgentInfo = {
  kind: ExternalAgentKind
  label: string
  installed: boolean
  path: string | null
}

export type ExternalSessionSummary = {
  kind: ExternalAgentKind
  label: string
  id: string
  title: string
  cwd: string | null
  updatedAt: string | null
  turns: number
}

export type ExternalAgentsResponse = {
  agents: ExternalAgentInfo[]
  sessions: ExternalSessionSummary[]
}

export type ExternalLaunchResult = {
  kind: ExternalAgentKind
  command: string
  terminal: TerminalSession
  pty: PtySessionInfo
}

export type HandoffResult = {
  kind: ExternalAgentKind
  path: string
  prompt: string
  workspacePath: string
  messages: number
  native: boolean
  resumeId?: string
  nativePath?: string
  /** Present when `launch` was true. */
  command?: string
  terminal?: TerminalSession
  pty?: PtySessionInfo
}

export type ClientSurface = 'cli' | 'ui' | 'slack' | 'unknown'

export type UsageDayPoint = {
  day: string
  tokens: number
  inputTokens: number
  outputTokens: number
  cacheReadTokens: number
  cliTokens: number
  uiTokens: number
  slackTokens: number
  unknownTokens: number
  runs: number
}

export type UsageModelRow = {
  modelId: string
  provider: string
  tokens: number
  inputTokens: number
  outputTokens: number
  runs: number
  messages: number
}

export type UsageChartModel = {
  modelId: string
  provider: string
}

export type UsageModelDayPoint = {
  day: string
  modelId: string
  provider: string
  tokens: number
}

export type UsageOverview = {
  lifetimeTokens: number
  inputTokens: number
  outputTokens: number
  cacheReadTokens: number
  peakDayTokens: number
  peakDay: string | null
  modelsUsed: number
  runs: number
  sessions: number
  messages: number
  avgTokensPerSession: number
  longestAgentSeconds: number
  longestStreakDays: number
  currentStreakDays: number
  cliTokens: number
  uiTokens: number
  slackTokens: number
  unknownTokens: number
  cliShare: number
  uiShare: number
  days: UsageDayPoint[]
  topModels: UsageModelRow[]
  /** Last-30-day stacked chart series (day × model). */
  modelDays: UsageModelDayPoint[]
  /** Stable model order for chart colors. */
  chartModels: UsageChartModel[]
  backfilled: boolean
}

/** relay = inbound via FastFold Cloud; socket = inbound via Slack Socket Mode. */
export type SlackMode = 'relay' | 'socket'

export type SlackRelayState =
  | 'off'
  | 'signed_out'
  | 'auth_expired'
  | 'reconnecting'
  | 'live'

export type SlackWorkspace = {
  teamId: string
  teamName: string | null
  domain: string | null
  mode: SlackMode
  botUserId: string | null
  connectionId: string | null
  assistantEnabled: boolean
  enabled: boolean
  /** Actually receiving mentions right now, not just "enabled". */
  live: boolean
  /** Tokens are never returned; these only report whether one is stored. */
  hasBotToken: boolean
  hasAppToken: boolean
  /** An outbound Slack call recently failed with an auth error (e.g. the bot
   * token was rotated by a reinstall) — distinct from `live`, which only
   * reflects the inbound socket/relay connection. */
  needsReauth: boolean
  createdAt: string
  updatedAt: string
}

export type SlackConnectorStatus = {
  mode: SlackMode | null
  relayState: SlackRelayState
  relayDetail: string | null
  workspaces: SlackWorkspace[]
}

export type SlackAllowedUser = {
  teamId: string
  slackUserId: string
  displayName: string | null
  createdAt: string
}

export type SlackSubscription = {
  sessionId: string
  channel: string
  createdAt: string
}

export type SlackParkedMessage = {
  id: string
  teamId: string
  channel: string
  threadTarget: string | null
  slackUserId: string
  userName: string | null
  text: string
  createdAt: string
}

export type SlackDirectoryPerson = {
  id: string
  name: string
  handle: string | null
  avatarUrl: string | null
}

export type SlackDirectoryChannel = {
  id: string
  name: string
  isPrivate: boolean
}

export type SlackDirectory = {
  people: SlackDirectoryPerson[]
  channels: SlackDirectoryChannel[]
}

export type SlackManifest = {
  appName: string
  manifest: string
  steps: string[]
}

export type SessionConnectorMute = {
  sessionId: string
  connector: 'slack'
  muted: boolean
}

export type AgentSession = {
  id: string
  title: string
  /** pending = still eligible for auto-title; auto = model-generated; user = renamed */
  titleSource?: SessionTitleSource
  status: AgentSessionStatus
  organizeLabel: 'pinned' | 'archive' | null
  projectId: string | null
  specialistId: string | null
  sandboxBackend?: 'builtin' | 'modal' | null
  /** Per-chat model; null/undefined falls back to global runtime settings. */
  provider?: string | null
  model?: string | null
  openaiProfileId?: string | null
  workspacePath: string | null
  /** Connector that spawned the session; null when it started locally. */
  source?: SessionSource | null
  /** Human-readable origin, e.g. "#dev-ops · Acme". */
  sourceLabel?: string | null
  /** Product surface for usage attribution. */
  clientSurface?: ClientSurface
  lastMessageAt: string | null
  createdAt: string
  updatedAt: string
}

/**
 * A tab-strip group that contains N chat sessions displayed side by side in a
 * split view. Behaves like a "virtual tab" — has its own name, color, and pin,
 * and lives in the tab strip alongside solo tabs. The chatIds are the sessions
 * that live INSIDE this group (they no longer appear in the strip as solo tabs
 * while inside the group; on dissolve they come back).
 *
 * Persisted client-side (localStorage) as a UI preference — not on the backend.
 */
/**
 * Kind discriminator for every "thing that can appear in a tab or split".
 * Chat and Terminal ship in FAS-107; files/preview/structure are the
 * planned next entrants and slot into the same union.
 */
export type WorkspaceItemKind = 'chat' | 'terminal'

/**
 * Lightweight typed pointer stored in tab strip / split groups / tiling
 * leaves. Cheap to list and easy to narrow. Precedent: VSCode's
 * `Tab.input: TabInputText | TabInputTerminal | TabInputWebview | ...`.
 */
export type WorkspaceItemRef =
  | { kind: 'chat'; id: string }
  | { kind: 'terminal'; id: string }

/**
 * Row from the `workspace_items` denormalized index — the tab strip /
 * sidebar / split picker query this shape and then hydrate per-kind
 * detail (title, model, cwd) on demand from the kind's own endpoint.
 */
export type WorkspaceItem = {
  id: string
  kind: WorkspaceItemKind
  projectId: string | null
  organizeLabel: 'pinned' | 'archive' | null
  title: string
  updatedAt: string
}

/**
 * Terminal-as-first-class-item (FAS-107). Peer of `AgentSession`. The
 * live PTY (fd, buffer, WebSocket subscribers) is held in the server's
 * `PtyManager` on top of this metadata row.
 */
export type TerminalSession = {
  id: string
  title: string
  titleSource: SessionTitleSource
  projectId: string | null
  workspacePath: string | null
  shell: string | null
  /** Set when the terminal was opened from a chat's side-panel. */
  originChatId: string | null
  /**
   * Stable identity for user-assigned color / rename across shell
   * respawns in the same cwd. Precedent: WezTerm's `pane_id` vs pane
   * role split — the ephemeral id changes when a shell dies but the
   * slot_key stays the same so color/name follow.
   */
  slotKey: string | null
  status: 'idle' | 'running' | 'detached' | 'exited'
  /**
   * FAS-107 paridad-con-chat: `'pinned'` / `'archive'` / null — same
   * shape as `AgentSession.organizeLabel` so pin/archive work
   * end-to-end without depending on the workspace_items denormalization.
   */
  organizeLabel: 'pinned' | 'archive' | null
  lastActivityAt: string | null
  createdAt: string
  updatedAt: string
  /**
   * UI-only: the coding-agent CLI currently in the foreground of this
   * terminal's PTY (from `PtySessionInfo.agent` / the `agent.changed`
   * PTY event). Not persisted on the row.
   */
  agent?: ExternalAgentKind | null
}

/**
 * Tiling tree used for the split-view layout (Warp / iTerm2 pattern).
 * A leaf holds a chatId or a terminalId (or a generic typed `ref`, used
 * by new layouts); a branch splits its content horizontally or
 * vertically among N children whose `ratios` sum to 1.0. Stored
 * per-monitor so a docked 4K layout doesn't dictate the shape on a
 * MacBook 13".
 *
 * The `type: 'chat'` leaf is kept for backwards-compat with layouts
 * persisted before FAS-107 — new writes use `type: 'ref'`.
 */
export type PaneNode =
  | { type: 'chat'; chatId: string }
  | { type: 'terminal'; terminalId: string }
  | { type: 'ref'; ref: WorkspaceItemRef }
  | {
      type: 'branch'
      direction: 'horizontal' | 'vertical'
      ratios: number[]
      children: PaneNode[]
    }

export type SessionGroup = {
  /** Prefixed id: `grp_<random>` so it never collides with session ids. */
  id: string
  name: string
  /** Same palette as the tab color tag; null = no color. */
  color: string | null
  pinned: boolean
  /**
   * FAS-107 X5.2: renombrado de `chatIds` a `itemIds`. Guarda ids de
   * chats Y terminales (posiblemente más tipos en el futuro). El nombre
   * anterior engañaba — cada consumidor asumía "solo chats" y escribía
   * código que olvidaba terminales, patrón que produjo 5+ bugs.
   *
   * Migración de datos: `readTabGroups` en `app-storage.ts` promueve
   * `chatIds` legacy a `itemIds` al leer del localStorage.
   *
   * TODO futuro (X5.3): reemplazar por `items: WorkspaceItemRef[]`
   * con tipo discriminado explícito (`{ kind, id }`).
   */
  itemIds: string[]
  /** Typed members (FAS-107). Contains a superset of `itemIds`. */
  items?: WorkspaceItemRef[]
  /** Which item (chat/terminal) inside the split has focus. */
  activeChatId: string
  /**
   * Pending group: recién creado desde "Create split view", todavía sólo
   * tiene 1 chatId (el de origen). El segundo panel se pinta como picker
   * hasta que el usuario elige el chat compañero. Al elegirlo, el flag
   * se limpia y el grupo pasa a ser un split real de 2+ chats.
   */
  isPending?: boolean
  /**
   * Tiling tree persisted per-monitor. Missing = group renders with a
   * generated default (a single horizontal branch with all chats as
   * siblings, equal ratios). Key is a monitor fingerprint like
   * `1920x1080@2` — different screens keep independent layouts so the
   * user's careful 4K arrangement doesn't dictate the shape on a laptop.
   */
  layout?: {
    perMonitor: Record<string, PaneNode>
  }
}

/** True for tab-strip ids that identify a group instead of a chat session. */
export function isSessionGroupId(id: string): boolean {
  return id.startsWith('grp_')
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
  /** Present when the message arrived through a connector, e.g. Slack. */
  source?: MessageSource | null
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
  | EventEnvelope<
      'session.created' | 'session.updated',
      { session: AgentSession }
    >
  | EventEnvelope<'run.started', { messageId: string }>
  | EventEnvelope<'assistant.delta', { delta: string }>
  | EventEnvelope<'assistant.message', { message: AgentMessage }>
  | EventEnvelope<
      'tool.started',
      { name: string; arguments: unknown; toolCallId: string }
    >
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
      'plan.created',
      { path: string; title: string; summary: string }
    >
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
  | EventEnvelope<
      'run.awaiting_approval',
      {
        runId?: string
        interruptId: string
        actionRequests: HitlActionRequest[]
        reviewConfigs: HitlReviewConfig[]
      }
    >
  | EventEnvelope<
      'run.approval_resolved',
      {
        interruptId?: string
        decisions: HitlDecision[]
      }
    >

export type IntegrationUnlock = {
  kind: 'tool' | 'skill' | 'capability' | 'notice'
  id: string
  label: string
  description: string
  source: string | null
  requirement: 'built_in' | 'install' | 'connector' | 'ambient' | 'not_wired'
  installable: boolean
  installed: boolean | null
  statusDetail: string | null
}

/** Sign in with ChatGPT connection state (server never sends tokens). */
export type ChatGPTAuthStatus = {
  connected: boolean
  email: string | null
  planUsage: boolean
  expiresAt: number | null
}

export type ChatGPTAuthStart = {
  url: string
  state: string
}

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
    updatedAt: string | null
  }>
  unlocks: IntegrationUnlock[]
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
    signal?: AbortSignal
  ): Promise<IntegrationSummary>
  removeIntegration(
    key: string,
    signal?: AbortSignal
  ): Promise<IntegrationSummary>
  autofillIntegration(
    key: string,
    signal?: AbortSignal
  ): Promise<IntegrationSummary>
  installIntegrationCapability(
    key: string,
    capabilityId: string,
    signal?: AbortSignal
  ): Promise<IntegrationSummary>
  setupIntegration(
    key: string,
    workingDirectory?: string | null,
    signal?: AbortSignal
  ): Promise<IntegrationSetupResult>
  validateIntegration(
    key: string,
    signal?: AbortSignal
  ): Promise<{ ok: boolean; message: string }>
  /** Fetch the stored secret for local reveal/copy (user opt-in). */
  revealIntegrationSecret(
    key: string,
    signal?: AbortSignal
  ): Promise<{ configured: boolean; envVar: string; value: string }>
}

export type RuntimeSettings = {
  provider: string
  model: string
  openaiBaseUrl: string | null
  /** Active OpenAI-compatible profile id (local oMLX/Ollama/… or openai_cloud). */
  openaiProfileId?: string | null
  agentProfile: string
  toolMode: string
  /** Always-on prompt / Deep Agents surface: low | medium | high. */
  knowledgeLevel?: 'low' | 'medium' | 'high' | string
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
  /** True = Plan mode (author plans/*.md); false = Agent mode. */
  planMode?: boolean
  /**
   * Agent file-access policy:
   * - "project": workspace + linked project folder only (default, safe).
   * - "full": anywhere on the host filesystem (opt-in, higher risk).
   */
  fileAccess?: 'project' | 'full'
}

export type AgentPlanCard = {
  path: string
  title: string
  summary: string
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
  status:
    | 'ready'
    | 'running'
    | 'stopped'
    | 'unavailable'
    | 'starting'
    | 'stopping'
    | string
  providerSandboxName: string | null
  modalConfigured: boolean
  computeType: string
  gpuClass: string
  cpuCores: number
  ramGb: number
  cpuImage: string
  gpuImage?: string
  /** Active base image for the current compute mode (CPU or GPU). */
  baseImage?: string
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
  /** False when Fast (thinking off) is rejected — e.g. Muse Spark. */
  supportsReasoningFast?: boolean
  reasoningEffortOptions?: string[]
  /** Per-model effort level (low|medium|high). */
  reasoningEffort?: string | null
  /** Per-model Fast toggle. */
  reasoningFast?: boolean
  /** Multimodal user-input capabilities (image / PDF / audio / video content blocks). */
  supportsImageInputs?: boolean
  supportsPdfInputs?: boolean
  supportsAudioInputs?: boolean
  supportsVideoInputs?: boolean
  /** Effective context window when known (e.g. oMLX max_model_len). */
  contextWindow?: number | null
}

export type CreateAgentModelInput = {
  id: string
  provider?: string
  label?: string | null
}

export type ModelPreferences = {
  favorites: string[]
  recent: string[]
}

export type ToggleModelFavoriteInput = {
  provider?: string | null
  model: string
  profileId?: string | null
}

export type ToggleModelFavoriteResult = {
  favorite: boolean
  favorites: string[]
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
    signal?: AbortSignal
  ): Promise<RuntimeSettings>
  getOnboardingSettings?(signal?: AbortSignal): Promise<OnboardingSettings>
  updateOnboardingSettings?(
    changes: Partial<OnboardingSettings>,
    signal?: AbortSignal
  ): Promise<OnboardingSettings>
  getSandboxSettings?(signal?: AbortSignal): Promise<SandboxSettings>
  updateSandboxSettings?(
    changes: Partial<SandboxSettings>,
    signal?: AbortSignal
  ): Promise<SandboxSettings>
  probeSandboxSettings?(signal?: AbortSignal): Promise<SandboxProbeReport>
  getAccount?(options?: {
    checkUpdates?: boolean
    signal?: AbortSignal
  }): Promise<AccountSummary>
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
  /** False for registry core tools — always on; UI locks the toggle. */
  toggleable?: boolean
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

export type PromptBudgetTokenCountMethod = 'tiktoken' | 'provider'

export type PromptBudgetResponse = {
  totalTokens: number
  totalChars: number
  tokenizer: string
  toolMode: string
  knowledgeLevel?: 'low' | 'medium' | 'high' | string
  tokenCountMethod?: PromptBudgetTokenCountMethod | string
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
    signal?: AbortSignal
  ): Promise<DatasetInstallResult>
  removeDataset(
    datasetId: string,
    signal?: AbortSignal
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
    signal?: AbortSignal
  ): Promise<ToolSummary>
  batchUpdateTools(
    action: ToolBatchAction,
    ids: string[],
    signal?: AbortSignal
  ): Promise<ToolBatchResult>
}

export interface ModelsProvider {
  listModels(options?: {
    enabledOnly?: boolean
    discover?: boolean
    signal?: AbortSignal
  }): Promise<AgentModel[]>
  getModelPreferences?(signal?: AbortSignal): Promise<ModelPreferences>
  toggleModelFavorite?(
    input: ToggleModelFavoriteInput,
    signal?: AbortSignal
  ): Promise<ToggleModelFavoriteResult>
  createCustomModel?(
    input: CreateAgentModelInput,
    signal?: AbortSignal
  ): Promise<AgentModel>
  deleteCustomModel?(modelId: string, signal?: AbortSignal): Promise<void>
  updateModelEnabled(
    modelId: string,
    enabled: boolean,
    signal?: AbortSignal,
    provider?: string | null
  ): Promise<AgentModel>
  listModelProfiles(options?: {
    includeCloud?: boolean
    signal?: AbortSignal
  }): Promise<ModelProfile[]>
  createModelProfile(
    input: UpsertModelProfileInput,
    signal?: AbortSignal
  ): Promise<ModelProfile>
  updateModelProfile(
    profileId: string,
    input: UpsertModelProfileInput,
    signal?: AbortSignal
  ): Promise<ModelProfile>
  deleteModelProfile(profileId: string, signal?: AbortSignal): Promise<void>
  /** Fetch the stored Local LLM API key for reveal/copy (user opt-in). */
  revealModelProfileSecret?(
    profileId: string,
    signal?: AbortSignal
  ): Promise<{ configured: boolean; value: string }>
  probeModelProfile(
    profileId: string,
    signal?: AbortSignal
  ): Promise<ModelProfileProbeResult>
  discoverModelEndpoint?(
    input: DiscoverModelEndpointInput,
    signal?: AbortSignal
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
  /** Cached tools/list count when enabled (from last successful probe). */
  toolCount?: number | null
  /** Write-only on create/update — never returned by the API. */
  headers?: Record<string, string> | null
  createdAt: string
  updatedAt: string
}

export type McpCatalogEntry = {
  id: string
  name: string
  description: string
  url: string | null
  transport: 'stdio' | 'sse' | 'streamable_http'
  authMode: 'oauth' | 'api_key' | 'api_key_or_oauth' | 'none'
  preferredAuth: 'oauth' | 'api_key'
  apiKeyEnvVar: string | null
  docsUrl: string | null
  setupUrl: string | null
  integrationKey: string | null
  /** Featured cards (dashboard / onboarding). Non-featured stay in the full MCP list. */
  featured?: boolean
  defaultEnabled: boolean
  configured: boolean
  authMethod: 'oauth' | 'api_key' | 'local' | null
  /** Masked API key preview when a secret is stored (e.g. ``ns_…abcd``). */
  maskedPreview?: string | null
  enabled: boolean
  serverId: string | null
  connected: boolean
  toolCount?: number | null
  statusMessage?: string | null
  command?: string | null
  args?: string[]
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

/** mcp.json document (`{ mcpServers: { ... } }`). */
export type McpJsonDocument = {
  mcpServers: Record<string, Record<string, unknown>>
}

export type McpJsonConfig = {
  path: string
  document: McpJsonDocument
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
  /** Coding-agent CLI detected in the foreground, if any. */
  agent?: ExternalAgentKind | null
  agentCwd?: string | null
}

export interface McpProvider {
  listMcpServers(signal?: AbortSignal): Promise<McpServer[]>
  listMcpCatalog(signal?: AbortSignal): Promise<McpCatalogEntry[]>
  /** Re-add a removed catalog template to the installed list. */
  installMcpCatalog?(
    catalogId: string,
    options?: { force?: boolean; signal?: AbortSignal }
  ): Promise<McpServer>
  /** Re-install all missing featured catalog templates. */
  resetFeaturedMcpDefaults?(signal?: AbortSignal): Promise<{
    installed: string[]
    errors: Array<{ id: string; error: string }>
  }>
  connectMcpCatalog(
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string },
    signal?: AbortSignal
  ): Promise<ConnectMcpResult>
  connectMcpServer?(
    serverId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string },
    signal?: AbortSignal
  ): Promise<ConnectMcpResult>
  disconnectMcpCatalog(
    catalogId: string,
    signal?: AbortSignal
  ): Promise<ConnectMcpResult>
  setMcpCatalogEnabled(
    catalogId: string,
    enabled: boolean,
    signal?: AbortSignal
  ): Promise<ConnectMcpResult>
  validateMcpCatalog(
    catalogId: string,
    signal?: AbortSignal
  ): Promise<ValidateMcpResult>
  validateMcpServer(
    serverId: string,
    signal?: AbortSignal
  ): Promise<ValidateMcpResult>
  getMcpJsonConfig?(signal?: AbortSignal): Promise<McpJsonConfig>
  putMcpJsonConfig?(
    document: McpJsonDocument,
    signal?: AbortSignal
  ): Promise<McpJsonConfig>
  createMcpServer(
    input: Omit<McpServer, 'id' | 'createdAt' | 'updatedAt'>,
    signal?: AbortSignal
  ): Promise<McpServer>
  updateMcpServer(
    id: string,
    changes: Partial<
      Omit<McpServer, 'id' | 'transport' | 'createdAt' | 'updatedAt'>
    >,
    signal?: AbortSignal
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
  category?: string
  version: string | null
  updatedAt: string | null
  iconSrc: string | null
  enabled: boolean
  commit?: string | null
  updateAvailable?: boolean
  latestVersion?: string | null
  updateChannel?: 'release' | 'commit' | string | null
  hasRuntimeDeps?: boolean
  depsStatus?: string | null
}

export type AgentSkillDetail = AgentSkill & {
  content: string
  directory: string | null
}

export type AgentSkillDepCheck = {
  name: string
  status: string
  detail: string
  fix?: string
}

export type AgentSkillDepSetupStep = {
  title: string
  body: string
}

export type AgentSkillDepsStatus = {
  adapterId: string
  skillName: string
  status: string
  summary: string
  command?: string
  hasRuntimeDeps?: boolean
  checks: AgentSkillDepCheck[]
  setupSteps: AgentSkillDepSetupStep[]
}

export type AgentSkillDepsInstallResult = {
  ok: boolean
  summary: string
  status: AgentSkillDepsStatus | null
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

export type AgentCatalogLeaderboardView = 'all-time' | 'trending' | 'hot'

export type AgentCatalogLeaderboard = {
  data: AgentCatalogSkill[]
  view: AgentCatalogLeaderboardView | string
  page: number
  perPage: number
  /** Unique ranked skills (API pagination.total). */
  total: number
  /** Homepage All Time badge — e.g. 986330. */
  allTimeTotal: number
  hasMore: boolean
  count: number
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
  /** skills.sh page Summary (rich markdown), not SKILL.md description. */
  summary?: string | null
  githubStars?: number | null
  firstSeen?: string | null
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
  listSkillCatalogLeaderboard?(
    options?: {
      view?: AgentCatalogLeaderboardView
      page?: number
      perPage?: number
    },
    signal?: AbortSignal
  ): Promise<AgentCatalogLeaderboard>
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
  getSkillDeps?(
    name: string,
    signal?: AbortSignal
  ): Promise<AgentSkillDepsStatus>
  doctorSkillDeps?(
    name: string,
    signal?: AbortSignal
  ): Promise<AgentSkillDepsStatus>
  installSkillDeps?(
    name: string,
    options?: { force?: boolean },
    signal?: AbortSignal
  ): Promise<AgentSkillDepsInstallResult>
}

export interface FileProvider {
  listFiles(sessionId: string, signal?: AbortSignal): Promise<WorkspaceFile[]>
  readFile(
    sessionId: string,
    path: string,
    signal?: AbortSignal
  ): Promise<WorkspaceFileContent>
  writeFile(
    sessionId: string,
    input: {
      path: string
      content: string
      encoding?: 'text' | 'base64'
      baseVersion?: string | null
    },
    signal?: AbortSignal
  ): Promise<FileWriteResult>
  uploadFile(
    sessionId: string,
    file: File,
    relativeDirectory?: string,
    signal?: AbortSignal
  ): Promise<WorkspaceFileContent>
  createFolder(
    sessionId: string,
    path: string,
    signal?: AbortSignal
  ): Promise<void>
  moveFile(
    sessionId: string,
    sourcePath: string,
    targetPath: string,
    signal?: AbortSignal
  ): Promise<void>
  deleteFile(
    sessionId: string,
    path: string,
    recursive?: boolean,
    signal?: AbortSignal
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
      | { scope?: 'full' | 'core'; signal?: AbortSignal }
  ): Promise<DoctorReport>
  getStorage?(signal?: AbortSignal): Promise<StorageReport>
  getEnvironment?(signal?: AbortSignal): Promise<EnvironmentReport>
  installEnvironmentPackage?(
    name: string,
    options?: { allowUnlisted?: boolean; signal?: AbortSignal }
  ): Promise<EnvironmentPackageMutationResult>
  uninstallEnvironmentPackage?(
    name: string,
    signal?: AbortSignal
  ): Promise<EnvironmentPackageMutationResult>
  downloadDiagnostics?(
    uiDiagnostics?: Record<string, unknown> | null,
    signal?: AbortSignal
  ): Promise<{ blob: Blob; filename: string }>
  listSessions(options?: {
    projectId?: string | null
    signal?: AbortSignal
  }): Promise<AgentSession[]>
  getSessionsRevision?(signal?: AbortSignal): Promise<string>
  listProjects?(signal?: AbortSignal): Promise<AgentProject[]>
  listLibrary?(options?: {
    kind?: LibraryKind | null
    q?: string | null
    projectId?: string | null
    page?: number
    perPage?: number
    signal?: AbortSignal
  }): Promise<LibraryItemList>
  uploadLibraryFile?(file: File, signal?: AbortSignal): Promise<LibraryItem>
  updateLibraryItem?(
    itemId: string,
    input: { displayName: string },
    signal?: AbortSignal
  ): Promise<LibraryItem>
  deleteLibraryItem?(itemId: string, signal?: AbortSignal): Promise<void>
  useLibraryInChat?(
    input: {
      itemIds: string[]
      projectId?: string | null
      title?: string | null
    },
    signal?: AbortSignal
  ): Promise<UseLibraryInChatResult>
  getLibraryContentUrl?(itemId: string): string
  fetchLibraryContent?(itemId: string, signal?: AbortSignal): Promise<Blob>
  readLibraryFile?(
    itemId: string,
    signal?: AbortSignal
  ): Promise<WorkspaceFileContent>
  writeLibraryFile?(
    itemId: string,
    input: { content: string; encoding?: 'text' | 'base64' },
    signal?: AbortSignal
  ): Promise<WorkspaceFileContent>
  listSpecialists?(signal?: AbortSignal): Promise<Specialist[]>
  getSpecialist?(
    specialistId: string,
    signal?: AbortSignal
  ): Promise<Specialist>
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
    signal?: AbortSignal
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
    signal?: AbortSignal
  ): Promise<Specialist>
  getPromptBudget?(
    options?: {
      specialistId?: string | null
      projectId?: string | null
      sampleQuery?: string | null
      tokenCountMethod?: PromptBudgetTokenCountMethod | string | null
    },
    signal?: AbortSignal
  ): Promise<PromptBudgetResponse>
  deleteSpecialist?(specialistId: string, signal?: AbortSignal): Promise<void>
  createProject?(
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
  ): Promise<AgentProject>
  updateProject?(
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
  ): Promise<AgentProject>
  listProjectFolderFiles?(
    projectId: string,
    signal?: AbortSignal
  ): Promise<ProjectFolderListing>
  readProjectFolderFile?(
    projectId: string,
    path: string,
    signal?: AbortSignal
  ): Promise<WorkspaceFileContent>
  renameProjectFolderFile?(
    projectId: string,
    path: string,
    name: string,
    signal?: AbortSignal
  ): Promise<ProjectFolderFile>
  deleteProjectFolderFile?(
    projectId: string,
    path: string,
    signal?: AbortSignal
  ): Promise<void>
  useProjectFolderInChat?(
    projectId: string,
    input: { paths: string[]; title?: string | null },
    signal?: AbortSignal
  ): Promise<{ sessionId: string; paths: string[] }>
  deleteProject?(projectId: string, signal?: AbortSignal): Promise<void>
  searchSessions(query: string, signal?: AbortSignal): Promise<AgentSession[]>
  createSession(
    input: {
      title?: string
      workspacePath?: string | null
      projectId?: string | null
      specialistId?: string | null
      sandboxBackend?: 'builtin' | 'modal' | null
      clientSurface?: ClientSurface
    },
    signal?: AbortSignal
  ): Promise<AgentSession>
  getUsageOverview?(
    signalOrOpts?:
      | AbortSignal
      | { projectId?: string | null; signal?: AbortSignal }
  ): Promise<UsageOverview>
  getDashboardLayout?(signal?: AbortSignal): Promise<WidgetLayout>
  updateDashboardLayout?(
    layout: WidgetLayout,
    signal?: AbortSignal
  ): Promise<WidgetLayout>
  updateSession(
    sessionId: string,
    input: {
      title?: string
      organizeLabel?: 'pinned' | 'archive' | null
      projectId?: string | null
      specialistId?: string | null
      sandboxBackend?: 'builtin' | 'modal' | null
    },
    signal?: AbortSignal
  ): Promise<AgentSession>
  getSessionSandbox?(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<SessionSandboxStatus>
  sandboxStreamUrl?(sessionId: string): string
  startSessionSandbox?(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<SessionSandboxStatus>
  stopSessionSandbox?(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<SessionSandboxStatus>
  restartSessionSandbox?(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<SessionSandboxStatus>
  autoTitleSession(
    sessionId: string,
    input?: { force?: boolean },
    signal?: AbortSignal
  ): Promise<AgentSession>
  compactSession?(
    sessionId: string,
    input?: { instructions?: string | null },
    signal?: AbortSignal
  ): Promise<{ turnsBefore: number; turnsAfter: number; summary: string }>
  deleteSession(sessionId: string, signal?: AbortSignal): Promise<void>
  listMessages(sessionId: string, signal?: AbortSignal): Promise<AgentMessage[]>
  listEventHistory(
    sessionId: string,
    signal?: AbortSignal
  ): Promise<AgentEvent[]>
  setMessageFeedback(
    sessionId: string,
    messageId: string,
    reaction: 'up' | 'down' | null,
    signal?: AbortSignal
  ): Promise<void>
  sendMessage(
    sessionId: string,
    content: string,
    signal?: AbortSignal
  ): Promise<{ runId: string }>
  interrupt(sessionId: string, signal?: AbortSignal): Promise<boolean>
  submitApprovals?(
    sessionId: string,
    decisions: HitlDecision[],
    options?: { interruptId?: string | null; signal?: AbortSignal }
  ): Promise<{ accepted: boolean; interruptId?: string | null }>
  streamEvents(
    sessionId: string,
    options: {
      afterSequence?: number
      signal?: AbortSignal
      onEvent: (event: AgentEvent) => void
    }
  ): Promise<void>
}
