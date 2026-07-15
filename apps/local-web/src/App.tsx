import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentEvent,
  AgentProject,
  AgentSession,
  AgentSkill,
  AgentSkillDetail,
  BackendHealth,
  IntegrationSummary,
  McpCatalogEntry,
  McpServer,
  RuntimeSettings,
  SandboxSettings,
  SessionSandboxStatus,
  Specialist,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import {
  Archive,
  ArrowDown,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  Folder,
  LayoutDashboard,
  Loader2,
  MoreHorizontal,
  PanelLeft,
  PanelRight,
  Pin,
  Search,
  Send,
  SquareTerminal,
  Terminal,
  Trash2,
  X
} from 'lucide-react'
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState
} from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import { matchPath, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import {
  Composer,
  type SandboxActionPhase
} from '@/components/agents/Composer'
import {
  composerToMessage,
  fileChipToken
} from '@/components/agents/composer-parts'
import {
  type DashboardSection,
  DashboardSidebar
} from '@/components/agents/DashboardSidebar'
import {
  GlobalSearchDialog,
  useGlobalSearchHotkey
} from '@/components/agents/GlobalSearchDialog'
import { LoginView } from '@/components/agents/LoginView'
import { OnboardingWizardHost } from '@/components/agents/OnboardingWizardHost'
import {
  clampOnboardingStep,
  isOnboardingPath,
  ONBOARDING_MAX_STEP,
  onboardingPath,
  onboardingStepDef,
  onboardingStepFromSlug
} from '@/lib/onboarding'
import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { NewProjectDialog } from '@/components/agents/NewProjectDialog'
import {
  ChatPageSkeleton,
  DashboardPageSkeleton,
  type DashboardSkeletonKind,
  DetailPageSkeleton
} from '@/components/agents/PageSkeletons'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { ProjectSelector } from '@/components/agents/ProjectSelector'
import { ProjectSettingsDialog } from '@/components/agents/ProjectSettingsDialog'
import { QueuedMessages } from '@/components/agents/QueuedMessages'
import { ReasoningGhost } from '@/components/agents/ReasoningGhost'
import { SessionActionsMenu } from '@/components/agents/SessionActionsMenu'
import { SessionStatusIcon } from '@/components/agents/SessionStatusIcon'
import { SessionTabs } from '@/components/agents/SessionTabs'
import { SidebarUserMenu } from '@/components/agents/SidebarUserMenu'
import { TodoListInline } from '@/components/agents/TodoListInline'
import { ToolCard, type TranscriptTool } from '@/components/agents/ToolCard'
import {
  buildConversationTimeline,
  formatSessionExportMarkdown,
  thoughtDurationForTools,
  TOOL_RUN_VISIBLE_COUNT
} from '@/components/agents/transcript'
import { UserMessageContent } from '@/components/agents/UserMessageContent'
import { WorkspacePanel } from '@/components/agents/WorkspacePanel'
import { AppErrorBoundary } from '@/components/AppErrorBoundary'
import { ErrorPage } from '@/components/ErrorPage'
import {
  isAuthCredentialError,
  isBackendUnavailableError,
  normalizeAppError
} from '@/lib/app-error'
import { SandwalkMark } from '@/components/SandwalkMark'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import {
  FILES_PANEL_COLLAPSED_STORAGE_KEY,
  projectTabsKey,
  readCollapsedSidebarSections,
  readLastSessionByScope,
  readOpenTabsByProject,
  readProjectScopeId,
  readRecentProjectIds,
  SESSION_PANELS_AUTO_SAVE_ID,
  SHELL_PANELS_AUTO_SAVE_ID,
  SIDEBAR_COLLAPSED_STORAGE_KEY,
  TERMINAL_OPEN_STORAGE_KEY,
  writeCollapsedSidebarSections,
  writeLastSessionByScope,
  writeOpenTabsByProject,
  writeProjectScopeId,
  writeRecentProjectIds
} from '@/lib/app-storage'
import {
  loginPathWithNext,
  nextFromSearch,
  sanitizeAuthReturnTo
} from '@/lib/auth-routing'
import {
  type ComposerModelOption,
  toComposerModelOptions
} from '@/lib/composer-models'
import {
  AUTO_TITLE_FIRST_RESPONSE_THRESHOLD,
  downloadMarkdown,
  emptySessionChatState,
  formatMessagePopoverDate,
  groupSessions,
  isLowSignalTitle,
  relativeTime,
  type SessionChatState,
  visibleSessionIds
} from '@/lib/sessions'
import {
  catalogSkillDetailPath,
  cloudAccountDisplayName,
  parseCatalogSkillId,
  type SkillsViewMode
} from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

async function validateIntegrationOrProbeModal(
  client: LocalAgentClient,
  key: string
): Promise<{ ok: boolean; message: string }> {
  if (key === 'modal') {
    try {
      const report = await client.probeSandboxSettings()
      const failed = report.steps.find(step => !step.ok)
      return {
        ok: report.ok,
        message: report.ok
          ? 'Modal sandbox probe passed.'
          : failed?.detail || 'Modal sandbox probe failed.'
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      const missingProbe =
        /\/v1\/settings\/sandbox\/probe/i.test(message) &&
        /\b404\b|not found/i.test(message)
      return {
        ok: false,
        message: missingProbe
          ? 'Probe endpoint missing on this agent server. Restart sandwalk / `sandwalk serve` after updating the CLI, then retry.'
          : message
      }
    }
  }
  return client.validateIntegration(key)
}

const AgentRuntimeView = lazy(() =>
  import('@/components/agents/AgentRuntimeView').then(m => ({
    default: m.AgentRuntimeView
  }))
)
const AgentPromptsView = lazy(() =>
  import('@/components/agents/AgentPromptsView').then(m => ({
    default: m.AgentPromptsView
  }))
)
const AgentSandboxView = lazy(() =>
  import('@/components/agents/AgentSandboxView').then(m => ({
    default: m.AgentSandboxView
  }))
)
const DashboardOverviewView = lazy(() =>
  import('@/components/agents/DashboardOverviewView').then(m => ({
    default: m.DashboardOverviewView
  }))
)
const DataView = lazy(() =>
  import('@/components/agents/DataView').then(m => ({ default: m.DataView }))
)
const DoctorView = lazy(() =>
  import('@/components/agents/DoctorView').then(m => ({ default: m.DoctorView }))
)
const EnvironmentView = lazy(() =>
  import('@/components/agents/EnvironmentView').then(m => ({
    default: m.EnvironmentView
  }))
)
const GeneralView = lazy(() =>
  import('@/components/agents/GeneralView').then(m => ({
    default: m.GeneralView
  }))
)
const HomeView = lazy(() =>
  import('@/components/agents/HomeView').then(m => ({ default: m.HomeView }))
)
const InspectView = lazy(() =>
  import('@/components/agents/InspectView').then(m => ({
    default: m.InspectView
  }))
)
const IntegrationsView = lazy(() =>
  import('@/components/agents/IntegrationsView').then(m => ({
    default: m.IntegrationsView
  }))
)
const McpView = lazy(() =>
  import('@/components/agents/McpView').then(m => ({ default: m.McpView }))
)
const McpDetailView = lazy(() =>
  import('@/components/agents/McpDetailView').then(m => ({
    default: m.McpDetailView
  }))
)
const SandboxListView = lazy(() =>
  import('@/components/agents/SandboxListView').then(m => ({
    default: m.SandboxListView
  }))
)
const ModelsView = lazy(() =>
  import('@/components/agents/ModelsView').then(m => ({ default: m.ModelsView }))
)
const ServerStatusView = lazy(() =>
  import('@/components/agents/ServerStatusView').then(m => ({
    default: m.ServerStatusView
  }))
)
const SkillsView = lazy(() =>
  import('@/components/agents/SkillsView').then(m => ({ default: m.SkillsView }))
)
const SpecialistsView = lazy(() =>
  import('@/components/agents/SpecialistsView').then(m => ({
    default: m.SpecialistsView
  }))
)
const StorageView = lazy(() =>
  import('@/components/agents/StorageView').then(m => ({
    default: m.StorageView
  }))
)
const ToolsView = lazy(() =>
  import('@/components/agents/ToolsView').then(m => ({ default: m.ToolsView }))
)

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8787'
/** Soft warn: live SSE streams start crowding the browser's ~6 conn/host limit. */
const CONCURRENT_RUN_SOFT_LIMIT = 3
/** Hard confirm: starting another run is likely to stall files/chat. */
const CONCURRENT_RUN_HARD_LIMIT = 5

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const [backendUrl, setBackendUrl] = useState(
    () => localStorage.getItem('fastfold.backend.url') || DEFAULT_BACKEND_URL
  )
  const [backendApiKey, setBackendApiKey] = useState('')
  // Kept after login so WebSocket URLs can pass ?token= (cookies are not always
  // attached cross-port). Cleared on logout. Login input itself is cleared.
  const [clientApiKey, setClientApiKey] = useState<string | undefined>()
  const client = useMemo(
    () =>
      new LocalAgentClient({
        baseUrl: backendUrl,
        apiKey: clientApiKey || backendApiKey || undefined
      }),
    [backendApiKey, backendUrl, clientApiKey]
  )
  const [health, setHealth] = useState<BackendHealth | null>(null)
  const [cloudUserName, setCloudUserName] = useState<string | null>(null)
  const [needsAuthLogin, setNeedsAuthLogin] = useState(false)
  const needsAuthLoginRef = useRef(false)
  const [authBootstrapped, setAuthBootstrapped] = useState(false)
  const [authLoggingIn, setAuthLoggingIn] = useState(false)
  const [authLoginError, setAuthLoginError] = useState<unknown>(null)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorStack, setErrorStack] = useState<string | null>(null)
  const [connectionLimitDismissed, setConnectionLimitDismissed] =
    useState(false)
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [projects, setProjects] = useState<AgentProject[]>([])
  const [newProjectOpen, setNewProjectOpen] = useState(false)
  const [projectSettingsOpen, setProjectSettingsOpen] = useState(false)
  const [projectScopeId, setProjectScopeId] = useState<string | null>(() =>
    readProjectScopeId()
  )
  const [lastSessionByScope, setLastSessionByScope] = useState<
    Record<string, string>
  >(() => readLastSessionByScope())
  const [recentProjectIds, setRecentProjectIds] = useState<string[]>(() =>
    readRecentProjectIds()
  )
  const [sessionPreviews, setSessionPreviews] = useState<
    Record<string, string>
  >({})
  const [chatBySessionId, setChatBySessionId] = useState<
    Record<string, SessionChatState>
  >({})
  const [skills, setSkills] = useState<AgentSkill[]>([])
  const [skillDetail, setSkillDetail] = useState<AgentSkillDetail | null>(null)
  const [integrations, setIntegrations] = useState<IntegrationSummary[]>([])
  const catalogSearchEnabled = useMemo(
    () => integrations.find(item => item.key === 'skills-sh')?.configured ?? false,
    [integrations]
  )
  const [mcpServers, setMcpServers] = useState<McpServer[]>([])
  const [mcpCatalog, setMcpCatalog] = useState<McpCatalogEntry[]>([])
  const [mcpCatalogLoading, setMcpCatalogLoading] = useState(false)
  const [specialists, setSpecialists] = useState<Specialist[]>([])
  const [specialistsLoading, setSpecialistsLoading] = useState(false)
  const [runtimeSettings, setRuntimeSettings] =
    useState<RuntimeSettings | null>(null)
  const [sandboxSettings, setSandboxSettings] =
    useState<SandboxSettings | null>(null)
  const [sessionSandboxStatus, setSessionSandboxStatus] =
    useState<SessionSandboxStatus | null>(null)
  const [sessionSandboxPhase, setSessionSandboxPhase] =
    useState<SandboxActionPhase>('idle')
  const sandboxActionSessionRef = useRef<string | null>(null)
  const [modelOptions, setModelOptions] = useState<ComposerModelOption[]>([])
  const [globalSearchOpen, setGlobalSearchOpen] = useState(false)
  const [pendingOpenPath, setPendingOpenPath] = useState<string | null>(null)
  const pendingMentionRef = useRef<string | null>(null)
  const sidebarPanelRef = useRef<ImperativePanelHandle>(null)
  const filesPanelRef = useRef<ImperativePanelHandle>(null)
  const chatScrollRef = useRef<HTMLDivElement | null>(null)
  const chatEndRef = useRef<HTMLDivElement | null>(null)
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
  const [copiedResumeCommand, setCopiedResumeCommand] = useState(false)
  const [cliMenuOpen, setCliMenuOpen] = useState(false)
  const [terminalOpen, setTerminalOpen] = useState(() => {
    try {
      return localStorage.getItem(TERMINAL_OPEN_STORAGE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [filesPanelCollapsed, setFilesPanelCollapsed] = useState(() => {
    try {
      return localStorage.getItem(FILES_PANEL_COLLAPSED_STORAGE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [threadMenuOpenId, setThreadMenuOpenId] = useState<string | null>(null)
  const [collapsedSidebarSections, setCollapsedSidebarSections] = useState<
    Record<string, boolean>
  >(() => readCollapsedSidebarSections())
  const [renameTarget, setRenameTarget] = useState<AgentSession | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<AgentSession | null>(null)
  const [selectedSessionIds, setSelectedSessionIds] = useState<Set<string>>(
    () => new Set()
  )
  const [selectionAnchorId, setSelectionAnchorId] = useState<string | null>(
    null
  )
  const [batchBusy, setBatchBusy] = useState(false)
  const [batchDeletePending, setBatchDeletePending] = useState(false)
  const [openTabsByProject, setOpenTabsByProject] = useState<
    Record<string, string[]>
  >(() => readOpenTabsByProject())
  const [workspaceVersion, setWorkspaceVersion] = useState(0)
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([])
  const [integrationValues, setIntegrationValues] = useState<
    Record<string, string>
  >({})
  const onboardingAutoOpenedRef = useRef(false)
  const streamControllersRef = useRef<Map<string, AbortController>>(new Map())
  const sessionIdRef = useRef<string | null>(null)
  const loadSessionsRef = useRef<(() => Promise<void>) | null>(null)
  const createSessionInFlightRef = useRef(false)
  const autoTitlePassCountRef = useRef<Record<string, number>>({})
  const autoTitleInFlightRef = useRef<Record<string, boolean>>({})
  const prevRunActiveForTitleRef = useRef<Record<string, boolean>>({})

  const detailRoute = matchPath(
    '/dashboard/skills/:skillName',
    location.pathname
  )
  const importGithubRoute = matchPath(
    '/dashboard/skills/import/github',
    location.pathname
  )
  const importFileRoute = matchPath(
    '/dashboard/skills/import/file',
    location.pathname
  )
  const trustedSourcesRoute = matchPath(
    '/dashboard/skills/trusted/sources',
    location.pathname
  )
  const catalogDetailRoute = matchPath(
    { path: '/dashboard/skills/catalog/*', end: true },
    location.pathname
  )
  const legacySkillRoute = matchPath(
    '/agents/skills/:skillName',
    location.pathname
  )
  const integrationDetailRoute = matchPath(
    '/dashboard/integrations/:integrationKey',
    location.pathname
  )
  const mcpCatalogDetailRoute = matchPath(
    '/dashboard/mcp/catalog/:catalogId',
    location.pathname
  )
  const mcpServerDetailRoute = matchPath(
    '/dashboard/mcp/server/:serverId',
    location.pathname
  )
  const sandboxDetailRoute = matchPath(
    '/dashboard/agent/sandbox/:kind',
    location.pathname
  )
  const onboardingRoute = matchPath('/onboarding/:slug', location.pathname)
  const onOnboardingPath = isOnboardingPath(location.pathname)
  const onboardingStep = onOnboardingPath
    ? onboardingStepFromSlug(onboardingRoute?.params.slug)
    : 0
  const legacyIntegrationRoute = matchPath(
    '/agents/integrations/:integrationKey',
    location.pathname
  )
  const isCatalogSearchPath = location.pathname === '/dashboard/skills/search'
  const isCatalogPath = location.pathname.startsWith('/dashboard/skills/catalog')
  const skillRouteName =
    isCatalogSearchPath || isCatalogPath
      ? null
      : (detailRoute?.params.skillName ?? legacySkillRoute?.params.skillName)
  const catalogSkillRoute = parseCatalogSkillId(
    catalogDetailRoute?.params['*']
      ? (() => {
          try {
            return decodeURIComponent(catalogDetailRoute.params['*'])
          } catch {
            return catalogDetailRoute.params['*']
          }
        })()
      : null
  )
  const integrationRouteName =
    integrationDetailRoute?.params.integrationKey ??
    legacyIntegrationRoute?.params.integrationKey ??
    null
  const decodedIntegrationRouteName = integrationRouteName
    ? (() => {
        try {
          return decodeURIComponent(integrationRouteName)
        } catch {
          return integrationRouteName
        }
      })()
    : null
  const normalizedIntegrationRouteName = decodedIntegrationRouteName
    ? decodedIntegrationRouteName.toLowerCase().replace(/[_\s]+/g, '-')
    : null
  const selectedIntegrationKey = decodedIntegrationRouteName
    ? integrations.find(item => {
        const normalizedKey = item.key.toLowerCase().replace(/[_\s]+/g, '-')
        const normalizedName = item.name.toLowerCase().replace(/[_\s]+/g, '-')
        return (
          item.key === decodedIntegrationRouteName ||
          normalizedKey === normalizedIntegrationRouteName ||
          normalizedName === normalizedIntegrationRouteName
        )
      })?.key ?? decodedIntegrationRouteName
    : null
  const sessionRoute = matchPath('/agents/:sessionId', location.pathname)
  const projectRoute = matchPath('/projects/:projectId', location.pathname)
  const specialistNewRoute = matchPath(
    '/dashboard/specialists/new',
    location.pathname
  )
  const specialistEditRoute = matchPath(
    '/dashboard/specialists/:specialistId',
    location.pathname
  )
  const routeProjectId = projectRoute?.params.projectId ?? null
  const specialistsViewMode: 'list' | 'new' | 'edit' = specialistNewRoute
    ? 'new'
    : specialistEditRoute?.params.specialistId &&
        specialistEditRoute.params.specialistId !== 'new'
      ? 'edit'
      : 'list'
  const specialistsEditId =
    specialistsViewMode === 'edit'
      ? specialistEditRoute?.params.specialistId ?? null
      : null
  const activeProjectId = projectScopeId
  const tabsScopeKey = projectTabsKey(activeProjectId)
  const openTabIds = openTabsByProject[tabsScopeKey] || []
  const activeProject =
    projects.find(project => project.id === activeProjectId) || null
  const activeIntegration =
    integrations.find(item => item.key === selectedIntegrationKey) || null
  const isDashboard =
    location.pathname === '/dashboard' ||
    location.pathname.startsWith('/dashboard/')
  const dashboardSection: DashboardSection = location.pathname.startsWith(
    '/dashboard/status'
  ) || location.pathname.startsWith('/dashboard/server')
    ? 'status'
    : location.pathname.startsWith('/dashboard/general') ||
        location.pathname.startsWith('/dashboard/settings')
      ? 'general'
      : location.pathname.startsWith('/dashboard/agent/sandbox')
        ? 'agent_sandbox'
        : location.pathname.startsWith('/dashboard/agent/prompts')
          ? 'agent_prompts'
          : location.pathname.startsWith('/dashboard/agent')
            ? 'agent_runtime'
            : location.pathname.startsWith('/dashboard/models')
              ? 'models'
              : location.pathname.startsWith('/dashboard/datasets')
                ? 'datasets'
                : location.pathname.startsWith('/dashboard/tools')
                  ? 'tools'
                  : location.pathname.startsWith('/dashboard/doctor')
                    ? 'doctor'
                    : location.pathname.startsWith('/dashboard/storage')
                      ? 'storage'
                      : location.pathname.startsWith('/dashboard/environment')
                        ? 'environment'
                        : location.pathname.startsWith('/dashboard/skills')
                          ? 'skills'
                          : location.pathname.startsWith('/dashboard/specialists')
                            ? 'specialists'
                            : location.pathname.startsWith('/dashboard/integrations')
                              ? 'integrations'
                              : location.pathname.startsWith('/dashboard/mcp')
                                ? 'mcp'
                                : 'overview'
  const isSkills =
    dashboardSection === 'skills' ||
    location.pathname === '/agents/skills' ||
    Boolean(legacySkillRoute)
  const skillsViewMode: SkillsViewMode =
    catalogSkillRoute
    ? 'catalog_detail'
    : (detailRoute || legacySkillRoute) && !isCatalogSearchPath
    ? 'detail'
    : importGithubRoute
    ? 'import_github'
    : importFileRoute
    ? 'import_file'
    : trustedSourcesRoute
    ? 'trusted_sources'
    : 'list'
  const isIntegrations =
    dashboardSection === 'integrations' ||
    location.pathname === '/agents/integrations' ||
    Boolean(legacyIntegrationRoute)
  const isDashboardStatus = dashboardSection === 'status'
  const isDashboardGeneral = dashboardSection === 'general'
  const isDashboardAgentRuntime = dashboardSection === 'agent_runtime'
  const isDashboardAgentSandbox = dashboardSection === 'agent_sandbox'
  const isDashboardAgentPrompts = dashboardSection === 'agent_prompts'
  const isDashboardModels = dashboardSection === 'models'
  const isDashboardData = dashboardSection === 'datasets'
  const isDashboardTools = dashboardSection === 'tools'
  const isDashboardDoctor = dashboardSection === 'doctor'
  const isDashboardStorage = dashboardSection === 'storage'
  const isDashboardEnvironment = dashboardSection === 'environment'
  const isDashboardMcp = dashboardSection === 'mcp'
  const mcpCatalogDetailId = mcpCatalogDetailRoute?.params.catalogId
    ? decodeURIComponent(mcpCatalogDetailRoute.params.catalogId)
    : null
  const mcpServerDetailId = mcpServerDetailRoute?.params.serverId
    ? decodeURIComponent(mcpServerDetailRoute.params.serverId)
    : null
  const mcpDetailCatalogEntry = mcpCatalogDetailId
    ? mcpCatalog.find(entry => entry.id === mcpCatalogDetailId) || null
    : null
  const mcpDetailServer = mcpServerDetailId
    ? mcpServers.find(server => server.id === mcpServerDetailId) || null
    : null
  const isMcpDetail = Boolean(mcpCatalogDetailId || mcpServerDetailId)
  const sandboxKindRaw = sandboxDetailRoute?.params.kind
  const sandboxKind =
    sandboxKindRaw === 'local' || sandboxKindRaw === 'modal'
      ? sandboxKindRaw
      : null
  const isSandboxLocalDetail = sandboxKind === 'local'
  const isSandboxModalDetail = sandboxKind === 'modal'
  const isDashboardSpecialists = dashboardSection === 'specialists'
  const isDashboardOverview = isDashboard && dashboardSection === 'overview'
  const isHome =
    location.pathname === '/' || location.pathname === '/agents/home'
  const isProjectHome = Boolean(routeProjectId)
  const isInspect = new URLSearchParams(location.search).get('inspect') === '1'
  const dashboardSkeletonKind: DashboardSkeletonKind = (() => {
    if (isHome || isProjectHome) return 'home'
    if (isDashboardOverview) return 'overview'
    if (isDashboardDoctor) return 'doctor'
    if (
      isDashboardStatus ||
      isDashboardGeneral ||
      isDashboardAgentRuntime ||
      isDashboardAgentPrompts ||
      isDashboardStorage ||
      isDashboardEnvironment
    ) {
      return 'settings'
    }
    if (isDashboardModels) return 'models'
    if (isDashboardData || isDashboardTools) return 'list'
    if (isDashboardSpecialists) {
      return specialistsViewMode === 'list' ? 'list' : 'detail'
    }
    if (isDashboardMcp || isIntegrations) return 'cards'
    if (isDashboardAgentSandbox) {
      return sandboxKind ? 'settings' : 'cards'
    }
    if (isSkills) {
      return skillsViewMode === 'list' ? 'cards' : 'detail'
    }
    return 'detail'
  })()
  const sessionId =
    !isDashboard &&
    !isSkills &&
    !isIntegrations &&
    !isHome &&
    !isProjectHome &&
    sessionRoute?.params.sessionId &&
    sessionRoute.params.sessionId !== 'home' &&
    sessionRoute.params.sessionId !== 'skills' &&
    sessionRoute.params.sessionId !== 'integrations'
      ? sessionRoute.params.sessionId
      : null
  const session = sessions.find(item => item.id === sessionId) || null

  const patchOpenTabs = useCallback(
    (scopeKey: string, updater: (current: string[]) => string[]) => {
      setOpenTabsByProject(current => {
        const prev = current[scopeKey] || []
        const next = updater(prev)
        if (
          next.length === prev.length &&
          next.every((id, index) => id === prev[index])
        ) {
          return current
        }
        const map = { ...current, [scopeKey]: next }
        writeOpenTabsByProject(map)
        return map
      })
    },
    []
  )

  const setOpenTabIds = useCallback(
    (value: string[] | ((current: string[]) => string[])) => {
      patchOpenTabs(tabsScopeKey, current =>
        typeof value === 'function' ? value(current) : value
      )
    },
    [patchOpenTabs, tabsScopeKey]
  )

  const openSessionTab = useCallback(
    (id: string, scopeKey: string = tabsScopeKey) => {
      patchOpenTabs(scopeKey, current =>
        current.includes(id) ? current : [...current, id]
      )
    },
    [patchOpenTabs, tabsScopeKey]
  )

  const runningSessionIdsKey = sessions
    .filter(item => item.status === 'running')
    .map(item => item.id)
    .sort()
    .join(',')
  const runningCount = runningSessionIdsKey
    ? runningSessionIdsKey.split(',').length
    : 0
  const showConnectionLimitWarning =
    runningCount >= CONCURRENT_RUN_SOFT_LIMIT && !connectionLimitDismissed
  const chat = sessionId
    ? chatBySessionId[sessionId] ?? emptySessionChatState()
    : emptySessionChatState()
  const {
    messages,
    tools,
    todosByRunId,
    runIdByMessageId,
    usageByRunId,
    tokenUsage,
    activeRunId,
    runActive,
    liveDelta,
    composer,
    composerSkills,
    composerFiles,
    queuedMessages,
    expandedToolRunKeys,
    messagesLoaded
  } = chat

  sessionIdRef.current = sessionId
  // Live draft from Composer keystrokes (not lifted into React state on each type).
  const composerLiveRef = useRef(composer)
  useEffect(() => {
    composerLiveRef.current = composer
  }, [composer, sessionId])

  const [editingQueuedId, setEditingQueuedId] = useState<string | null>(null)
  const pendingImmediateSendRef = useRef<{
    sessionId: string
    text: string
  } | null>(null)
  const drainingQueueRef = useRef(false)

  useEffect(() => {
    setEditingQueuedId(null)
  }, [sessionId])

  const patchChat = useCallback(
    (
      id: string,
      patch:
        | Partial<SessionChatState>
        | ((prev: SessionChatState) => SessionChatState)
    ) => {
      setChatBySessionId(current => {
        const prev = current[id] ?? emptySessionChatState()
        const next =
          typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
        if (next === prev) return current
        return { ...current, [id]: next }
      })
    },
    []
  )

  const chatBySessionIdRef = useRef(chatBySessionId)
  chatBySessionIdRef.current = chatBySessionId

  const prefetchSessionMessages = useCallback(
    async (id: string, signal?: AbortSignal) => {
      if (chatBySessionIdRef.current[id]?.messagesLoaded) return
      try {
        const history = await client.listMessages(id, signal)
        if (signal?.aborted) return
        patchChat(id, prev => ({
          ...prev,
          messages: history,
          messagesLoaded: true
        }))
      } catch (cause: unknown) {
        if (signal?.aborted) return
        if (cause instanceof Error && cause.name === 'AbortError') return
      }
    },
    [client, patchChat]
  )

  const loadSessions = useCallback(async () => {
    const nextSessions = await client.listSessions()
    setSessions(nextSessions)
    setChatBySessionId(current => {
      let changed = false
      const next = { ...current }
      for (const item of nextSessions) {
        const prev = next[item.id]
        if (!prev) continue
        const shouldRun = item.status === 'running'
        if (prev.runActive === shouldRun) continue
        next[item.id] = { ...prev, runActive: shouldRun }
        changed = true
      }
      return changed ? next : current
    })
    void Promise.all(
      nextSessions.slice(0, 12).map(async item => {
        try {
          const history = await client.listMessages(item.id)
          return [
            item.id,
            history.at(-1)?.content || 'No messages yet.'
          ] as const
        } catch {
          return [item.id, 'No messages yet.'] as const
        }
      })
    ).then(entries => setSessionPreviews(Object.fromEntries(entries)))
  }, [client])

  loadSessionsRef.current = loadSessions

  const loadProjects = useCallback(async () => {
    setProjects(await client.listProjects())
  }, [client])

  const loadSkills = useCallback(async () => {
    const items = await client.listSkills()
    const seen = new Set<string>()
    const unique = items.filter(skill => {
      const key = skill.name.trim().toLowerCase()
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
    setSkills(unique)
  }, [client])

  const loadIntegrations = useCallback(async () => {
    setIntegrations(await client.listIntegrations())
  }, [client])

  const loadMcpServers = useCallback(async () => {
    setMcpServers(await client.listMcpServers())
  }, [client])

  const loadMcpCatalog = useCallback(async () => {
    setMcpCatalogLoading(true)
    try {
      setMcpCatalog(await client.listMcpCatalog())
    } finally {
      setMcpCatalogLoading(false)
    }
  }, [client])

  const refreshMcp = useCallback(async () => {
    await Promise.all([loadMcpServers(), loadMcpCatalog()])
  }, [loadMcpCatalog, loadMcpServers])

  const loadSpecialists = useCallback(async () => {
    setSpecialistsLoading(true)
    try {
      setSpecialists(await client.listSpecialists())
    } catch {
      // Optional capability — older backends may not expose /v1/specialists yet.
      setSpecialists([])
    } finally {
      setSpecialistsLoading(false)
    }
  }, [client])

  const loadModelOptions = useCallback(async () => {
    try {
      const [models, profiles] = await Promise.all([
        client.listModels({
          enabledOnly: true,
          discover: true
        }),
        client.listModelProfiles().catch(() => [])
      ])
      const backendsByProfileId = Object.fromEntries(
        (profiles || []).map(profile => [profile.id, profile.backend])
      )
      setModelOptions(
        toComposerModelOptions(
          models.map(model => ({
            ...model,
            backend:
              model.backend ??
              (model.profileId
                ? backendsByProfileId[model.profileId] || null
                : null)
          }))
        )
      )
    } catch {
      // Keep the last known selector list if the catalog request fails.
    }
  }, [client])

  const loadAccount = useCallback(
    (options?: { checkUpdates?: boolean; signal?: AbortSignal }) =>
      client.getAccount(options),
    [client]
  )

  const refreshCloudUserName = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const account = await loadAccount({ signal })
        if (signal?.aborted) return
        setCloudUserName(cloudAccountDisplayName(account))
      } catch {
        if (!signal?.aborted) setCloudUserName(null)
      }
    },
    [loadAccount]
  )

  const loadAccountForUi = useCallback(
    async (options?: { checkUpdates?: boolean; signal?: AbortSignal }) => {
      const account = await loadAccount(options)
      if (!options?.signal?.aborted) {
        setCloudUserName(cloudAccountDisplayName(account))
      }
      return account
    },
    [loadAccount]
  )

  const logoutAccount = useCallback(
    async (signal?: AbortSignal) => {
      const account = await client.logoutAccount(signal)
      if (!signal?.aborted) {
        setCloudUserName(cloudAccountDisplayName(account))
      }
      return account
    },
    [client]
  )

  useEffect(() => {
    if (!health) {
      setCloudUserName(null)
      return
    }
    const controller = new AbortController()
    void refreshCloudUserName(controller.signal)
    return () => controller.abort()
  }, [health, refreshCloudUserName])

  // Cloud account name when linked; otherwise Mac/local GECOS name from health.
  const sidebarUserName =
    cloudUserName?.trim() || health?.userName?.trim() || null

  const loadStorage = useCallback(
    (signal?: AbortSignal) => client.getStorage(signal),
    [client]
  )
  const loadEnvironment = useCallback(
    (signal?: AbortSignal) => client.getEnvironment(signal),
    [client]
  )
  const loadServerStatus = useCallback(
    (signal?: AbortSignal) => client.getServerStatus(signal),
    [client]
  )

  const connect = useCallback(async () => {
    setConnecting(true)
    setError(null)
    setErrorStack(null)
    const goToLogin = () => {
      const alreadyNext = nextFromSearch(location.search)
      const deepLink =
        location.pathname === '/'
          ? null
          : sanitizeAuthReturnTo(
              `${location.pathname}${location.search}${location.hash}`
            )
      needsAuthLoginRef.current = true
      setHealth(null)
      setNeedsAuthLogin(true)
      const target = loginPathWithNext(alreadyNext || deepLink)
      if (`${location.pathname}${location.search}` !== target) {
        navigate(target, { replace: true })
      }
    }

    try {
      // If we already decided login is required (e.g. logout), do not remount
      // the shell from a stale reconnect.
      if (needsAuthLoginRef.current) {
        return
      }
      const nextHealth = await client.health()
      if (needsAuthLoginRef.current) return
      localStorage.setItem('fastfold.backend.url', backendUrl)

      let authEnabled = false
      let authenticated: boolean | null = null
      try {
        const status = await client.authStatus()
        authEnabled = Boolean(status.authEnabled)
        authenticated =
          typeof status.authenticated === 'boolean'
            ? status.authenticated
            : null
      } catch {
        authEnabled = false
        authenticated = null
      }
      if (needsAuthLoginRef.current) return

      if (authEnabled) {
        if (authenticated === false) {
          // Auth on, no session — show login without probing protected routes.
          goToLogin()
          return
        }
        if (authenticated === null) {
          // Legacy servers without `authenticated` — keep the old probe.
          try {
            await client.getRuntimeSettings()
          } catch (cause) {
            if (isAuthCredentialError(cause)) {
              goToLogin()
              return
            }
            throw cause
          }
        }
      }
      if (needsAuthLoginRef.current) return

      // Only mount the app shell after auth is confirmed.
      needsAuthLoginRef.current = false
      setNeedsAuthLogin(false)
      setHealth(nextHealth)
      const [, , , , , , , settings, sandbox] = await Promise.all([
        loadSessions(),
        loadProjects(),
        loadSkills(),
        loadIntegrations(),
        loadMcpServers(),
        loadMcpCatalog(),
        loadSpecialists(),
        client.getRuntimeSettings(),
        // Older backends may not have /settings/sandbox yet — don't block connect.
        client.getSandboxSettings().catch(() => null),
        loadModelOptions()
      ])
      if (needsAuthLoginRef.current) return
      setRuntimeSettings(settings)
      setSandboxSettings(sandbox)
      try {
        const onboarding = await client.getOnboardingSettings()
        const step = clampOnboardingStep(onboarding.step)
        if (!onboarding.completed && !onboardingAutoOpenedRef.current) {
          onboardingAutoOpenedRef.current = true
          if (!isOnboardingPath(location.pathname)) {
            navigate(onboardingPath(step), { replace: true })
            return
          }
        }
      } catch {
        // Older backends may not expose onboarding settings yet.
      }
      const returnTo = nextFromSearch(location.search)
      if (returnTo) {
        navigate(returnTo, { replace: true })
      }
    } catch (cause) {
      if (needsAuthLoginRef.current) return
      const message =
        cause instanceof Error ? cause.message : 'Unable to connect'
      const isLocalBackend = /127\.0\.0\.1|localhost/i.test(backendUrl)
      // Only credential failures belong on the login screen. Network / CORS /
      // 5xx must surface as a backend error — not a fake "enter API key" page.
      if (isAuthCredentialError(cause)) {
        try {
          const status = await client.authStatus()
          if (status.authEnabled) {
            goToLogin()
            return
          }
        } catch {
          // Fall through to backend-error UI below.
        }
      }
      if (isLocalBackend && isBackendUnavailableError(cause)) {
        needsAuthLoginRef.current = false
        setNeedsAuthLogin(false)
        setHealth(null)
        setError(message)
        setErrorStack(cause instanceof Error ? cause.stack || null : null)
        return
      }
      setHealth(null)
      setError(message)
      setErrorStack(cause instanceof Error ? cause.stack || null : null)
    } finally {
      setConnecting(false)
      setAuthBootstrapped(true)
    }
  }, [
    backendUrl,
    client,
    loadIntegrations,
    loadMcpCatalog,
    loadMcpServers,
    loadModelOptions,
    loadProjects,
    loadSessions,
    loadSkills,
    loadSpecialists,
    location.hash,
    location.pathname,
    location.search,
    navigate
  ])

  const submitAuthLogin = useCallback(
    async (apiKey: string, remember: boolean) => {
      setAuthLoggingIn(true)
      setAuthLoginError(null)
      try {
        await client.login(apiKey, { remember })
        setClientApiKey(apiKey.trim())
        setBackendApiKey('')
        needsAuthLoginRef.current = false
        // Keep login UI until connect() confirms the session.
        await connect()
      } catch (cause) {
        needsAuthLoginRef.current = true
        setNeedsAuthLogin(true)
        if (isBackendUnavailableError(cause) || !isAuthCredentialError(cause)) {
          setAuthLoginError(cause)
          const info = normalizeAppError(cause)
          toast.error(info.title)
        } else {
          const raw = cause instanceof Error ? cause.message : 'Invalid API key'
          let message = 'Invalid API key'
          try {
            const jsonMatch = raw.match(/\{.*\}/s)
            if (jsonMatch) {
              const parsed = JSON.parse(jsonMatch[0]) as { detail?: string }
              if (parsed.detail) message = parsed.detail
            } else if (/invalid api key/i.test(raw)) {
              message = 'Invalid API key'
            } else if (raw && !raw.startsWith('FastFold Agent API')) {
              message = raw
            }
          } catch {
            // keep friendly default
          }
          toast.error(message)
        }
      } finally {
        setAuthLoggingIn(false)
      }
    },
    [client, connect]
  )

  const logoutSession = useCallback(async () => {
    // Gate the UI immediately so a reconnect effect cannot remount the app
    // before the logout request finishes / cookie is cleared.
    needsAuthLoginRef.current = true
    setNeedsAuthLogin(true)
    setAuthLoginError(null)
    setHealth(null)
    setAuthBootstrapped(true)
    setBackendApiKey('')
    setClientApiKey(undefined)
    setRuntimeSettings(null)
    if (location.pathname !== '/' || location.search) {
      navigate('/', { replace: true })
    }
    try {
      await client.logout()
    } catch {
      // Cookie clear may have failed; UI is already on login.
    }
  }, [client, location.pathname, location.search, navigate])

  useEffect(() => {
    // Legacy /login URL → root (login renders under / when unauthenticated).
    if (location.pathname === '/login') {
      navigate('/', { replace: true })
      return
    }
    if (location.pathname === '/agents/home') {
      navigate('/', { replace: true })
      return
    }
    if (location.pathname === '/dashboard/settings') {
      navigate('/dashboard/general', { replace: true })
      return
    }
    if (location.pathname === '/agents/skills') {
      navigate('/dashboard/skills', { replace: true })
      return
    }
    if (legacySkillRoute?.params.skillName) {
      navigate(
        `/dashboard/skills/${legacySkillRoute.params.skillName}`,
        { replace: true }
      )
      return
    }
    if (location.pathname === '/agents/integrations') {
      navigate('/dashboard/integrations', { replace: true })
      return
    }
    if (legacyIntegrationRoute?.params.integrationKey) {
      navigate(
        `/dashboard/integrations/${legacyIntegrationRoute.params.integrationKey}`,
        { replace: true }
      )
      return
    }
    if (onOnboardingPath) {
      const canonical = onboardingPath(onboardingStep)
      if (location.pathname !== canonical) {
        navigate(canonical, { replace: true })
      }
    }
  }, [
    legacyIntegrationRoute?.params.integrationKey,
    legacySkillRoute?.params.skillName,
    location.pathname,
    navigate,
    onOnboardingPath,
    onboardingStep
  ])

  useEffect(() => {
    const base = 'sandwalk'
    if (onOnboardingPath) {
      const stepTitle = onboardingStepDef(onboardingStep).title
      document.title = `Onboarding ${stepTitle} - ${base}`
      return
    }
    if (session?.title) {
      document.title = `${session.title} · ${base}`
      return
    }
    if (isDashboardOverview) {
      document.title = `Dashboard · ${base}`
      return
    }
    if (isDashboardStatus) {
      document.title = `Status · ${base}`
      return
    }
    if (isDashboardGeneral) {
      document.title = `General · ${base}`
      return
    }
    if (isDashboardModels) {
      document.title = `Models · ${base}`
      return
    }
    if (isDashboardTools) {
      document.title = `Tools · ${base}`
      return
    }
    if (isDashboardDoctor) {
      document.title = `Doctor · ${base}`
      return
    }
    if (isDashboardStorage) {
      document.title = `Storage · ${base}`
      return
    }
    if (isDashboardEnvironment) {
      document.title = `Environment · ${base}`
      return
    }
    if (isSkills) {
      document.title = `Skills · ${base}`
      return
    }
    if (isDashboardSpecialists) {
      document.title = `Specialists · ${base}`
      return
    }
    if (isIntegrations) {
      if (activeIntegration) {
        document.title = `${activeIntegration.name} · Integrations · ${base}`
        return
      }
      document.title = `Integrations · ${base}`
      return
    }
    if (isDashboardData) {
      document.title = `Datasets · ${base}`
      return
    }
    if (isDashboardAgentSandbox) {
      if (isSandboxLocalDetail) {
        document.title = `Local Sandbox · ${base}`
        return
      }
      if (isSandboxModalDetail) {
        document.title = `Modal Sandbox · ${base}`
        return
      }
      document.title = `Sandbox · ${base}`
      return
    }
    if (isDashboardAgentPrompts) {
      document.title = `Prompts · ${base}`
      return
    }
    if (isDashboardAgentRuntime) {
      document.title = `Runtime · ${base}`
      return
    }
    if (isDashboardMcp) {
      document.title = `MCP · ${base}`
      return
    }
    if (activeProject) {
      document.title = `${activeProject.name} · ${base}`
      return
    }
    document.title = base
  }, [
    activeIntegration,
    activeProject,
    isDashboardDoctor,
    isDashboardStorage,
    isDashboardEnvironment,
    isDashboardAgentSandbox,
    isDashboardAgentPrompts,
    isDashboardAgentRuntime,
    isSandboxLocalDetail,
    isSandboxModalDetail,
    isDashboardMcp,
    isDashboardOverview,
    isDashboardStatus,
    isDashboardGeneral,
    isDashboardModels,
    isDashboardData,
    isDashboardTools,
    isDashboardSpecialists,
    isIntegrations,
    isSkills,
    onOnboardingPath,
    onboardingStep,
    session?.title
  ])

  useEffect(() => {
    if (needsAuthLogin) return
    void connect()
  }, [connect, needsAuthLogin])

  // Local dashboard: when the API is temporarily down or returning 5xx,
  // keep retrying until health/bootstrap succeeds.
  useEffect(() => {
    if (needsAuthLogin || health || connecting) return
    if (!error) return
    if (!/127\.0\.0\.1|localhost/i.test(backendUrl)) return
    if (!isBackendUnavailableError(error)) return
    const timer = window.setInterval(() => {
      void connect()
    }, 5000)
    return () => window.clearInterval(timer)
  }, [backendUrl, connect, connecting, error, health, needsAuthLogin])

  useEffect(() => {
    if (isDashboardModels || !health) return
    void loadModelOptions()
  }, [health, isDashboardModels, loadModelOptions])

  useEffect(() => {
    setIntegrationValues({})
  }, [selectedIntegrationKey])

  useEffect(() => {
    if (!isIntegrations || !selectedIntegrationKey) return
    if (integrations.length === 0) return
    if (!integrations.some(item => item.key === selectedIntegrationKey)) {
      navigate('/dashboard/integrations', { replace: true })
    }
  }, [integrations, isIntegrations, navigate, selectedIntegrationKey])

  useEffect(() => {
    if (!sessionId) return
    const item = sessions.find(session => session.id === sessionId)
    // Keep project tab strips clean: only pin sessions that belong to the scope.
    if (activeProjectId && item && item.projectId !== activeProjectId) return
    openSessionTab(sessionId)
  }, [activeProjectId, openSessionTab, sessionId, sessions])

  useEffect(() => {
    // Wait until sessions are loaded — otherwise every persisted tab looks
    // "unknown" and gets wiped on reload.
    if (!activeProjectId || sessions.length === 0) return
    setOpenTabsByProject(current => {
      const ids = current[activeProjectId]
      if (!ids || ids.length === 0) return current
      const filtered = ids.filter(id => {
        const item = sessions.find(session => session.id === id)
        return Boolean(item && item.projectId === activeProjectId)
      })
      if (filtered.length === ids.length) return current
      const next = { ...current }
      if (filtered.length > 0) next[activeProjectId] = filtered
      else delete next[activeProjectId]
      writeOpenTabsByProject(next)
      return next
    })
  }, [activeProjectId, sessions])

  useEffect(() => {
    if (!sessionId) return
    setLastSessionByScope(current => {
      if (current[tabsScopeKey] === sessionId) return current
      const next = { ...current, [tabsScopeKey]: sessionId }
      writeLastSessionByScope(next)
      return next
    })
  }, [sessionId, tabsScopeKey])

  useEffect(() => {
    writeProjectScopeId(projectScopeId)
  }, [projectScopeId])

  useEffect(() => {
    if (sessions.length === 0) return
    const existing = new Set(sessions.map(item => item.id))
    setOpenTabsByProject(current => {
      let changed = false
      const next: Record<string, string[]> = {}
      for (const [key, ids] of Object.entries(current)) {
        const filtered = ids.filter(id => existing.has(id))
        if (filtered.length !== ids.length) changed = true
        if (filtered.length > 0) next[key] = filtered
        else if (ids.length > 0) changed = true
      }
      if (!changed) return current
      writeOpenTabsByProject(next)
      return next
    })
    setLastSessionByScope(current => {
      let changed = false
      const next: Record<string, string> = {}
      for (const [key, id] of Object.entries(current)) {
        if (!existing.has(id)) {
          changed = true
          continue
        }
        next[key] = id
      }
      if (!changed) return current
      writeLastSessionByScope(next)
      return next
    })
  }, [sessions])

  useEffect(() => {
    if (!sessionId) {
      setWorkspaceFiles([])
      return
    }
    let cancelled = false
    void client
      .listFiles(sessionId)
      .then(files => {
        if (!cancelled) setWorkspaceFiles(files)
      })
      .catch(() => {
        if (!cancelled) setWorkspaceFiles([])
      })
    return () => {
      cancelled = true
    }
  }, [client, sessionId, workspaceVersion])

  useEffect(() => {
    if (!sessionId || !health) {
      setSessionSandboxStatus(null)
      setSessionSandboxPhase('idle')
      sandboxActionSessionRef.current = null
      return
    }
    if (sandboxActionSessionRef.current !== sessionId) {
      setSessionSandboxPhase('idle')
    }
    let cancelled = false
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null
    let reconnectDelayMs = 1000
    let hardFailures = 0

    const applyStatus = (status: SessionSandboxStatus) => {
      if (cancelled) return
      setSessionSandboxStatus(status)
      if (status.status === 'starting') {
        setSessionSandboxPhase('starting')
        sandboxActionSessionRef.current = sessionId
      } else if (status.status === 'stopping') {
        setSessionSandboxPhase('stopping')
        sandboxActionSessionRef.current = sessionId
      } else if (status.status === 'running') {
        if (sandboxActionSessionRef.current === sessionId) {
          sandboxActionSessionRef.current = null
        }
        setSessionSandboxPhase('idle')
      } else if (
        (status.status === 'stopped' ||
          status.status === 'unavailable' ||
          status.status === 'ready') &&
        sandboxActionSessionRef.current !== sessionId
      ) {
        setSessionSandboxPhase('idle')
      }
    }

    const refresh = () => {
      void client
        .getSessionSandbox(sessionId)
        .then(status => {
          if (!cancelled) applyStatus(status)
        })
        .catch(() => {
          if (!cancelled) setSessionSandboxStatus(null)
        })
    }

    const connect = () => {
      if (cancelled) return
      try {
        socket?.close()
      } catch {
        // ignore
      }
      const ws = new WebSocket(client.sandboxStreamUrl(sessionId))
      socket = ws
      ws.onopen = () => {
        reconnectDelayMs = 1000
        hardFailures = 0
        refresh()
      }
      ws.onmessage = event => {
        try {
          const payload = JSON.parse(String(event.data)) as SessionSandboxStatus & {
            type?: string
          }
          if (payload?.sessionId) applyStatus(payload)
        } catch {
          // ignore malformed frames
        }
      }
      ws.onclose = event => {
        if (cancelled) return
        // 1006 = abnormal close (refused / failed handshake). Back off harder
        // so a down API does not reconnect-storm the console.
        if (event.code === 1006 || event.code === 4401 || event.code === 1011) {
          hardFailures += 1
          reconnectDelayMs = Math.min(
            Math.max(reconnectDelayMs, 2000) * 2,
            hardFailures >= 5 ? 30000 : 15000
          )
        }
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = null
          connect()
        }, reconnectDelayMs)
        if (!(event.code === 1006 || event.code === 4401 || event.code === 1011)) {
          reconnectDelayMs = Math.min(reconnectDelayMs * 2, 8000)
        }
      }
      ws.onerror = () => {
        try {
          ws.close()
        } catch {
          // ignore
        }
      }
    }

    refresh()
    connect()
    return () => {
      cancelled = true
      if (reconnectTimer != null) window.clearTimeout(reconnectTimer)
      try {
        socket?.close()
      } catch {
        // ignore
      }
    }
  }, [client, health, sessionId, session?.sandboxBackend])

  useEffect(() => {
    try {
      localStorage.setItem(
        SIDEBAR_COLLAPSED_STORAGE_KEY,
        sidebarCollapsed ? '1' : '0'
      )
    } catch {
      // ignore storage failures
    }
  }, [sidebarCollapsed])

  useEffect(() => {
    try {
      localStorage.setItem(
        FILES_PANEL_COLLAPSED_STORAGE_KEY,
        filesPanelCollapsed ? '1' : '0'
      )
    } catch {
      // ignore storage failures
    }
  }, [filesPanelCollapsed])

  useEffect(() => {
    try {
      localStorage.setItem(TERMINAL_OPEN_STORAGE_KEY, terminalOpen ? '1' : '0')
    } catch {
      // ignore storage failures
    }
  }, [terminalOpen])

  useEffect(() => {
    const panel = sidebarPanelRef.current
    if (!panel) return
    if (sidebarCollapsed) {
      if (!panel.isCollapsed()) panel.collapse()
    } else if (panel.isCollapsed()) {
      panel.expand()
    }
  }, [sidebarCollapsed])

  useEffect(() => {
    const panel = filesPanelRef.current
    if (!panel) return
    if (filesPanelCollapsed) {
      if (!panel.isCollapsed()) panel.collapse()
    } else if (panel.isCollapsed()) {
      panel.expand()
    }
  }, [filesPanelCollapsed, sessionId])

  useEffect(() => {
    writeCollapsedSidebarSections(collapsedSidebarSections)
  }, [collapsedSidebarSections])

  useEffect(() => {
    if (runningCount < CONCURRENT_RUN_SOFT_LIMIT) {
      setConnectionLimitDismissed(false)
    }
  }, [runningCount])

  useEffect(() => {
    if (routeProjectId) {
      setProjectScopeId(routeProjectId)
      return
    }
    if (
      location.pathname === '/' ||
      location.pathname === '/agents/home'
    ) {
      setProjectScopeId(null)
    }
  }, [location.pathname, routeProjectId])

  useEffect(() => {
    if (!health || !sessionId) return
    if (chatBySessionIdRef.current[sessionId]?.messagesLoaded) return

    // Empty/new sessions: show the empty composer immediately, hydrate in background.
    const meta = sessions.find(item => item.id === sessionId)
    if (meta && !meta.lastMessageAt && meta.status === 'idle') {
      patchChat(sessionId, prev =>
        prev.messagesLoaded
          ? prev
          : { ...prev, messages: [], messagesLoaded: true }
      )
    }

    const controller = new AbortController()
    void client
      .listMessages(sessionId, controller.signal)
      .then(history => {
        patchChat(sessionId, prev => ({
          ...prev,
          messages: history,
          messagesLoaded: true
        }))
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to load messages'
          )
        }
      })
    return () => controller.abort()
    // Intentionally omit `sessions` — only re-hydrate when the active session changes.
  }, [client, health, patchChat, sessionId])

  const [showChatSkeleton, setShowChatSkeleton] = useState(false)
  useEffect(() => {
    if (messagesLoaded || runActive || !sessionId) {
      setShowChatSkeleton(false)
      return
    }
    const timer = window.setTimeout(() => setShowChatSkeleton(true), 180)
    return () => window.clearTimeout(timer)
  }, [messagesLoaded, runActive, sessionId])

  useEffect(() => {
    if (!health) {
      for (const controller of streamControllersRef.current.values()) {
        controller.abort()
      }
      streamControllersRef.current.clear()
      return
    }

    // Only stream the active session + any currently running sessions.
    // An SSE per open tab exhausts the browser's ~6 HTTP/1.1 connections/host,
    // which leaves file content fetches stuck in (pending).
    const wanted = new Set<string>()
    if (sessionId) wanted.add(sessionId)
    for (const id of runningSessionIdsKey.split(',').filter(Boolean)) {
      wanted.add(id)
    }

    for (const [id, controller] of [...streamControllersRef.current]) {
      if (!wanted.has(id)) {
        controller.abort()
        streamControllersRef.current.delete(id)
      }
    }

    for (const id of wanted) {
      if (streamControllersRef.current.has(id)) continue
      const controller = new AbortController()
      streamControllersRef.current.set(id, controller)

      void client
        .streamEvents(id, {
          signal: controller.signal,
          onEvent: (event: AgentEvent) => {
            if (event.type === 'run.started') {
              patchChat(id, prev => ({
                ...prev,
                runActive: true,
                activeRunId: event.runId,
                liveDelta: ''
              }))
              setSessions(current =>
                current.map(item =>
                  item.id === id
                    ? { ...item, status: 'running' as const }
                    : item
                )
              )
              void client.listMessages(id).then(history => {
                patchChat(id, prev => ({
                  ...prev,
                  messages: history,
                  messagesLoaded: true
                }))
              })
            } else if (event.type === 'session.updated') {
              void loadSessionsRef.current?.()
            } else if (event.type === 'assistant.delta') {
              patchChat(id, prev => ({
                ...prev,
                liveDelta: prev.liveDelta + event.payload.delta
              }))
            } else if (event.type === 'tool.started') {
              const toolId = event.payload.toolCallId || event.id
              patchChat(id, prev => {
                if (prev.tools.some(tool => tool.id === toolId)) return prev
                return {
                  ...prev,
                  tools: [
                    ...prev.tools,
                    {
                      id: toolId,
                      runId: event.runId,
                      messageId: null,
                      name: event.payload.name,
                      status: 'pending' as const,
                      args: event.payload.arguments,
                      startedAt: event.timestamp
                    }
                  ]
                }
              })
            } else if (event.type === 'tool.completed') {
              patchChat(id, prev => ({
                ...prev,
                tools: prev.tools.map(tool =>
                  tool.id === event.payload.toolCallId
                    ? {
                        ...tool,
                        status: event.payload.isError
                          ? ('error' as const)
                          : ('completed' as const),
                        result: event.payload.output,
                        durationSeconds: event.payload.durationSeconds,
                        endedAt: event.timestamp
                      }
                    : tool
                )
              }))
            } else if (event.type === 'todos.updated') {
              if (!event.runId) return
              patchChat(id, prev => ({
                ...prev,
                todosByRunId: {
                  ...prev.todosByRunId,
                  [event.runId as string]: event.payload.todos
                }
              }))
            } else if (event.type === 'run.usage') {
              const payload = event.payload as Record<string, unknown>
              const nextUsage = {
                inputTokens: Number(
                  payload.inputTokens ?? payload.input_tokens ?? 0
                ),
                outputTokens: Number(
                  payload.outputTokens ?? payload.output_tokens ?? 0
                )
              }
              patchChat(id, prev => ({
                ...prev,
                tokenUsage: nextUsage,
                usageByRunId: event.runId
                  ? {
                      ...prev.usageByRunId,
                      [event.runId as string]: nextUsage
                    }
                  : prev.usageByRunId
              }))
            } else if (event.type === 'assistant.message') {
              patchChat(id, prev => {
                const message = event.payload.message
                const messages = prev.messages.some(
                  item => item.id === message.id
                )
                  ? prev.messages
                  : [...prev.messages, message]
                return {
                  ...prev,
                  liveDelta: '',
                  messages,
                  messagesLoaded: true,
                  runIdByMessageId: event.runId
                    ? {
                        ...prev.runIdByMessageId,
                        [message.id]: event.runId as string
                      }
                    : prev.runIdByMessageId,
                  tools: event.runId
                    ? prev.tools.map(tool =>
                        tool.runId === event.runId
                          ? { ...tool, messageId: message.id }
                          : tool
                      )
                    : prev.tools
                }
              })
            } else if (
              event.type === 'run.completed' ||
              event.type === 'run.failed' ||
              event.type === 'run.interrupted'
            ) {
              const nextStatus =
                event.type === 'run.failed'
                  ? ('error' as const)
                  : event.type === 'run.interrupted'
                  ? ('interrupted' as const)
                  : ('idle' as const)
              patchChat(id, prev => ({
                ...prev,
                runActive: false,
                activeRunId: null,
                liveDelta: '',
                todosByRunId:
                  event.runId && prev.todosByRunId[event.runId]
                    ? {
                        ...prev.todosByRunId,
                        [event.runId]: prev.todosByRunId[event.runId].map(
                          todo =>
                            todo.status === 'in_progress'
                              ? { ...todo, status: 'completed' as const }
                              : todo
                        )
                      }
                    : prev.todosByRunId
              }))
              setSessions(current =>
                current.map(item =>
                  item.id === id ? { ...item, status: nextStatus } : item
                )
              )
              if (event.type === 'run.completed') {
                setWorkspaceVersion(current => current + 1)
              }
              void client.listMessages(id).then(history => {
                patchChat(id, prev => ({
                  ...prev,
                  messages: history,
                  messagesLoaded: true
                }))
              })
              void loadSessionsRef.current?.()
            }
          }
        })
        .catch((cause: unknown) => {
          if (!controller.signal.aborted && sessionIdRef.current === id) {
            setError(
              cause instanceof Error
                ? cause.message
                : 'Event stream disconnected'
            )
          }
        })
        .finally(() => {
          if (streamControllersRef.current.get(id) === controller) {
            streamControllersRef.current.delete(id)
          }
        })
    }
  }, [client, health, patchChat, runningSessionIdsKey, sessionId])

  useEffect(() => {
    if (!sessionId) return
    const justFinished =
      Boolean(prevRunActiveForTitleRef.current[sessionId]) && !runActive
    prevRunActiveForTitleRef.current[sessionId] = runActive
    if (!justFinished || autoTitleInFlightRef.current[sessionId]) return
    const conversationCount = messages.filter(
      message => message.role === 'user' || message.role === 'assistant'
    ).length
    if (conversationCount < AUTO_TITLE_FIRST_RESPONSE_THRESHOLD) return
    if (!isLowSignalTitle(session?.title || '')) return
    // Keep retrying while the stored title is still a placeholder (e.g. after
    // a bad overwrite). Cap attempts so intentional untitled chats settle.
    if ((autoTitlePassCountRef.current[sessionId] || 0) >= 3) return

    autoTitleInFlightRef.current[sessionId] = true
    const titledSessionId = sessionId
    void (async () => {
      try {
        const updated = await client.autoTitleSession(titledSessionId, {
          force: true
        })
        const title = String(updated.title || '').trim()
        if (!title) return
        setSessions(current =>
          current.map(item =>
            item.id === titledSessionId
              ? { ...item, title, updatedAt: updated.updatedAt }
              : item
          )
        )
        autoTitlePassCountRef.current[titledSessionId] =
          (autoTitlePassCountRef.current[titledSessionId] || 0) + 1
      } catch {
        // Best effort; retry on a later completed run.
      } finally {
        autoTitleInFlightRef.current[titledSessionId] = false
      }
    })()
  }, [client, messages, runActive, session?.title, sessionId])

  useEffect(() => {
    const name = skillRouteName
    if (!name) {
      setSkillDetail(null)
      return
    }
    const controller = new AbortController()
    void client
      .getSkill(decodeURIComponent(name), controller.signal)
      .then(setSkillDetail)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to load skill'
          )
        }
      })
    return () => controller.abort()
  }, [client, skillRouteName])

  useGlobalSearchHotkey(globalSearchOpen, setGlobalSearchOpen)

  const createSession = useCallback(
    async (projectId?: string | null) => {
      if (createSessionInFlightRef.current) return
      createSessionInFlightRef.current = true
      try {
        const id = projectId ?? activeProjectId ?? null
        const scopeKey = projectTabsKey(id)
        // New chats always start on Built-in. Modal starts only when the user
        // turns on the per-session Modal toggle in the composer.
        const created = await client.createSession({
          title: 'Untitled session',
          projectId: id || undefined,
          sandboxBackend: 'builtin'
        })
        if (id) {
          setProjectScopeId(id)
          setRecentProjectIds(current => {
            const next = [id, ...current.filter(item => item !== id)].slice(
              0,
              10
            )
            writeRecentProjectIds(next)
            return next
          })
        }
        patchOpenTabs(scopeKey, current =>
          current.includes(created.id) ? current : [...current, created.id]
        )
        // Skip chat skeleton flash — new sessions start empty.
        patchChat(created.id, {
          messages: [],
          messagesLoaded: true
        })
        setLastSessionByScope(current => {
          const next = { ...current, [scopeKey]: created.id }
          writeLastSessionByScope(next)
          return next
        })
        await loadSessions()
        if (id) await loadProjects()
        navigate(`/agents/${created.id}`)
      } catch (cause) {
        setError(
          cause instanceof Error ? cause.message : 'Unable to create agent'
        )
      } finally {
        createSessionInFlightRef.current = false
      }
    },
    [
      activeProjectId,
      client,
      loadProjects,
      loadSessions,
      navigate,
      patchChat,
      patchOpenTabs
    ]
  )

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return
      if (event.key.toLowerCase() !== 'n') return
      if (!(event.metaKey || event.ctrlKey)) return
      if (event.altKey || event.shiftKey) return
      event.preventDefault()
      void createSession(activeProjectId)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [activeProjectId, createSession])

  const closeSessionTab = (id: string) => {
    const scopeProjectId = activeProjectId
    const tabIsInScope = (tabId: string) => {
      const item = sessions.find(session => session.id === tabId)
      if (!item) return false
      if (!scopeProjectId) return true
      return item.projectId === scopeProjectId
    }

    let neighbor: string | null | undefined
    setOpenTabIds(current => {
      const index = current.indexOf(id)
      if (index === -1) return current
      const withoutClosed = current.filter(tabId => tabId !== id)
      // Drop tabs that don't belong in this project scope (e.g. leftover global tabs).
      const next = scopeProjectId
        ? withoutClosed.filter(tabIsInScope)
        : withoutClosed

      if (id === sessionId) {
        if (next.length === 0) {
          neighbor = null
        } else {
          const preferred = withoutClosed
            .slice(Math.min(index, withoutClosed.length))
            .concat(withoutClosed.slice(0, Math.min(index, withoutClosed.length)).reverse())
            .find(tabId => next.includes(tabId))
          neighbor = preferred || next[next.length - 1] || null
        }
      }
      return next
    })

    if (neighbor === undefined) return

    if (!neighbor) {
      setLastSessionByScope(current => {
        if (!(tabsScopeKey in current)) return current
        const next = { ...current }
        delete next[tabsScopeKey]
        writeLastSessionByScope(next)
        return next
      })
      navigate(scopeProjectId ? `/projects/${scopeProjectId}` : '/')
      return
    }

    navigate(`/agents/${neighbor}`)
  }

  const closeOtherSessionTabs = (keepId: string) => {
    setOpenTabIds(current => current.filter(id => id === keepId))
    if (sessionId !== keepId) navigate(`/agents/${keepId}`)
  }

  const sendMessage = async (composerOverride?: string) => {
    const composerText = composerOverride ?? composerLiveRef.current ?? composer
    const legacySkills = composerSkills
      .filter(name => !composerText.includes(`⟦/:${name}⟧`))
      .map(name => `/${name}`)
    const legacyFiles = composerFiles
      .filter(path => !composerText.includes(`⟦@:${path}⟧`))
      .map(path => `@${path}`)
    const content = [
      ...legacySkills,
      ...legacyFiles,
      composerToMessage(composerText)
    ]
      .filter(Boolean)
      .join(' ')
      .trim()
    if (!sessionId || !content || runActive) return
    const othersRunning = sessions.filter(
      item => item.status === 'running' && item.id !== sessionId
    ).length
    if (othersRunning + 1 >= CONCURRENT_RUN_HARD_LIMIT) {
      const proceed = window.confirm(
        `You already have ${othersRunning} agent${
          othersRunning === 1 ? '' : 's'
        } running. Browsers allow about 6 live connections to the local API, so files and chat can freeze with this many concurrent runs.\n\nStart another run anyway?`
      )
      if (!proceed) return
    } else if (othersRunning + 1 >= CONCURRENT_RUN_SOFT_LIMIT) {
      setConnectionLimitDismissed(false)
    }
    const targetSessionId = sessionId
    const previousComposer = composerText
    const previousSkills = composerSkills
    const previousFiles = composerFiles
    composerLiveRef.current = ''
    patchChat(targetSessionId, {
      composer: '',
      composerSkills: [],
      composerFiles: []
    })
    setError(null)
    try {
      await client.sendMessage(targetSessionId, content)
      patchChat(targetSessionId, prev => ({
        ...prev,
        runActive: true
      }))
      setSessions(current =>
        current.map(item =>
          item.id === targetSessionId
            ? { ...item, status: 'running' as const }
            : item
        )
      )
      const history = await client.listMessages(targetSessionId)
      patchChat(targetSessionId, prev => ({
        ...prev,
        messages: history,
        messagesLoaded: true
      }))
    } catch (cause) {
      composerLiveRef.current = previousComposer
      patchChat(targetSessionId, {
        composer: previousComposer,
        composerSkills: previousSkills,
        composerFiles: previousFiles
      })
      setError(
        cause instanceof Error ? cause.message : 'Unable to send message'
      )
    }
  }

  const clearComposerDraft = useCallback(
    (id: string) => {
      composerLiveRef.current = ''
      patchChat(id, {
        composer: '',
        composerSkills: [],
        composerFiles: []
      })
    },
    [patchChat]
  )

  const handleComposerSend = (text: string) => {
    if (!sessionId) return
    const trimmed = text.trim()
    if (!trimmed) return

    if (editingQueuedId) {
      patchChat(sessionId, prev => ({
        ...prev,
        queuedMessages: prev.queuedMessages.map(item =>
          item.id === editingQueuedId ? { ...item, text } : item
        )
      }))
      setEditingQueuedId(null)
      clearComposerDraft(sessionId)
      return
    }

    if (runActive) {
      patchChat(sessionId, prev => ({
        ...prev,
        queuedMessages: [
          ...prev.queuedMessages,
          { id: crypto.randomUUID(), text }
        ]
      }))
      clearComposerDraft(sessionId)
      return
    }

    void sendMessage(text)
  }

  const editQueuedMessage = (id: string) => {
    if (!sessionId) return
    const item = queuedMessages.find(message => message.id === id)
    if (!item) return
    setEditingQueuedId(id)
    composerLiveRef.current = item.text
    patchChat(sessionId, {
      composer: item.text,
      composerSkills: [],
      composerFiles: []
    })
  }

  const cancelEditQueuedMessage = () => {
    if (!sessionId) {
      setEditingQueuedId(null)
      return
    }
    setEditingQueuedId(null)
    clearComposerDraft(sessionId)
  }

  const removeQueuedMessage = (id: string) => {
    if (!sessionId) return
    if (editingQueuedId === id) {
      setEditingQueuedId(null)
      clearComposerDraft(sessionId)
    }
    patchChat(sessionId, prev => ({
      ...prev,
      queuedMessages: prev.queuedMessages.filter(item => item.id !== id)
    }))
  }

  const sendQueuedMessageNow = (id: string) => {
    if (!sessionId) return
    const item = queuedMessages.find(message => message.id === id)
    if (!item) return
    if (editingQueuedId === id) {
      setEditingQueuedId(null)
      clearComposerDraft(sessionId)
    }
    patchChat(sessionId, prev => ({
      ...prev,
      queuedMessages: prev.queuedMessages.filter(message => message.id !== id)
    }))
    if (runActive) {
      pendingImmediateSendRef.current = {
        sessionId,
        text: item.text
      }
      void client.interrupt(sessionId)
      return
    }
    void sendMessage(item.text)
  }

  useEffect(() => {
    if (!sessionId || runActive || drainingQueueRef.current) return

    const pending = pendingImmediateSendRef.current
    if (pending && pending.sessionId === sessionId) {
      pendingImmediateSendRef.current = null
      drainingQueueRef.current = true
      void sendMessage(pending.text).finally(() => {
        drainingQueueRef.current = false
      })
      return
    }

    const queued =
      chatBySessionIdRef.current[sessionId]?.queuedMessages ?? []
    if (queued.length === 0) return
    const next = queued[0]
    drainingQueueRef.current = true
    patchChat(sessionId, prev => ({
      ...prev,
      queuedMessages: prev.queuedMessages.filter(item => item.id !== next.id)
    }))
    void sendMessage(next.text).finally(() => {
      drainingQueueRef.current = false
    })
    // Drain when a run finishes or when the queue gains items while idle.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sendMessage closes over session state
  }, [runActive, sessionId, queuedMessages.length])

  const loadSkillDetail = useCallback(
    (name: string) => client.getSkill(name),
    [client]
  )

  const updateSession = async (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => {
    try {
      await client.updateSession(target.id, changes)
      await Promise.all([loadSessions(), loadProjects()])
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update agent'
      )
    }
  }

  const selectSessionSpecialist = async (specialistId: string | null) => {
    if (!session) return
    try {
      const updated = await client.updateSession(session.id, { specialistId })
      setSessions(current =>
        current.map(item => (item.id === updated.id ? updated : item))
      )
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update agent'
      )
    }
  }

  const refreshSessionSandbox = useCallback(
    async (targetSessionId?: string | null) => {
      const id = targetSessionId ?? sessionId
      if (!id) {
        setSessionSandboxStatus(null)
        return null
      }
      try {
        const status = await client.getSessionSandbox(id)
        if ((targetSessionId ?? sessionIdRef.current) === id) {
          setSessionSandboxStatus(status)
          if (status.status === 'starting') {
            setSessionSandboxPhase('starting')
            sandboxActionSessionRef.current = id
          } else if (status.status === 'stopping') {
            setSessionSandboxPhase('stopping')
            sandboxActionSessionRef.current = id
          } else if (status.status === 'running') {
            if (sandboxActionSessionRef.current === id) {
              sandboxActionSessionRef.current = null
            }
            setSessionSandboxPhase('idle')
          } else if (
            (status.status === 'stopped' ||
              status.status === 'unavailable' ||
              status.status === 'ready') &&
            sandboxActionSessionRef.current !== id
          ) {
            setSessionSandboxPhase('idle')
          }
        }
        return status
      } catch {
        if ((targetSessionId ?? sessionIdRef.current) === id) {
          setSessionSandboxStatus(null)
        }
        return null
      }
    },
    [client, sessionId]
  )

  // Safety-net poll while provisioning, matching cloud agent-ide behavior.
  useEffect(() => {
    if (!sessionId || !health) return
    const pending =
      sessionSandboxPhase !== 'idle' ||
      sessionSandboxStatus?.status === 'starting' ||
      sessionSandboxStatus?.status === 'stopping'
    if (!pending) return
    const timer = window.setInterval(() => {
      void refreshSessionSandbox(sessionId)
    }, 2500)
    return () => window.clearInterval(timer)
  }, [
    health,
    refreshSessionSandbox,
    sessionId,
    sessionSandboxPhase,
    sessionSandboxStatus?.status
  ])

  const selectSessionSandboxBackend = async (
    backend: 'builtin' | 'modal'
  ) => {
    if (!session) return
    if (
      backend === 'modal' &&
      sessionSandboxStatus?.modalConfigured !== true
    ) {
      return
    }
    const targetId = session.id
    try {
      if (backend === 'builtin' && sessionSandboxStatus?.status === 'running') {
        sandboxActionSessionRef.current = targetId
        setSessionSandboxPhase('stopping')
        try {
          await client.stopSessionSandbox(targetId)
        } catch {
          // Best-effort stop when leaving Modal for this chat.
        } finally {
          if (sandboxActionSessionRef.current === targetId) {
            sandboxActionSessionRef.current = null
          }
          if (sessionIdRef.current === targetId) {
            setSessionSandboxPhase('idle')
          }
        }
      }
      await client.updateSession(targetId, { sandboxBackend: backend })
      await Promise.all([loadSessions(), loadProjects()])
      const status = await refreshSessionSandbox(targetId)
      if (
        backend === 'modal' &&
        status?.modalConfigured !== false &&
        status?.status !== 'running'
      ) {
        sandboxActionSessionRef.current = targetId
        setSessionSandboxPhase('starting')
        void client
          .startSessionSandbox(targetId)
          .then(next => {
            if (sessionIdRef.current === targetId) {
              setSessionSandboxStatus(next)
            }
          })
          .catch(cause => {
            setError(
              cause instanceof Error
                ? cause.message
                : 'Unable to start sandbox'
            )
            void refreshSessionSandbox(targetId)
          })
          .finally(() => {
            if (sandboxActionSessionRef.current === targetId) {
              sandboxActionSessionRef.current = null
            }
            if (sessionIdRef.current === targetId) {
              setSessionSandboxPhase('idle')
            }
          })
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Unable to update sandbox backend'
      )
      await refreshSessionSandbox(targetId)
      setSessionSandboxPhase('idle')
      sandboxActionSessionRef.current = null
    }
  }

  const startSessionSandbox = async () => {
    if (!sessionId) return
    const targetId = sessionId
    if (sessionSandboxPhase !== 'idle') return
    sandboxActionSessionRef.current = targetId
    setSessionSandboxPhase('starting')
    try {
      const status = await client.startSessionSandbox(targetId)
      if (sessionIdRef.current === targetId) {
        setSessionSandboxStatus(status)
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to start sandbox'
      )
      await refreshSessionSandbox(targetId)
    } finally {
      if (sandboxActionSessionRef.current === targetId) {
        sandboxActionSessionRef.current = null
      }
      if (sessionIdRef.current === targetId) {
        setSessionSandboxPhase('idle')
      }
    }
  }

  const stopSessionSandbox = async () => {
    if (!sessionId) return
    const targetId = sessionId
    if (sessionSandboxPhase !== 'idle') return
    sandboxActionSessionRef.current = targetId
    setSessionSandboxPhase('stopping')
    try {
      const status = await client.stopSessionSandbox(targetId)
      if (sessionIdRef.current === targetId) {
        setSessionSandboxStatus(status)
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to stop sandbox'
      )
      await refreshSessionSandbox(targetId)
    } finally {
      if (sandboxActionSessionRef.current === targetId) {
        sandboxActionSessionRef.current = null
      }
      if (sessionIdRef.current === targetId) {
        setSessionSandboxPhase('idle')
      }
    }
  }

  const restartSessionSandbox = async () => {
    if (!sessionId) return
    const targetId = sessionId
    if (sessionSandboxPhase !== 'idle') return
    sandboxActionSessionRef.current = targetId
    setSessionSandboxPhase('restarting')
    try {
      const status = await client.restartSessionSandbox(targetId)
      if (sessionIdRef.current === targetId) {
        setSessionSandboxStatus(status)
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to restart sandbox'
      )
      await refreshSessionSandbox(targetId)
    } finally {
      if (sandboxActionSessionRef.current === targetId) {
        sandboxActionSessionRef.current = null
      }
      if (sessionIdRef.current === targetId) {
        setSessionSandboxPhase('idle')
      }
    }
  }

  const updateSessionSandboxCompute = async (changes: {
    computeType: 'cpu' | 'gpu'
    gpuClass: string
    cpuCores: number
    ramGb: number
  }) => {
    try {
      const next = await client.updateSandboxSettings(changes)
      setSandboxSettings(next)
      setSessionSandboxStatus(current =>
        current
          ? {
              ...current,
              computeType: next.computeType,
              gpuClass: next.gpuClass,
              cpuCores: next.cpuCores,
              ramGb: next.ramGb,
              cpuImage:
                next.computeType === 'gpu' ? next.gpuImage : next.cpuImage
            }
          : current
      )
      if (sessionId) await refreshSessionSandbox(sessionId)
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Unable to update sandbox compute'
      )
    }
  }

  const createProject = async (input: {
    name: string
    description: string
    agentContext: string
  }) => {
    try {
      const project = await client.createProject(input)
      await loadProjects()
      setProjectScopeId(project.id)
      setRecentProjectIds(current => {
        const next = [
          project.id,
          ...current.filter(item => item !== project.id)
        ].slice(0, 10)
        writeRecentProjectIds(next)
        return next
      })
      navigate(`/projects/${project.id}`)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to create project'
      )
      throw cause
    }
  }

  const saveProjectSettings = async (input: {
    name: string
    description: string
    agentContext: string
  }) => {
    if (!activeProject) return
    try {
      await client.updateProject(activeProject.id, {
        name: input.name,
        description: input.description || null,
        agentContext: input.agentContext || null
      })
      await loadProjects()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update project'
      )
      throw cause
    }
  }

  const landingPathForScope = useCallback(
    (scopeId: string | null) => {
      const key = projectTabsKey(scopeId)
      const tabs = (openTabsByProject[key] || []).filter(id => {
        const item = sessions.find(session => session.id === id)
        if (!item) return false
        if (!scopeId) return true
        return item.projectId === scopeId
      })
      if (tabs.length === 0) {
        return scopeId ? `/projects/${scopeId}` : '/'
      }
      const last = lastSessionByScope[key]
      const target =
        last && tabs.includes(last) ? last : tabs[tabs.length - 1]
      return `/agents/${target}`
    },
    [lastSessionByScope, openTabsByProject, sessions]
  )

  const selectAllProjects = () => {
    setProjectScopeId(null)
    navigate(landingPathForScope(null))
  }

  const selectProjectScope = (projectId: string) => {
    setProjectScopeId(projectId)
    setRecentProjectIds(current => {
      const next = [
        projectId,
        ...current.filter(item => item !== projectId)
      ].slice(0, 10)
      writeRecentProjectIds(next)
      return next
    })
    navigate(landingPathForScope(projectId))
  }

  const togglePinProject = async (project: AgentProject) => {
    try {
      await client.updateProject(project.id, { pinned: !project.pinned })
      await loadProjects()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update project'
      )
    }
  }

  const deleteProject = async (project: AgentProject) => {
    try {
      await client.deleteProject(project.id)
      setOpenTabsByProject(current => {
        if (!(project.id in current)) return current
        const next = { ...current }
        delete next[project.id]
        writeOpenTabsByProject(next)
        return next
      })
      setLastSessionByScope(current => {
        if (!(project.id in current)) return current
        const next = { ...current }
        delete next[project.id]
        writeLastSessionByScope(next)
        return next
      })
      if (activeProjectId === project.id) {
        setProjectScopeId(null)
        navigate('/')
      }
      await Promise.all([loadProjects(), loadSessions()])
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to delete project'
      )
    }
  }

  const deleteSession = async (target: AgentSession) => {
    await client.deleteSession(target.id)
    let neighbor: string | null = null
    let scopeEmpty = false
    const scopeProjectId = activeProjectId
    setOpenTabsByProject(current => {
      let changed = false
      const next: Record<string, string[]> = {}
      for (const [key, ids] of Object.entries(current)) {
        if (!ids.includes(target.id) && key !== tabsScopeKey) {
          next[key] = ids
          continue
        }
        const withoutTarget = ids.filter(id => id !== target.id)
        const filtered =
          key === tabsScopeKey && scopeProjectId
            ? withoutTarget.filter(id => {
                const item = sessions.find(session => session.id === id)
                return Boolean(item && item.projectId === scopeProjectId)
              })
            : withoutTarget
        if (filtered.length !== ids.length) changed = true
        if (key === tabsScopeKey) {
          neighbor = filtered[0] || null
          scopeEmpty = filtered.length === 0
        }
        if (filtered.length > 0) next[key] = filtered
        else if (ids.length > 0) changed = true
      }
      if (!changed) return current
      writeOpenTabsByProject(next)
      return next
    })
    if (scopeEmpty) {
      setLastSessionByScope(current => {
        if (!(tabsScopeKey in current)) return current
        const next = { ...current }
        delete next[tabsScopeKey]
        writeLastSessionByScope(next)
        return next
      })
    }
    setChatBySessionId(current => {
      if (!current[target.id]) return current
      const next = { ...current }
      delete next[target.id]
      return next
    })
    await loadSessions()
    if (target.id === sessionId) {
      navigate(
        neighbor
          ? `/agents/${neighbor}`
          : scopeProjectId
            ? `/projects/${scopeProjectId}`
            : '/'
      )
    }
  }

  const openRenameDialog = (target: AgentSession) => {
    setRenameTarget(target)
    setRenameValue(target.title || '')
  }

  const submitRename = async () => {
    const title = renameValue.trim()
    if (!renameTarget || !title) return
    await updateSession(renameTarget, { title })
    setRenameTarget(null)
    setRenameValue('')
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    const target = deleteTarget
    setDeleteTarget(null)
    await deleteSession(target)
  }

  const exportTranscript = async (target: AgentSession) => {
    const [messages, events] = await Promise.all([
      client.listMessages(target.id),
      client.listEventHistory(target.id).catch(() => [] as AgentEvent[])
    ])
    const markdown = formatSessionExportMarkdown({
      title: target.title,
      messages,
      events
    })
    const url = URL.createObjectURL(
      new Blob([markdown], { type: 'text/markdown' })
    )
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${target.title
      .replace(/[^a-z0-9]+/gi, '-')
      .toLowerCase()}.md`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const clearSessionSelection = useCallback(() => {
    setSelectedSessionIds(new Set())
    setSelectionAnchorId(null)
  }, [])

  const selectedSessions = useMemo(
    () => sessions.filter(item => selectedSessionIds.has(item.id)),
    [sessions, selectedSessionIds]
  )

  useEffect(() => {
    setSelectedSessionIds(current => {
      if (current.size === 0) return current
      const valid = new Set(sessions.map(item => item.id))
      let changed = false
      const next = new Set<string>()
      for (const id of current) {
        if (valid.has(id)) next.add(id)
        else changed = true
      }
      return changed ? next : current
    })
  }, [sessions])

  useEffect(() => {
    if (selectedSessionIds.size === 0) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        clearSessionSelection()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [clearSessionSelection, selectedSessionIds.size])

  const selectSessionRange = (orderedIds: string[], targetId: string) => {
    const anchor = selectionAnchorId
    if (!anchor) {
      setSelectedSessionIds(new Set([targetId]))
      setSelectionAnchorId(targetId)
      return
    }
    const start = orderedIds.indexOf(anchor)
    const end = orderedIds.indexOf(targetId)
    if (start < 0 || end < 0) {
      setSelectedSessionIds(new Set([targetId]))
      setSelectionAnchorId(targetId)
      return
    }
    const [lo, hi] = start < end ? [start, end] : [end, start]
    setSelectedSessionIds(new Set(orderedIds.slice(lo, hi + 1)))
  }

  const toggleSessionSelected = (targetId: string) => {
    setSelectedSessionIds(current => {
      const next = new Set(current)
      if (next.has(targetId)) next.delete(targetId)
      else next.add(targetId)
      return next
    })
    setSelectionAnchorId(targetId)
  }

  const batchArchiveSelected = async () => {
    if (selectedSessions.length === 0 || batchBusy) return
    setBatchBusy(true)
    setError(null)
    try {
      await Promise.all(
        selectedSessions.map(item =>
          client.updateSession(item.id, { organizeLabel: 'archive' })
        )
      )
      setCollapsedSidebarSections(current => ({
        ...current,
        archive: false
      }))
      clearSessionSelection()
      await loadSessions()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to archive sessions'
      )
    } finally {
      setBatchBusy(false)
    }
  }

  const batchMoveSelected = async (projectId: string | null) => {
    if (selectedSessions.length === 0 || batchBusy) return
    setBatchBusy(true)
    setError(null)
    try {
      await Promise.all(
        selectedSessions.map(item =>
          client.updateSession(item.id, { projectId })
        )
      )
      clearSessionSelection()
      await loadSessions()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to move sessions'
      )
    } finally {
      setBatchBusy(false)
    }
  }

  const batchExportSelected = async () => {
    if (selectedSessions.length === 0 || batchBusy) return
    setBatchBusy(true)
    setError(null)
    try {
      for (const item of selectedSessions) {
        await exportTranscript(item)
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to export sessions'
      )
    } finally {
      setBatchBusy(false)
    }
  }

  const confirmBatchDelete = async () => {
    if (selectedSessions.length === 0) return
    setBatchDeletePending(false)
    setBatchBusy(true)
    setError(null)
    const targets = [...selectedSessions]
    clearSessionSelection()
    try {
      for (const target of targets) {
        await deleteSession(target)
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to delete sessions'
      )
    } finally {
      setBatchBusy(false)
    }
  }

  const setComposer = useCallback(
    (value: string | ((current: string) => string)) => {
      if (!sessionId) return
      patchChat(sessionId, prev => {
        const next =
          typeof value === 'function'
            ? value(composerLiveRef.current)
            : value
        composerLiveRef.current = next
        return {
          ...prev,
          composer: next
        }
      })
    },
    [patchChat, sessionId]
  )

  const setComposerSkills = useCallback(
    (value: string[] | ((current: string[]) => string[])) => {
      if (!sessionId) return
      patchChat(sessionId, prev => ({
        ...prev,
        composerSkills:
          typeof value === 'function' ? value(prev.composerSkills) : value
      }))
    },
    [patchChat, sessionId]
  )

  const setComposerFiles = useCallback(
    (value: string[] | ((current: string[]) => string[])) => {
      if (!sessionId) return
      patchChat(sessionId, prev => ({
        ...prev,
        composerFiles:
          typeof value === 'function' ? value(prev.composerFiles) : value
      }))
    },
    [patchChat, sessionId]
  )

  useEffect(() => {
    const path = pendingMentionRef.current
    if (!sessionId || !path) return
    pendingMentionRef.current = null
    setComposer(current => `${current}${fileChipToken(path)}`)
    setComposerFiles([])
  }, [sessionId, setComposer, setComposerFiles])

  const displayedSessions = activeProjectId
    ? sessions.filter(item => item.projectId === activeProjectId)
    : sessions
  const sections = groupSessions(displayedSessions)
  const orderedVisibleSessionIds = useMemo(
    () => visibleSessionIds(sections, collapsedSidebarSections),
    [sections, collapsedSidebarSections]
  )
  const openTabs = openTabIds
    .map(id => sessions.find(item => item.id === id))
    .filter((item): item is AgentSession => Boolean(item))
    .filter(
      item => !activeProjectId || item.projectId === activeProjectId
    )
  const showSessionTabs =
    !isDashboard &&
    !isHome &&
    !isProjectHome &&
    !isSkills &&
    !isIntegrations &&
    (Boolean(sessionId) || openTabs.length > 0)
  const activeTitle = isDashboardOverview
    ? 'Overview'
    : isDashboardStatus
    ? 'Status'
    : isDashboardGeneral
    ? 'General'
    : isDashboardAgentRuntime
    ? 'Runtime'
    : isDashboardAgentPrompts
    ? 'Prompts'
    : isDashboardModels
    ? 'Models'
    : isDashboardData
    ? 'Datasets'
    : isDashboardTools
    ? 'Tools'
    : isDashboardDoctor
    ? 'Doctor'
    : isDashboardStorage
    ? 'Storage'
    : isDashboardEnvironment
    ? 'Environment'
    : isSkills
    ? 'Skills'
    : isDashboardSpecialists
    ? 'Specialists'
    : isIntegrations
    ? 'Integrations'
    : isDashboardMcp
    ? 'MCPs'
    : isHome || isProjectHome
    ? 'Home'
    : session?.title || 'New Chat'
  const canShowFilesPanel = Boolean(sessionId)
  const conversationTimeline = useMemo(
    () =>
      buildConversationTimeline({
        messages,
        tools,
        todosByRunId,
        runIdByMessageId,
        activeRunId
      }),
    [activeRunId, messages, runIdByMessageId, todosByRunId, tools]
  )

  const scrollChatToBottom = useCallback(() => {
    const root = chatScrollRef.current
    const viewport = root?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (viewport) {
      viewport.scrollTop = viewport.scrollHeight
      setShowScrollToBottom(false)
      return
    }
    chatEndRef.current?.scrollIntoView({ block: 'end' })
    setShowScrollToBottom(false)
  }, [])

  const updateScrollToBottomVisibility = useCallback(() => {
    const root = chatScrollRef.current
    const viewport = root?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (!viewport) {
      setShowScrollToBottom(false)
      return
    }
    const distanceFromBottom =
      viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight
    setShowScrollToBottom(distanceFromBottom > 96)
  }, [])

  useEffect(() => {
    if (!sessionId || !messagesLoaded || messages.length === 0) {
      setShowScrollToBottom(false)
      return
    }
    const root = chatScrollRef.current
    const viewport = root?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (!viewport) return

    updateScrollToBottomVisibility()
    viewport.addEventListener('scroll', updateScrollToBottomVisibility, {
      passive: true
    })
    const observer = new ResizeObserver(() => updateScrollToBottomVisibility())
    observer.observe(viewport)
    const content = viewport.firstElementChild
    if (content) observer.observe(content)

    return () => {
      viewport.removeEventListener('scroll', updateScrollToBottomVisibility)
      observer.disconnect()
    }
  }, [
    conversationTimeline.length,
    messages.length,
    messagesLoaded,
    sessionId,
    updateScrollToBottomVisibility
  ])

  const chatPinnedSessionRef = useRef<string | null>(null)

  // Show the latest message when opening/loading a session with history.
  // Only pin once per session — do not keep forcing scroll while streaming.
  useLayoutEffect(() => {
    if (!sessionId || !messagesLoaded || messages.length === 0) return
    if (chatPinnedSessionRef.current === sessionId) return
    chatPinnedSessionRef.current = sessionId
    scrollChatToBottom()
    const frame = window.requestAnimationFrame(() => scrollChatToBottom())
    const timers = [80, 250, 600].map(ms =>
      window.setTimeout(() => scrollChatToBottom(), ms)
    )
    return () => {
      window.cancelAnimationFrame(frame)
      for (const timer of timers) window.clearTimeout(timer)
    }
  }, [messages.length, messagesLoaded, scrollChatToBottom, sessionId])

  const activeRunTodos = activeRunId ? todosByRunId[activeRunId] || [] : []
  const activeRunTools = activeRunId
    ? tools.filter(tool => tool.runId === activeRunId && !tool.messageId)
    : []

  if (!authBootstrapped && !needsAuthLogin) {
    return (
      <main className="grid min-h-full place-items-center bg-[#f5f5f5] dark:bg-neutral-950">
        <AuraIconPulse className="text-muted-foreground/50 h-12 w-12" />
      </main>
    )
  }

  if (needsAuthLogin) {
    return (
      <LoginView
        submitting={authLoggingIn || connecting}
        error={authLoginError}
        onRetry={() => {
          setAuthLoginError(null)
          void connect()
        }}
        onSubmit={submitAuthLogin}
      />
    )
  }

  if (!health) {
    const isLocalBackend = /127\.0\.0\.1|localhost/i.test(backendUrl)
    const backendDown = Boolean(error) && isBackendUnavailableError(error)
    const connectError = error
      ? errorStack
        ? Object.assign(new Error(error), { stack: errorStack })
        : error
      : null

    // Local Mac / Vite dashboard: don't show the remote "Connect to backend"
    // form. Wait for the API, then connect() sends you to Login when auth is on.
    if (isLocalBackend) {
      return (
        <main className="bg-background grid h-full place-items-center p-6">
          <div className="bg-card w-full max-w-md space-y-4 rounded-xl border p-6 text-center">
            <div className="flex flex-col items-center gap-3">
              <div className="bg-primary text-primary-foreground grid size-10 place-items-center rounded-lg">
                <SandwalkMark className="h-6 w-6" />
              </div>
              <div>
                <h1 className="font-semibold">sandwalk</h1>
                <p className="text-muted-foreground mt-1 text-sm">
                  {backendDown
                    ? 'Local agent API error'
                    : connecting
                      ? 'Waiting for the local agent API…'
                      : 'Connecting…'}
                </p>
              </div>
              {(connecting && !connectError) && (
                <Loader2 className="text-muted-foreground size-5 animate-spin" />
              )}
            </div>
            {connectError ? (
              <ErrorPage
                className="text-left"
                variant="inline"
                error={connectError}
                onRetry={() => void connect()}
                retryLabel="Retry"
              />
            ) : null}
            {!connectError ? (
              <Button
                className="w-full"
                disabled={connecting}
                onClick={() => void connect()}
              >
                {connecting ? <Loader2 className="animate-spin" /> : null}
                Retry
              </Button>
            ) : null}
          </div>
        </main>
      )
    }

    return (
      <main className="bg-background grid h-full place-items-center p-6">
        <form
          className="bg-card w-full max-w-lg rounded-xl border p-6"
          onSubmit={event => {
            event.preventDefault()
            void connect()
          }}
        >
          <div className="mb-6 flex items-center gap-3">
            <div className="bg-primary text-primary-foreground grid size-10 place-items-center rounded-lg">
              <SandwalkMark className="h-6 w-6" />
            </div>
            <div>
              <h1 className="font-semibold">sandwalk</h1>
              <p className="text-muted-foreground text-sm">
                Connect to an agent backend
              </p>
            </div>
          </div>
          <Input
            value={backendUrl}
            onChange={event => setBackendUrl(event.target.value)}
          />
          <Input
            className="mt-2"
            type="password"
            value={backendApiKey}
            onChange={event => setBackendApiKey(event.target.value)}
            placeholder="Backend API key (remote servers only)"
          />
          {error ? (
            <ErrorPage
              className="mt-3"
              variant="inline"
              error={
                errorStack
                  ? Object.assign(new Error(error), { stack: errorStack })
                  : error
              }
            />
          ) : null}
          <Button className="mt-4 w-full" disabled={connecting}>
            {connecting ? <Loader2 className="animate-spin" /> : null}
            Connect
          </Button>
        </form>
      </main>
    )
  }

  // Dedicated setup pages — no dashboard chrome.
  if (onOnboardingPath) {
    return (
      <div className="h-full min-h-0 overflow-hidden">
        <OnboardingWizardHost
          step={onboardingStep}
          client={client}
          onStepChange={next => {
            const clamped = clampOnboardingStep(next)
            void client
              .updateOnboardingSettings({ step: clamped })
              .catch(() => {})
            navigate(onboardingPath(clamped))
          }}
          onFinish={() => {
            void client
              .updateOnboardingSettings({
                completed: true,
                step: ONBOARDING_MAX_STEP
              })
              .catch(() => {})
            void loadModelOptions()
            void loadIntegrations()
            void loadSkills()
            void loadMcpServers()
            void loadMcpCatalog()
            navigate('/', { replace: true })
          }}
          onExit={() => navigate('/')}
        />
      </div>
    )
  }

  return (
    <>
      <ResizablePanelGroup
        direction="horizontal"
        autoSaveId={SHELL_PANELS_AUTO_SAVE_ID}
        className="bg-background h-full w-full overflow-hidden"
      >
        <ResizablePanel
          id="sidebar"
          order={1}
          ref={sidebarPanelRef}
          collapsible
          collapsedSize={0}
          defaultSize={18}
          minSize={12}
          maxSize={30}
          onCollapse={() => setSidebarCollapsed(true)}
          onExpand={() => setSidebarCollapsed(false)}
          className="min-w-0"
        >
        <aside className="bg-sidebar flex h-full flex-col overflow-hidden">
          {isDashboard ? (
            <DashboardSidebar
              active={dashboardSection}
              userName={sidebarUserName}
              onCollapse={() => setSidebarCollapsed(true)}
              onLogout={logoutSession}
              onRefreshUser={refreshCloudUserName}
              backendVersion={health?.version ?? null}
              backendUrl={backendUrl}
              connected={Boolean(health)}
            />
          ) : (
            <>
          <div className="shrink-0 p-3">
            <div className="mb-2 flex items-center gap-1">
              <button
                type="button"
                className="hover:bg-sidebar-accent/70 inline-flex size-8 shrink-0 items-center justify-center rounded-md"
                onClick={() => {
                  setProjectScopeId(null)
                  navigate('/')
                }}
                aria-label="Home"
                title="Home"
              >
                <SandwalkMark className="h-5 w-5" />
              </button>
              <ProjectSelector
                projects={projects}
                value={activeProjectId}
                onSelectAll={selectAllProjects}
                onSelectProject={selectProjectScope}
                onOpenSettings={() => setProjectSettingsOpen(true)}
                onNewProject={() => setNewProjectOpen(true)}
              />
              <div className="min-w-0 flex-1" />
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 shrink-0"
                      onClick={() => setGlobalSearchOpen(true)}
                      aria-label="Search"
                    >
                      <Search className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">Search ⌘K</TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 shrink-0"
                onClick={() => setSidebarCollapsed(true)}
                aria-label="Hide sidebar"
              >
                <PanelLeft className="size-4" />
              </Button>
            </div>
            <button
              type="button"
              className="text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground flex w-full items-center justify-between rounded-md px-2 py-1.5 text-[13px]"
              onClick={() => void createSession(activeProjectId)}
            >
              <span className="inline-flex items-center gap-2">
                <Send className="size-3.5" />
                New Agent
              </span>
              <span className="text-muted-foreground/70 text-[11px]">⌘N</span>
            </button>
            {canShowFilesPanel ? (
              <button
                type="button"
                className={cn(
                  'mt-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[13px]',
                  !filesPanelCollapsed
                    ? 'bg-sidebar-accent text-foreground'
                    : 'text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground'
                )}
                onClick={() => setFilesPanelCollapsed(current => !current)}
              >
                <Folder className="size-3.5" />
                Files
              </button>
            ) : null}
            <button
              type="button"
              className="text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground mt-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[13px]"
              onClick={() => navigate('/dashboard')}
            >
              <LayoutDashboard className="size-3.5" />
              Dashboard
            </button>
          </div>
          {selectedSessionIds.size > 0 ? (
            <div className="border-border/60 mx-2 mb-1 space-y-2 rounded-lg border bg-sidebar-accent/40 px-2.5 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-foreground text-[12px] font-medium">
                  {selectedSessionIds.size} selected
                </span>
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground inline-flex size-6 items-center justify-center rounded-md"
                  aria-label="Clear selection"
                  disabled={batchBusy}
                  onClick={clearSessionSelection}
                >
                  <X className="size-3.5" />
                </button>
              </div>
              <div className="flex flex-wrap gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-[11px]"
                  disabled={batchBusy}
                  onClick={() => void batchArchiveSelected()}
                >
                  <Archive className="size-3" />
                  Archive
                </Button>
                <ProjectPicker
                  projects={projects}
                  value={null}
                  disabled={batchBusy}
                  noneLabel="No project"
                  trigger={
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-7 px-2 text-[11px]"
                      disabled={batchBusy}
                    >
                      <Folder className="size-3" />
                      Move
                    </Button>
                  }
                  onChange={projectId => {
                    void batchMoveSelected(projectId)
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-[11px]"
                  disabled={batchBusy}
                  onClick={() => void batchExportSelected()}
                >
                  <Download className="size-3" />
                  Export
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="text-destructive hover:text-destructive h-7 px-2 text-[11px]"
                  disabled={batchBusy}
                  onClick={() => setBatchDeletePending(true)}
                >
                  <Trash2 className="size-3" />
                  Delete
                </Button>
              </div>
              <p className="text-muted-foreground text-[10px] leading-snug">
                Shift+click range · ⌘/Ctrl+click toggle · Esc clears
              </p>
            </div>
          ) : null}
          <ScrollArea className="flex-1">
            <div className="space-y-3 p-3">
              {sections.length === 0 ? (
                <p className="text-muted-foreground px-1.5 py-2 text-[13px]">
                  No Agents Yet
                </p>
              ) : (
              sections.map(section => {
                const collapsed = Boolean(collapsedSidebarSections[section.id])
                return (
                  <div key={section.id} className="space-y-1">
                    <button
                      type="button"
                      className="text-muted-foreground/80 hover:text-foreground flex w-full items-center gap-1 rounded-md px-1.5 py-0.5 text-left text-[13px]"
                      aria-expanded={!collapsed}
                      onClick={() =>
                        setCollapsedSidebarSections(current => ({
                          ...current,
                          [section.id]: !current[section.id]
                        }))
                      }
                    >
                      <ChevronDown
                        className={cn(
                          'size-3.5 shrink-0 transition-transform',
                          collapsed && '-rotate-90'
                        )}
                      />
                      <span className="min-w-0 flex-1 truncate">
                        {section.title}
                      </span>
                      <span className="text-muted-foreground/60 shrink-0 text-[11px] tabular-nums">
                        {section.items.length}
                      </span>
                    </button>
                    {!collapsed ? (
                      <ul className="space-y-0.5">
                        {section.items.map(item => {
                          const isSelected = selectedSessionIds.has(item.id)
                          return (
                          <li key={item.id}>
                            <div
                              className={cn(
                                'hover:bg-sidebar-accent/70 group grid grid-cols-[minmax(0,1fr)_2.75rem] items-center rounded px-1.5 py-1.5',
                                item.id === sessionId && 'bg-sidebar-accent',
                                isSelected &&
                                  'bg-sidebar-accent ring-primary/30 ring-1'
                              )}
                            >
                              <button
                                type="button"
                                className="flex min-w-0 items-center gap-1.5 text-left"
                                onClick={event => {
                                  if (event.shiftKey) {
                                    event.preventDefault()
                                    selectSessionRange(
                                      orderedVisibleSessionIds,
                                      item.id
                                    )
                                    return
                                  }
                                  if (event.metaKey || event.ctrlKey) {
                                    event.preventDefault()
                                    toggleSessionSelected(item.id)
                                    return
                                  }
                                  if (selectedSessionIds.size > 0) {
                                    clearSessionSelection()
                                  }
                                  setSelectionAnchorId(item.id)
                                  openSessionTab(item.id)
                                  void prefetchSessionMessages(item.id)
                                  navigate(`/agents/${item.id}`)
                                }}
                              >
                                {isSelected || selectedSessionIds.size > 0 ? (
                                  <span
                                    className={cn(
                                      'grid size-3.5 shrink-0 place-items-center rounded-[4px] border',
                                      isSelected
                                        ? 'border-primary bg-primary text-primary-foreground'
                                        : 'border-muted-foreground/40'
                                    )}
                                    aria-hidden
                                  >
                                    {isSelected ? (
                                      <Check className="size-2.5" strokeWidth={3} />
                                    ) : null}
                                  </span>
                                ) : (
                                  <SessionStatusIcon
                                    status={
                                      chatBySessionId[item.id]?.runActive
                                        ? 'running'
                                        : item.status
                                    }
                                  />
                                )}
                                {item.organizeLabel === 'pinned' ? (
                                  <Pin className="text-muted-foreground/70 size-3 shrink-0" />
                                ) : null}
                                <span className="text-foreground/90 group-hover:text-foreground truncate text-[13px]">
                                  {item.title || 'Untitled'}
                                </span>
                              </button>
                              <div className="relative h-7 w-11 justify-self-end">
                                <span
                                  className={cn(
                                    'text-muted-foreground/70 pointer-events-none absolute inset-0 flex items-center justify-end pr-0.5 text-[11px] transition-opacity',
                                    threadMenuOpenId === item.id
                                      ? 'opacity-0'
                                      : 'opacity-100 group-hover:opacity-0'
                                  )}
                                >
                                  {relativeTime(
                                    item.lastMessageAt || item.updatedAt
                                  )}
                                </span>
                                <Popover
                                  open={threadMenuOpenId === item.id}
                                  onOpenChange={open => {
                                    setThreadMenuOpenId(open ? item.id : null)
                                  }}
                                >
                                  <PopoverTrigger asChild>
                                    <button
                                      type="button"
                                      className={cn(
                                        'text-muted-foreground hover:bg-muted absolute right-0 top-0 inline-flex h-7 w-7 items-center justify-center rounded-md',
                                        threadMenuOpenId === item.id
                                          ? 'opacity-100'
                                          : 'opacity-0 group-hover:opacity-100'
                                      )}
                                      aria-label="Thread options"
                                    >
                                      <MoreHorizontal className="h-4 w-4" />
                                    </button>
                                  </PopoverTrigger>
                                  <PopoverContent
                                    align="start"
                                    className="w-44 p-1.5"
                                  >
                                    <SessionActionsMenu
                                      session={item}
                                      projects={projects}
                                      onRename={() => {
                                        setThreadMenuOpenId(null)
                                        openRenameDialog(item)
                                      }}
                                      onTogglePin={() => {
                                        setThreadMenuOpenId(null)
                                        void updateSession(item, {
                                          organizeLabel:
                                            item.organizeLabel === 'pinned'
                                              ? null
                                              : 'pinned'
                                        })
                                      }}
                                      onMoveToProject={projectId => {
                                        setThreadMenuOpenId(null)
                                        void updateSession(item, { projectId })
                                      }}
                                      onExport={() => {
                                        setThreadMenuOpenId(null)
                                        void exportTranscript(item)
                                      }}
                                      onInspect={() => {
                                        setThreadMenuOpenId(null)
                                        navigate(
                                          `/agents/${item.id}?inspect=1`
                                        )
                                      }}
                                      onArchive={() => {
                                        setThreadMenuOpenId(null)
                                        const nextLabel =
                                          item.organizeLabel === 'archive'
                                            ? null
                                            : 'archive'
                                        void updateSession(item, {
                                          organizeLabel: nextLabel
                                        })
                                        if (nextLabel === 'archive') {
                                          setCollapsedSidebarSections(
                                            current => ({
                                              ...current,
                                              archive: false
                                            })
                                          )
                                        }
                                      }}
                                      onDelete={() => {
                                        setThreadMenuOpenId(null)
                                        setDeleteTarget(item)
                                      }}
                                    />
                                  </PopoverContent>
                                </Popover>
                              </div>
                            </div>
                          </li>
                          )
                        })}
                      </ul>
                    ) : null}
                  </div>
                )
              })
              )}
            </div>
          </ScrollArea>
          <div className="shrink-0 p-2">
            <SidebarUserMenu
              userName={sidebarUserName}
              onLogout={logoutSession}
              onRefreshUser={refreshCloudUserName}
              backendVersion={health?.version ?? null}
              backendUrl={backendUrl}
              connected={Boolean(health)}
            />
          </div>
            </>
          )}
        </aside>
        </ResizablePanel>

        <ResizableHandle
          className={cn(
            'w-px',
            sidebarCollapsed && 'pointer-events-none opacity-0'
          )}
        />

        <ResizablePanel
          id="main"
          order={2}
          defaultSize={82}
          minSize={40}
          className="min-w-0"
        >
        <div className="relative flex h-full min-w-0 flex-col">
          {showConnectionLimitWarning ? (
            <div className="border-border bg-amber-500/10 text-amber-950 dark:text-amber-100 flex shrink-0 items-start gap-3 border-b px-3 py-2 text-xs">
              <div className="min-w-0 flex-1">
                <p className="font-medium">
                  {runningCount} agents running at once
                </p>
                <p className="text-muted-foreground mt-0.5">
                  Browsers allow about 6 live connections to the local API. With
                  this many concurrent runs, opening files or switching chats
                  can stall. Prefer finishing some runs before starting more.
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 shrink-0 px-2 text-xs"
                onClick={() => setConnectionLimitDismissed(true)}
              >
                Dismiss
              </Button>
            </div>
          ) : null}
          {!showSessionTabs &&
          !(isHome || isProjectHome || isDashboard) ? (
            <div className="flex h-10 shrink-0 items-center gap-1 border-b px-1.5 md:px-2">
              {sidebarCollapsed ? (
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 shrink-0"
                  onClick={() => setSidebarCollapsed(false)}
                  aria-label="Show sidebar"
                >
                  <PanelLeft className="size-4" />
                </Button>
              ) : null}
              <span className="min-w-0 flex-1 truncate px-2 text-sm font-medium">
                {activeTitle}
              </span>
            </div>
          ) : null}
          {(isHome || isProjectHome || isDashboard) && sidebarCollapsed ? (
            <div className="absolute left-2 top-2 z-20">
              <Button
                variant="ghost"
                size="icon"
                className="size-8 shrink-0"
                onClick={() => setSidebarCollapsed(false)}
                aria-label="Show sidebar"
              >
                <PanelLeft className="size-4" />
              </Button>
            </div>
          ) : null}

          {isDashboardOverview ||
          isDashboardStatus ||
          isDashboardGeneral ||
          isDashboardAgentRuntime ||
          isDashboardAgentSandbox ||
          isDashboardAgentPrompts ||
          isDashboardModels ||
          isDashboardData ||
          isDashboardTools ||
          isDashboardDoctor ||
          isDashboardStorage ||
          isDashboardEnvironment ||
          isSkills ||
          isIntegrations ||
          isDashboardMcp ||
          isDashboardSpecialists ||
          isHome ||
          isProjectHome ? (
            <Suspense
              fallback={
                <DashboardPageSkeleton kind={dashboardSkeletonKind} />
              }
            >
            <AppErrorBoundary
              variant="panel"
              resetKeys={[dashboardSection, location.pathname]}
            >
            {isDashboardOverview ? (
            <DashboardOverviewView sessions={sessions}>
              <SkillsView
                featuredOnly
                mode="list"
                skills={skills}
                loading={connecting && skills.length === 0}
                detail={null}
                catalogSkillRoute={null}
                catalogSearchEnabled={catalogSearchEnabled}
                onShowAll={() => navigate('/dashboard/skills')}
                onOpen={name =>
                  navigate(`/dashboard/skills/${encodeURIComponent(name)}`)
                }
                onOpenCatalogDetail={skill =>
                  navigate(catalogSkillDetailPath(skill))
                }
                onBack={() => navigate('/dashboard/skills')}
                onOpenImportGithub={() =>
                  navigate('/dashboard/skills/import/github')
                }
                onOpenImportFile={() =>
                  navigate('/dashboard/skills/import/file')
                }
                onOpenTrustedSources={() =>
                  navigate('/dashboard/skills/trusted/sources')
                }
                onOpenCatalogSetup={() =>
                  navigate('/dashboard/integrations/vercel')
                }
                onInstall={async source => {
                  const installed = await client.installSkill(source)
                  await loadSkills()
                  return installed
                }}
                onUpload={async file => {
                  await client.installSkillFile(file)
                  await loadSkills()
                }}
                onLoadSuggestedSources={signal =>
                  client.listSkillSources(signal)
                }
                onSearchCatalog={(query, signal) =>
                  client.searchSkillCatalog(query, 12, signal)
                }
                onGetCatalogDetail={(source, skill, signal) =>
                  client.getCatalogSkillDetail(source, skill, signal)
                }
                onGetCatalogAudit={(source, skill, signal) =>
                  client.getCatalogSkillAudit(source, skill, signal)
                }
                onBulkAction={async (action, names) => {
                  const result = await client.bulkSkillAction(action, names)
                  await loadSkills()
                  return result
                }}
                onSetEnabled={async (name, enabled) => {
                  await client.setSkillEnabled(name, enabled)
                  await loadSkills()
                }}
                onRemove={async name => {
                  await client.removeSkill(name)
                  await loadSkills()
                }}
              />
              <McpView
                featuredOnly
                mcpServers={mcpServers}
                catalog={mcpCatalog}
                catalogLoading={mcpCatalogLoading}
                onShowAll={() => navigate('/dashboard/mcp')}
                onRefresh={refreshMcp}
                onConnectCatalog={async (catalogId, input) => {
                  const result = await client.connectMcpCatalog(
                    catalogId,
                    input
                  )
                  await refreshMcp()
                  await loadIntegrations()
                  return result
                }}
                onToggleCatalog={async (entry, enabled) => {
                  await client.setMcpCatalogEnabled(entry.id, enabled)
                  await refreshMcp()
                }}
                onCreateMcp={async input => {
                  await client.createMcpServer(input)
                  await loadMcpServers()
                }}
                onDeleteMcp={async id => {
                  await client.deleteMcpServer(id)
                  await loadMcpServers()
                }}
                onToggleCustom={async (id, enabled) => {
                  await client.updateMcpServer(id, { enabled })
                  await loadMcpServers()
                }}
                onOpenCatalog={entry =>
                  navigate(
                    `/dashboard/mcp/catalog/${encodeURIComponent(entry.id)}`
                  )
                }
              />
              <IntegrationsView
                featuredOnly
                terminalClient={client}
                integrations={integrations}
                loading={connecting && integrations.length === 0}
                selectedKey={null}
                values={{}}
                onShowAll={() => navigate('/dashboard/integrations')}
                onValueChange={() => {}}
                onSelect={key => {
                  if (!key) {
                    navigate('/dashboard/integrations')
                    return
                  }
                  const target = integrations.find(item => item.key === key)
                  const segment = (target?.name || key)
                    .trim()
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, '-')
                    .replace(/^-+|-+$/g, '')
                  navigate(
                    `/dashboard/integrations/${encodeURIComponent(segment || key)}`
                  )
                }}
                onSave={async () => {}}
                onValidate={async key =>
                  validateIntegrationOrProbeModal(client, key)
                }
                onAutofill={async key => {
                  await client.autofillIntegration(key)
                  await loadIntegrations()
                }}
                onSetup={async key => {
                  const result = await client.setupIntegration(key)
                  await loadIntegrations()
                  return result
                }}
                onOpenVercelTerminal={async () => {
                  const existing = sessions.find(item =>
                    String(item.workspacePath || '')
                      .trim()
                      .endsWith('/.sandwalk/vercel-integration')
                  )
                  if (existing) return existing.id
                  const created = await client.createSession({
                    title: 'Vercel integration setup',
                    workspacePath: '~/.sandwalk/vercel-integration',
                    projectId: activeProjectId || undefined
                  })
                  await loadSessions()
                  return created.id
                }}
                onRemove={async key => {
                  await client.removeIntegration(key)
                  await loadIntegrations()
                }}
              />
            </DashboardOverviewView>
          ) : isDashboardStatus ? (
            <ServerStatusView
              onLoad={loadServerStatus}
              onClearCache={signal => client.clearRuntimeCache(signal)}
            />
          ) : isDashboardGeneral ? (
            <GeneralView
              backendUrl={backendUrl}
              backendVersion={health?.version ?? null}
              connected={Boolean(health)}
              onLoadAccount={loadAccountForUi}
              onLogoutAccount={logoutAccount}
              onOpenSetupWizard={() => {
                navigate(onboardingPath('welcome'))
              }}
            />
          ) : isDashboardAgentRuntime ? (
            <AgentRuntimeView
              connected={Boolean(health)}
              runtimeSettings={runtimeSettings}
              onUpdateRuntimeSettings={async changes => {
                const next = await client.updateRuntimeSettings(changes)
                setRuntimeSettings(next)
                return next
              }}
            />
          ) : isDashboardAgentPrompts ? (
            <AgentPromptsView
              connected={Boolean(health)}
              onGetPromptBudget={(options, signal) =>
                client.getPromptBudget(options, signal)
              }
              onListSpecialists={signal => client.listSpecialists(signal)}
            />
          ) : isDashboardAgentSandbox ? (
            isSandboxLocalDetail ? (
              <EnvironmentView
                title="Local Sandbox"
                description="Python environment the agent uses for Local Sandbox chats. Manage packages used by skills and tools. Core dependencies stay locked."
                onBack={() => navigate('/dashboard/agent/sandbox')}
                onLoad={loadEnvironment}
                onInstall={(name, options) =>
                  client.installEnvironmentPackage(name, options)
                }
                onUninstall={(name, signal) =>
                  client.uninstallEnvironmentPackage(name, signal)
                }
              />
            ) : isSandboxModalDetail ? (
              <AgentSandboxView
                connected={Boolean(health)}
                sandboxSettings={sandboxSettings}
                modalIntegration={
                  integrations.find(item => item.key === 'modal') || null
                }
                onBack={() => navigate('/dashboard/agent/sandbox')}
                onLoadSandboxSettings={async () => {
                  const next = await client.getSandboxSettings()
                  setSandboxSettings(next)
                  return next
                }}
                onUpdateSandboxSettings={async changes => {
                  const next = await client.updateSandboxSettings(changes)
                  setSandboxSettings(next)
                  return next
                }}
                onProbeSandbox={() => client.probeSandboxSettings()}
                onSaveModalIntegration={async values => {
                  const next = await client.updateIntegration('modal', values)
                  await loadIntegrations()
                  const settings = await client.getSandboxSettings()
                  setSandboxSettings(settings)
                  await refreshSessionSandbox()
                  return next
                }}
                onRemoveModalIntegration={async () => {
                  await client.removeIntegration('modal')
                  await loadIntegrations()
                  const settings = await client.getSandboxSettings()
                  setSandboxSettings(settings)
                  await refreshSessionSandbox()
                }}
                onRefreshIntegrations={async () => {
                  await loadIntegrations()
                  const settings = await client.getSandboxSettings()
                  setSandboxSettings(settings)
                  await refreshSessionSandbox()
                }}
              />
            ) : (
              <SandboxListView
                onOpen={id =>
                  navigate(`/dashboard/agent/sandbox/${id}`)
                }
              />
            )
          ) : isDashboardModels ? (
            <ModelsView
              integrations={integrations}
              onListModels={options => client.listModels(options)}
              onUpdateModelEnabled={async (modelId, enabled, signal) => {
                const updated = await client.updateModelEnabled(
                  modelId,
                  enabled,
                  signal
                )
                void loadModelOptions()
                return updated
              }}
              onCreateCustomModel={async (input, signal) => {
                const created = await client.createCustomModel(input, signal)
                void loadModelOptions()
                return created
              }}
              onDeleteCustomModel={async (modelId, signal) => {
                await client.deleteCustomModel(modelId, signal)
                void loadModelOptions()
              }}
              onListProfiles={signal => client.listModelProfiles({ signal })}
              onCreateProfile={async (input, signal) => {
                const created = await client.createModelProfile(input, signal)
                void loadModelOptions()
                return created
              }}
              onUpdateProfile={async (profileId, input, signal) => {
                const updated = await client.updateModelProfile(
                  profileId,
                  input,
                  signal
                )
                void loadModelOptions()
                return updated
              }}
              onDeleteProfile={async (profileId, signal) => {
                await client.deleteModelProfile(profileId, signal)
                void loadModelOptions()
              }}
              onProbeProfile={(profileId, signal) =>
                client.probeModelProfile(profileId, signal)
              }
              onDiscoverEndpoint={(input, signal) =>
                client.discoverModelEndpoint(input, signal)
              }
              onSaveProviderKey={async (key, envVar, value) => {
                await client.updateIntegration(key, { [envVar]: value })
                await loadIntegrations()
                await loadModelOptions()
              }}
              onClearProviderKey={async key => {
                await client.removeIntegration(key)
                await loadIntegrations()
                await loadModelOptions()
              }}
            />
          ) : isDashboardTools ? (
            <ToolsView
              onListTools={signal => client.listTools({ signal })}
              onUpdateToolEnabled={(toolId, enabled, signal) =>
                client.updateToolEnabled(toolId, enabled, signal)
              }
              onBatchUpdateTools={(action, ids, signal) =>
                client.batchUpdateTools(action, ids, signal)
              }
              onListDatasets={signal => client.listDatasets(signal)}
              onOpenData={() => navigate('/dashboard/datasets')}
            />
          ) : isDashboardData ? (
            <DataView
              onListDatasets={signal => client.listDatasets(signal)}
              onInstallDataset={(datasetId, signal) =>
                client.installDataset(datasetId, signal)
              }
              onRemoveDataset={(datasetId, signal) =>
                client.removeDataset(datasetId, signal)
              }
            />
          ) : isDashboardDoctor ? (
            <DoctorView
              onRun={signal => client.runDoctor(signal)}
              onDownloadDiagnostics={(uiDiagnostics, signal) =>
                client.downloadDiagnostics(uiDiagnostics, signal)
              }
            />
          ) : isDashboardStorage ? (
            <StorageView onLoad={loadStorage} />
          ) : isDashboardEnvironment ? (
            <EnvironmentView
              onLoad={loadEnvironment}
              onInstall={(name, options) =>
                client.installEnvironmentPackage(name, options)
              }
              onUninstall={(name, signal) =>
                client.uninstallEnvironmentPackage(name, signal)
              }
            />
          ) : isSkills ? (
            <SkillsView
              mode={skillsViewMode}
              skills={skills}
              loading={connecting && skills.length === 0}
              detail={skillDetail}
              catalogSkillRoute={catalogSkillRoute}
              catalogSearchEnabled={catalogSearchEnabled}
              openCatalogSearchInitially={isCatalogSearchPath}
              onOpen={name =>
                navigate(`/dashboard/skills/${encodeURIComponent(name)}`)
              }
              onOpenCatalogDetail={skill =>
                navigate(catalogSkillDetailPath(skill))
              }
              onBack={() => navigate('/dashboard/skills')}
              onOpenImportGithub={() => navigate('/dashboard/skills/import/github')}
              onOpenImportFile={() => navigate('/dashboard/skills/import/file')}
              onOpenTrustedSources={() => navigate('/dashboard/skills/trusted/sources')}
              onOpenCatalogSetup={() => navigate('/dashboard/integrations/vercel')}
              onInstall={async source => {
                const installed = await client.installSkill(source)
                await loadSkills()
                return installed
              }}
              onUpload={async file => {
                await client.installSkillFile(file)
                await loadSkills()
              }}
              onLoadSuggestedSources={signal => client.listSkillSources(signal)}
              onSearchCatalog={(query, signal) =>
                client.searchSkillCatalog(query, 12, signal)
              }
              onGetCatalogDetail={(source, skill, signal) =>
                client.getCatalogSkillDetail(source, skill, signal)
              }
              onGetCatalogAudit={(source, skill, signal) =>
                client.getCatalogSkillAudit(source, skill, signal)
              }
              onBulkAction={async (action, names) => {
                const result = await client.bulkSkillAction(action, names)
                if (action === 'remove') {
                  setSkillDetail(current =>
                    current && result.succeeded.includes(current.name) ? null : current
                  )
                } else if (skillDetail && result.succeeded.includes(skillDetail.name)) {
                  const refreshed = await client.getSkill(skillDetail.name)
                  setSkillDetail(refreshed)
                }
                await loadSkills()
                return result
              }}
              onSetEnabled={async (name, enabled) => {
                const updated = await client.setSkillEnabled(name, enabled)
                setSkillDetail(current =>
                  current && current.name === name ? updated : current
                )
                await loadSkills()
              }}
              onRemove={async name => {
                await client.removeSkill(name)
                setSkillDetail(current =>
                  current && current.name === name ? null : current
                )
                await loadSkills()
              }}
            />
          ) : isIntegrations ? (
            <IntegrationsView
              terminalClient={client}
              integrations={integrations}
              loading={connecting && integrations.length === 0}
              selectedKey={selectedIntegrationKey}
              values={integrationValues}
              onValueChange={(envName, value) =>
                setIntegrationValues(current => ({
                  ...current,
                  [envName]: value
                }))
              }
              onSelect={key => {
                if (!key) {
                  navigate('/dashboard/integrations')
                  return
                }
                const target = integrations.find(item => item.key === key)
                const segment = (target?.name || key)
                  .trim()
                  .toLowerCase()
                  .replace(/[^a-z0-9]+/g, '-')
                  .replace(/^-+|-+$/g, '')
                navigate(
                  `/dashboard/integrations/${encodeURIComponent(segment || key)}`
                )
              }}
              onSave={async () => {
                if (!selectedIntegrationKey) return
                await client.updateIntegration(
                  selectedIntegrationKey,
                  integrationValues
                )
                setIntegrationValues({})
                await loadIntegrations()
              }}
              onValidate={async key =>
                validateIntegrationOrProbeModal(client, key)
              }
              onAutofill={async key => {
                await client.autofillIntegration(key)
                await loadIntegrations()
              }}
              onSetup={async key => {
                const result = await client.setupIntegration(key)
                await loadIntegrations()
                return result
              }}
              onOpenVercelTerminal={async () => {
                const existing = sessions.find(item =>
                  String(item.workspacePath || '')
                    .trim()
                    .endsWith('/.sandwalk/vercel-integration')
                )
                if (existing) return existing.id
                const created = await client.createSession({
                  title: 'Vercel integration setup',
                  workspacePath: '~/.sandwalk/vercel-integration',
                  projectId: activeProjectId || undefined
                })
                await loadSessions()
                return created.id
              }}
              onRemove={async key => {
                await client.removeIntegration(key)
                if (selectedIntegrationKey === key) {
                  navigate('/dashboard/integrations', { replace: true })
                }
                await loadIntegrations()
              }}
            />
          ) : isDashboardMcp ? (
            isMcpDetail ? (
              <McpDetailView
                kind={mcpCatalogDetailId ? 'catalog' : 'server'}
                catalogEntry={mcpDetailCatalogEntry}
                server={mcpDetailServer}
                onBack={() => navigate('/dashboard/mcp')}
                onLoadTools={async () => {
                  if (mcpCatalogDetailId) {
                    return client.validateMcpCatalog(mcpCatalogDetailId)
                  }
                  if (mcpServerDetailId) {
                    return client.validateMcpServer(mcpServerDetailId)
                  }
                  return {
                    ok: false,
                    toolCount: 0,
                    message: 'MCP not found',
                    tools: [],
                    toolDetails: []
                  }
                }}
                onToggleEnabled={
                  mcpCatalogDetailId && mcpDetailCatalogEntry
                    ? async enabled => {
                        await client.setMcpCatalogEnabled(
                          mcpCatalogDetailId,
                          enabled
                        )
                        await refreshMcp()
                      }
                    : mcpServerDetailId
                      ? async enabled => {
                          await client.updateMcpServer(mcpServerDetailId, {
                            enabled
                          })
                          await loadMcpServers()
                        }
                      : undefined
                }
                onConnectCatalog={
                  mcpCatalogDetailId
                    ? async input => {
                        const result = await client.connectMcpCatalog(
                          mcpCatalogDetailId,
                          input
                        )
                        await refreshMcp()
                        await loadIntegrations()
                        return result
                      }
                    : undefined
                }
                onDisconnectCatalog={
                  mcpCatalogDetailId
                    ? async () => {
                        const result =
                          await client.disconnectMcpCatalog(mcpCatalogDetailId)
                        await refreshMcp()
                        await loadIntegrations()
                        return result
                      }
                    : undefined
                }
                onRefreshMeta={async () => {
                  await refreshMcp()
                  await loadIntegrations()
                }}
              />
            ) : (
              <McpView
                mcpServers={mcpServers}
                catalog={mcpCatalog}
                catalogLoading={mcpCatalogLoading}
                onRefresh={refreshMcp}
                onConnectCatalog={async (catalogId, input) => {
                  const result = await client.connectMcpCatalog(catalogId, input)
                  await refreshMcp()
                  await loadIntegrations()
                  return result
                }}
                onToggleCatalog={async (entry, enabled) => {
                  await client.setMcpCatalogEnabled(entry.id, enabled)
                  await refreshMcp()
                }}
                onCreateMcp={async input => {
                  await client.createMcpServer(input)
                  await loadMcpServers()
                }}
                onDeleteMcp={async id => {
                  await client.deleteMcpServer(id)
                  await loadMcpServers()
                }}
                onToggleCustom={async (id, enabled) => {
                  await client.updateMcpServer(id, { enabled })
                  await loadMcpServers()
                }}
                onOpenCatalog={entry =>
                  navigate(
                    `/dashboard/mcp/catalog/${encodeURIComponent(entry.id)}`
                  )
                }
                onOpenServer={server =>
                  navigate(
                    `/dashboard/mcp/server/${encodeURIComponent(server.id)}`
                  )
                }
              />
            )
          ) : isDashboardSpecialists ? (
            <SpecialistsView
              mode={specialistsViewMode}
              specialistId={specialistsEditId}
              specialists={specialists}
              skills={skills}
              mcpServers={mcpServers}
              mcpCatalog={mcpCatalog}
              loading={specialistsLoading}
              onRefresh={loadSpecialists}
              onCreate={input => client.createSpecialist(input)}
              onUpdate={(id, input) => client.updateSpecialist(id, input)}
              onDelete={id => client.deleteSpecialist(id)}
              onOpenNew={() => navigate('/dashboard/specialists/new')}
              onOpenEdit={id =>
                navigate(`/dashboard/specialists/${encodeURIComponent(id)}`)
              }
              onBack={() => navigate('/dashboard/specialists')}
              onManageSkills={() => navigate('/dashboard/skills')}
              onManageMcps={() => navigate('/dashboard/mcp')}
              onOpenSkill={name =>
                navigate(`/dashboard/skills/${encodeURIComponent(name)}`)
              }
              onOpenMcp={({ kind, id }) => {
                const hash =
                  kind === 'catalog'
                    ? `catalog-${encodeURIComponent(id)}`
                    : `server-${encodeURIComponent(id)}`
                navigate(`/dashboard/mcp#${hash}`)
              }}
              onEnableSkill={async name => {
                await client.setSkillEnabled(name, true)
                await loadSkills()
              }}
              onInstallSkill={async source => {
                await client.installSkill(source)
                await loadSkills()
              }}
              onListTools={signal => client.listTools({ signal })}
            />
          ) : isHome || isProjectHome ? (
            <HomeView
              projects={projects}
              sessions={sessions}
              previews={sessionPreviews}
              userName={health.userName}
              activeProjectId={activeProjectId}
              onCreateProject={() => setNewProjectOpen(true)}
              onCreateSession={projectId => void createSession(projectId)}
              onOpenProject={id => {
                setProjectScopeId(id)
                navigate(`/projects/${id}`)
              }}
              onOpenSession={id => navigate(`/agents/${id}`)}
              onTogglePinProject={project => void togglePinProject(project)}
              onDeleteProject={project => void deleteProject(project)}
            />
            ) : null}
            </AppErrorBoundary>
            </Suspense>
          ) : (
            <ResizablePanelGroup
              direction="horizontal"
              autoSaveId={SESSION_PANELS_AUTO_SAVE_ID}
              className="min-h-0 flex-1"
            >
              <ResizablePanel
                id="chat"
                order={1}
                defaultSize={65}
                minSize={30}
                className="min-w-0"
              >
              <main className="relative flex h-full min-w-0 flex-col">
                <div className="flex h-10 shrink-0 items-center gap-1 px-1.5 md:px-2">
                  {sidebarCollapsed ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 shrink-0"
                      onClick={() => setSidebarCollapsed(false)}
                      aria-label="Show sidebar"
                    >
                      <PanelLeft className="size-4" />
                    </Button>
                  ) : null}
                  <SessionTabs
                    tabs={openTabs}
                    activeId={sessionId}
                    onSelect={id => {
                      openSessionTab(id)
                      void prefetchSessionMessages(id)
                      navigate(`/agents/${id}`)
                    }}
                    onClose={closeSessionTab}
                    onCloseOthers={closeOtherSessionTabs}
                    onRename={openRenameDialog}
                    onTogglePin={item =>
                      void updateSession(item, {
                        organizeLabel:
                          item.organizeLabel === 'pinned' ? null : 'pinned'
                      })
                    }
                    onExport={item => void exportTranscript(item)}
                    onInspect={item => navigate(`/agents/${item.id}?inspect=1`)}
                    onArchive={item =>
                      void updateSession(item, {
                        organizeLabel:
                          item.organizeLabel === 'archive' ? null : 'archive'
                      })
                    }
                    onDelete={item => setDeleteTarget(item)}
                  />
                  <div className="ml-auto flex shrink-0 items-center gap-0.5">
                    {session?.projectId
                      ? (() => {
                          const projectName =
                            projects.find(p => p.id === session.projectId)
                              ?.name || null
                          if (!projectName) return null
                          return (
                            <button
                              type="button"
                              className="text-muted-foreground hover:text-foreground mr-1 inline-flex max-w-[12rem] items-center gap-1.5 rounded-md px-1.5 py-1 text-xs"
                              title={projectName}
                              onClick={() =>
                                selectProjectScope(session.projectId!)
                              }
                            >
                              <Folder className="size-3.5 shrink-0" />
                              <span className="truncate">{projectName}</span>
                            </button>
                          )
                        })()
                      : null}
                    <DropdownMenu
                      open={cliMenuOpen}
                      onOpenChange={open => {
                        setCliMenuOpen(open)
                        if (!open) setCopiedResumeCommand(false)
                      }}
                    >
                      <DropdownMenuTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="size-8"
                          aria-label="Resume in Agent CLI"
                          title="Resume in Agent CLI"
                          disabled={!sessionId}
                        >
                          <Terminal className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent
                        align="end"
                        sideOffset={6}
                        className="w-[22rem] overflow-hidden rounded-xl p-0"
                        onCloseAutoFocus={event => event.preventDefault()}
                      >
                        <div className="px-4 pt-3">
                          <p className="text-foreground text-sm font-semibold">
                            Resume in Agent CLI
                          </p>
                        </div>
                        <div className="px-4 pb-3 pt-2">
                          <div className="border-border/80 bg-muted/35 flex items-center gap-2 rounded-lg border p-2.5">
                            <Terminal className="text-muted-foreground size-4 shrink-0" />
                            <code className="min-w-0 flex-1 truncate font-mono text-[13px]">
                              {sessionId
                                ? `sandwalk --resume ${sessionId}`
                                : 'sandwalk --resume <chat_id>'}
                            </code>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="size-7 shrink-0 rounded-md"
                              disabled={!sessionId}
                              onClick={event => {
                                event.preventDefault()
                                event.stopPropagation()
                                if (!sessionId) return
                                void navigator.clipboard.writeText(
                                  `sandwalk --resume ${sessionId}`
                                )
                                setCopiedResumeCommand(true)
                                window.setTimeout(
                                  () => setCopiedResumeCommand(false),
                                  2000
                                )
                              }}
                              aria-label="Copy resume command"
                              title="Copy resume command"
                            >
                              {copiedResumeCommand ? (
                                <Check className="size-3.5" />
                              ) : (
                                <Copy className="size-3.5" />
                              )}
                            </Button>
                          </div>
                          <p className="text-muted-foreground mt-2 text-xs">
                            Continue this session in your local sandwalk CLI.
                          </p>
                        </div>
                        <div className="border-border/70 border-t px-4 py-3">
                          <DropdownMenuItem
                            className="h-10 cursor-pointer gap-2 rounded-lg px-3 text-sm"
                            disabled={!session}
                            onSelect={() => {
                              if (!session) return
                              void exportTranscript(session)
                            }}
                          >
                            <Download className="size-4" />
                            Export transcript
                          </DropdownMenuItem>
                        </div>
                      </DropdownMenuContent>
                    </DropdownMenu>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      disabled={!sessionId}
                      onClick={() => {
                        if (terminalOpen) {
                          setTerminalOpen(false)
                          return
                        }
                        setFilesPanelCollapsed(false)
                        setTerminalOpen(true)
                      }}
                      aria-label={
                        terminalOpen ? 'Hide terminal' : 'Show terminal'
                      }
                      title={terminalOpen ? 'Hide terminal' : 'Show terminal'}
                    >
                      <SquareTerminal
                        className={cn(
                          'size-4',
                          terminalOpen && 'text-foreground'
                        )}
                      />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      onClick={() =>
                        setFilesPanelCollapsed(current => !current)
                      }
                      aria-label={
                        filesPanelCollapsed
                          ? 'Show files panel'
                          : 'Hide files panel'
                      }
                      title={
                        filesPanelCollapsed
                          ? 'Show files panel'
                          : 'Hide files panel'
                      }
                    >
                      <PanelRight
                        className={cn(
                          'size-4',
                          !filesPanelCollapsed && 'text-foreground'
                        )}
                      />
                    </Button>
                  </div>
                </div>
                {isInspect ? (
                  <Suspense fallback={<DetailPageSkeleton />}>
                    <InspectView
                      messages={messages}
                      tools={tools}
                      onClose={() => navigate(`/agents/${sessionId}`)}
                    />
                  </Suspense>
                ) : null}
                <div
                  className={cn(
                    'flex min-h-0 flex-1 flex-col',
                    isInspect && 'hidden'
                  )}
                >
                  {!messagesLoaded && !runActive ? (
                    showChatSkeleton ? (
                      <div className="animate-in fade-in flex min-h-0 flex-1 flex-col overflow-hidden duration-200">
                        <ChatPageSkeleton />
                      </div>
                    ) : (
                      <div className="flex min-h-0 flex-1 flex-col" />
                    )
                  ) : messages.length === 0 && !runActive ? (
                    <div className="animate-in fade-in flex min-h-0 flex-1 flex-col items-center justify-center px-5 pb-20 duration-200">
                      <AuraIconPulse className="text-muted-foreground/70 mb-6 h-12 w-12" />
                      <div className="bg-background w-full max-w-[44rem]">
                        <div className="mb-2 flex items-center px-1">
                          <ProjectPicker
                            projects={projects}
                            value={session?.projectId ?? activeProjectId}
                            recentIds={recentProjectIds}
                            noneLabel="All"
                            onNewProject={() => setNewProjectOpen(true)}
                            onChange={projectId => {
                              if (session) {
                                void updateSession(session, { projectId })
                              }
                              if (projectId) selectProjectScope(projectId)
                              else selectAllProjects()
                            }}
                          />
                        </div>
                        <QueuedMessages
                          messages={queuedMessages}
                          editingId={editingQueuedId}
                          onEdit={editQueuedMessage}
                          onSendNow={sendQueuedMessageNow}
                          onRemove={removeQueuedMessage}
                        />
                        <Composer
                          key={sessionId ?? 'empty-composer'}
                          value={composer}
                          running={runActive}
                          skills={skills}
                          mcpServers={mcpServers}
                          skillChips={composerSkills}
                          fileChips={composerFiles}
                          workspaceFiles={workspaceFiles}
                          modelOptions={modelOptions}
                          specialists={specialists}
                          selectedSpecialistId={session?.specialistId ?? null}
                          sandboxStatus={sessionSandboxStatus}
                          sandboxPhase={sessionSandboxPhase}
                          showAura={false}
                          autoFocus
                          focusKey={sessionId}
                          editingQueued={Boolean(editingQueuedId)}
                          onCancelEditQueued={cancelEditQueuedMessage}
                          onChange={setComposer}
                          onLiveDraftChange={text => {
                            composerLiveRef.current = text
                          }}
                          onSkillChipsChange={setComposerSkills}
                          onFileChipsChange={setComposerFiles}
                          onOpenFile={path => {
                            setFilesPanelCollapsed(false)
                            setPendingOpenPath(path)
                          }}
                          onSend={handleComposerSend}
                          onStop={() =>
                            sessionId && void client.interrupt(sessionId)
                          }
                          onLoadSkill={loadSkillDetail}
                          onUpload={async files => {
                            if (!sessionId) return
                            await Promise.all(
                              Array.from(files).map(file =>
                                client.uploadFile(sessionId, file)
                              )
                            )
                            setWorkspaceVersion(current => current + 1)
                          }}
                          runtimeSettings={runtimeSettings}
                          tokenUsage={tokenUsage}
                          onSpecialistSelect={selectSessionSpecialist}
                          onCreateSpecialist={() =>
                            navigate('/dashboard/specialists/new')
                          }
                          onAddModels={() => navigate('/dashboard/models')}
                          onSandboxBackendSelect={selectSessionSandboxBackend}
                          onSandboxComputeChange={changes =>
                            void updateSessionSandboxCompute(changes)
                          }
                          onSandboxStart={() => void startSessionSandbox()}
                          onSandboxStop={() => void stopSessionSandbox()}
                          onSandboxRestart={() => void restartSessionSandbox()}
                          onLoadLocalSystem={async () => {
                            const report = await client.getServerStatus()
                            return report.system
                          }}
                          onModelSelect={async (provider, model, profileId) => {
                            if (profileId) {
                              try {
                                await client.updateModelProfile(profileId, {
                                  setActive: true
                                })
                              } catch {
                                // Profile activation is best-effort for local models.
                              }
                            }
                            // Local profile models are labeled provider=local in the
                            // catalog, but the runtime still speaks OpenAI-compatible.
                            const runtimeProvider =
                              provider === 'local' || profileId ? 'openai' : provider
                            setRuntimeSettings(
                              await client.updateRuntimeSettings({
                                provider: runtimeProvider,
                                model
                              })
                            )
                          }}
                          onReasoningSettingsChange={async changes => {
                            const runtimeProvider =
                              changes.provider === 'local'
                                ? 'openai'
                                : changes.provider
                            setRuntimeSettings(
                              await client.updateRuntimeSettings({
                                provider: runtimeProvider,
                                model: changes.model,
                                reasoningEffort: changes.reasoningEffort,
                                reasoningFast: changes.reasoningFast
                              })
                            )
                            await loadModelOptions()
                          }}
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="animate-in fade-in flex min-h-0 flex-1 flex-col duration-200">
                      <div className="relative min-h-0 flex-1">
                        <ScrollArea
                          ref={chatScrollRef}
                          className="chat-scrollbar h-full min-h-0"
                        >
                          <div className="mx-auto flex w-full max-w-[44rem] flex-col px-5 py-6">
                            <div className="mb-4 flex min-w-0 flex-1 flex-col gap-y-2 empty:hidden">
                            {(() => {
                              const items: Array<
                                | {
                                    kind: 'entry'
                                    key: string
                                    entry: (typeof conversationTimeline)[number]
                                  }
                                | {
                                    kind: 'tool_run'
                                    key: string
                                    tools: TranscriptTool[]
                                  }
                              > = []
                              let cursor = 0
                              while (cursor < conversationTimeline.length) {
                                const entry = conversationTimeline[cursor]
                                if (entry.kind !== 'tool') {
                                  items.push({
                                    kind: 'entry',
                                    key: `${entry.kind}-${cursor}`,
                                    entry
                                  })
                                  cursor += 1
                                  continue
                                }
                                const runTools: TranscriptTool[] = []
                                while (
                                  cursor < conversationTimeline.length &&
                                  conversationTimeline[cursor].kind === 'tool'
                                ) {
                                  const toolEntry = conversationTimeline[cursor]
                                  if (toolEntry.kind === 'tool') {
                                    runTools.push(toolEntry.tool)
                                  }
                                  cursor += 1
                                }
                                if (runTools.length > TOOL_RUN_VISIBLE_COUNT) {
                                  items.push({
                                    kind: 'tool_run',
                                    key: `tool-run-${
                                      runTools[0]?.id || cursor
                                    }`,
                                    tools: runTools
                                  })
                                } else {
                                  runTools.forEach((tool, index) => {
                                    items.push({
                                      kind: 'entry',
                                      key: `tool-${tool.id}-${index}`,
                                      entry: { kind: 'tool', tool }
                                    })
                                  })
                                }
                              }

                              return items.map(timelineItem => {
                                if (timelineItem.kind === 'tool_run') {
                                  const isExpanded =
                                    expandedToolRunKeys[timelineItem.key] ===
                                    true
                                  const visibleTools = isExpanded
                                    ? timelineItem.tools
                                    : timelineItem.tools.slice(
                                        -TOOL_RUN_VISIBLE_COUNT
                                      )
                                  const hiddenCount = Math.max(
                                    0,
                                    timelineItem.tools.length -
                                      TOOL_RUN_VISIBLE_COUNT
                                  )
                                  return (
                                    <div
                                      key={timelineItem.key}
                                      className="space-y-1"
                                    >
                                      {hiddenCount > 0 ? (
                                        <div className="mx-auto w-full max-w-[44rem] px-2">
                                          <button
                                            type="button"
                                            className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-xs"
                                            onClick={() => {
                                              if (!sessionId) return
                                              patchChat(sessionId, prev => ({
                                                ...prev,
                                                expandedToolRunKeys: {
                                                  ...prev.expandedToolRunKeys,
                                                  [timelineItem.key]:
                                                    !isExpanded
                                                }
                                              }))
                                            }}
                                          >
                                            {isExpanded ? (
                                              <ChevronDown className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
                                            ) : (
                                              <ChevronRight className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
                                            )}
                                            <span>
                                              {isExpanded
                                                ? 'Show less'
                                                : `Show more (${hiddenCount})`}
                                            </span>
                                          </button>
                                        </div>
                                      ) : null}
                                      {visibleTools.map(tool => (
                                        <div
                                          key={tool.id}
                                          className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                                        >
                                          <ToolCard
                                            tool={tool}
                                            isRunning={runActive}
                                            onStop={
                                              sessionId
                                                ? () =>
                                                    void client.interrupt(
                                                      sessionId
                                                    )
                                                : undefined
                                            }
                                          />
                                        </div>
                                      ))}
                                    </div>
                                  )
                                }

                                const entry = timelineItem.entry
                                if (entry.kind === 'thought') {
                                  const turnTools = tools.filter(
                                    tool =>
                                      tool.messageId === entry.message.id ||
                                      (runIdByMessageId[entry.message.id] &&
                                        tool.runId ===
                                          runIdByMessageId[entry.message.id])
                                  )
                                  const duration =
                                    thoughtDurationForTools(turnTools)
                                  return (
                                    <div
                                      key={timelineItem.key}
                                      className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                                    >
                                      <ReasoningGhost
                                        id={entry.message.id}
                                        label={
                                          duration
                                            ? `Thought for ${duration}`
                                            : 'Thought'
                                        }
                                        thought={entry.thought}
                                      />
                                    </div>
                                  )
                                }

                                if (entry.kind === 'tool') {
                                  return (
                                    <div
                                      key={timelineItem.key}
                                      className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                                    >
                                      <ToolCard
                                        tool={entry.tool}
                                        isRunning={runActive}
                                        onStop={
                                          sessionId
                                            ? () =>
                                                void client.interrupt(sessionId)
                                            : undefined
                                        }
                                      />
                                    </div>
                                  )
                                }

                                if (entry.kind === 'todos') {
                                  return (
                                    <div
                                      key={timelineItem.key}
                                      className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                                    >
                                      <TodoListInline
                                        todos={entry.todos}
                                        className="mt-1"
                                      />
                                    </div>
                                  )
                                }

                                const message = entry.message
                                const isUser = message.role === 'user'
                                const isAssistant = message.role === 'assistant'
                                const messagePopoverDate =
                                  formatMessagePopoverDate(message.createdAt)
                                const messageRunId =
                                  runIdByMessageId[message.id] || null
                                const messageUsage =
                                  (messageRunId &&
                                    usageByRunId[messageRunId]) ||
                                  null
                                const hideActionsWhileStreaming =
                                  runActive &&
                                  isAssistant &&
                                  message.id === messages.at(-1)?.id

                                return (
                                  <div
                                    key={timelineItem.key}
                                    className={cn(
                                      'fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] duration-150',
                                      isUser ? 'flex justify-end px-2' : ''
                                    )}
                                  >
                                    {isUser ? (
                                      <div className="relative min-w-0 max-w-[85%]">
                                        <div className="bg-muted text-foreground peer inline-block w-auto max-w-full break-words rounded-xl px-4 py-2">
                                          <UserMessageContent
                                            content={entry.content}
                                            onOpenFile={path => {
                                              setFilesPanelCollapsed(false)
                                              setPendingOpenPath(path)
                                            }}
                                          />
                                        </div>
                                      </div>
                                    ) : (
                                      <div
                                        className={cn(
                                          'text-foreground min-w-0 break-words px-2 leading-relaxed',
                                          message.role === 'system' &&
                                            'border-border/70 text-muted-foreground rounded-xl border'
                                        )}
                                      >
                                        {entry.content.trim() ? (
                                          <MarkdownContent
                                            content={entry.content}
                                            streaming={
                                              hideActionsWhileStreaming
                                            }
                                            className="max-w-full [&_*]:max-w-full [&_pre]:w-full [&_pre]:max-w-full [&_pre_code]:whitespace-pre-wrap [&_table]:w-full [&_table]:table-auto"
                                          />
                                        ) : null}
                                        {isAssistant &&
                                        entry.content &&
                                        !hideActionsWhileStreaming ? (
                                          <div className="text-muted-foreground -mb-7.5 min-h-7.5 -ml-1 flex items-center gap-1 pt-1.5">
                                            <button
                                              type="button"
                                              className="hover:bg-muted inline-flex h-7 w-7 items-center justify-center rounded-md"
                                              onClick={async () => {
                                                await navigator.clipboard.writeText(
                                                  message.content
                                                )
                                                setCopiedMessageId(message.id)
                                                window.setTimeout(() => {
                                                  setCopiedMessageId(current =>
                                                    current === message.id
                                                      ? null
                                                      : current
                                                  )
                                                }, 1200)
                                              }}
                                              aria-label="Copy message"
                                            >
                                              {copiedMessageId ===
                                              message.id ? (
                                                <Check className="size-4" />
                                              ) : (
                                                <Copy className="size-4" />
                                              )}
                                            </button>
                                            <Popover>
                                              <PopoverTrigger asChild>
                                                <button
                                                  type="button"
                                                  className="hover:bg-muted inline-flex h-7 w-7 items-center justify-center rounded-md"
                                                  aria-label="More actions"
                                                >
                                                  <MoreHorizontal className="size-4" />
                                                </button>
                                              </PopoverTrigger>
                                              <PopoverContent
                                                align="start"
                                                className="w-48 p-1.5"
                                              >
                                                {messagePopoverDate ? (
                                                  <div className="text-muted-foreground border-border/50 mb-1 border-b px-2 pb-1.5 pt-1 text-xs">
                                                    {messagePopoverDate}
                                                  </div>
                                                ) : null}
                                                <div className="text-muted-foreground border-border/50 mb-1 border-b px-2 pb-1.5 pt-1 text-xs tabular-nums">
                                                  <div className="flex items-center justify-between gap-3">
                                                    <span>↑ Input</span>
                                                    <span className="text-foreground">
                                                      {(
                                                        messageUsage?.inputTokens ??
                                                        0
                                                      ).toLocaleString()}
                                                    </span>
                                                  </div>
                                                  <div className="mt-0.5 flex items-center justify-between gap-3">
                                                    <span>↓ Output</span>
                                                    <span className="text-foreground">
                                                      {(
                                                        messageUsage?.outputTokens ??
                                                        0
                                                      ).toLocaleString()}
                                                    </span>
                                                  </div>
                                                </div>
                                                <button
                                                  type="button"
                                                  className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                                                  onClick={() =>
                                                    downloadMarkdown(
                                                      `${
                                                        session?.title ||
                                                        'assistant-reply'
                                                      }-${message.id.slice(
                                                        0,
                                                        8
                                                      )}.md`,
                                                      message.content
                                                    )
                                                  }
                                                >
                                                  <Download className="size-4" />
                                                  Export Markdown
                                                </button>
                                              </PopoverContent>
                                            </Popover>
                                          </div>
                                        ) : null}
                                      </div>
                                    )}
                                  </div>
                                )
                              })
                            })()}
                            {activeRunTools.length > 0 ? (
                              <div className="space-y-1">
                                {activeRunTools.map(tool => (
                                  <div
                                    key={`active-${tool.id}`}
                                    className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                                  >
                                    <ToolCard
                                      tool={tool}
                                      isRunning={runActive}
                                      onStop={
                                        sessionId
                                          ? () =>
                                              void client.interrupt(sessionId)
                                          : undefined
                                      }
                                    />
                                  </div>
                                ))}
                              </div>
                            ) : null}
                            {activeRunTodos.length > 0 ? (
                              <div className="mx-auto w-full max-w-[44rem] px-2">
                                <TodoListInline todos={activeRunTodos} />
                              </div>
                            ) : null}
                            {liveDelta ? (
                              <div className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150">
                                <MarkdownContent
                                  content={liveDelta}
                                  streaming
                                  className="max-w-full [&_*]:max-w-full"
                                />
                              </div>
                            ) : null}
                            {runActive && !liveDelta ? (
                              <div className="text-muted-foreground mx-auto flex w-full max-w-[44rem] items-center gap-1 px-2 py-2 text-sm">
                                <div className="bg-foreground/80 animate-breathe h-2.5 w-2.5 rounded-full" />
                                <span className="sr-only">Generating</span>
                              </div>
                            ) : null}
                            </div>
                            <div
                              ref={chatEndRef}
                              aria-hidden
                              className="h-px w-full shrink-0"
                            />
                          </div>
                        </ScrollArea>
                        {showScrollToBottom ? (
                          <button
                            type="button"
                            onClick={() => scrollChatToBottom()}
                            aria-label="Scroll to latest message"
                            title="Scroll to latest message"
                            className="bg-background text-foreground border-border/70 absolute bottom-3 left-1/2 z-20 flex size-9 -translate-x-1/2 items-center justify-center rounded-full border shadow-[0_4px_16px_-4px_rgba(0,0,0,0.18)] transition-opacity hover:bg-background dark:shadow-[0_6px_20px_-6px_rgba(0,0,0,0.65)]"
                          >
                            <ArrowDown className="size-4" />
                          </button>
                        ) : null}
                      </div>
                      <div className="bg-background mx-auto w-full max-w-[44rem] shrink-0 px-5 pb-6 pt-2">
                        <QueuedMessages
                          messages={queuedMessages}
                          editingId={editingQueuedId}
                          onEdit={editQueuedMessage}
                          onSendNow={sendQueuedMessageNow}
                          onRemove={removeQueuedMessage}
                        />
                        <Composer
                          key={sessionId ?? 'empty-composer'}
                          value={composer}
                          running={runActive}
                          skills={skills}
                          mcpServers={mcpServers}
                          skillChips={composerSkills}
                          fileChips={composerFiles}
                          workspaceFiles={workspaceFiles}
                          modelOptions={modelOptions}
                          specialists={specialists}
                          selectedSpecialistId={session?.specialistId ?? null}
                          sandboxStatus={sessionSandboxStatus}
                          sandboxPhase={sessionSandboxPhase}
                          showAura={false}
                          autoFocus
                          focusKey={sessionId}
                          editingQueued={Boolean(editingQueuedId)}
                          onCancelEditQueued={cancelEditQueuedMessage}
                          onChange={setComposer}
                          onLiveDraftChange={text => {
                            composerLiveRef.current = text
                          }}
                          onSkillChipsChange={setComposerSkills}
                          onFileChipsChange={setComposerFiles}
                          onOpenFile={path => {
                            setFilesPanelCollapsed(false)
                            setPendingOpenPath(path)
                          }}
                          onSend={handleComposerSend}
                          onStop={() =>
                            sessionId && void client.interrupt(sessionId)
                          }
                          onLoadSkill={loadSkillDetail}
                          onUpload={async files => {
                            if (!sessionId) return
                            await Promise.all(
                              Array.from(files).map(file =>
                                client.uploadFile(sessionId, file)
                              )
                            )
                            setWorkspaceVersion(current => current + 1)
                          }}
                          runtimeSettings={runtimeSettings}
                          tokenUsage={tokenUsage}
                          onSpecialistSelect={selectSessionSpecialist}
                          onCreateSpecialist={() =>
                            navigate('/dashboard/specialists/new')
                          }
                          onAddModels={() => navigate('/dashboard/models')}
                          onSandboxBackendSelect={selectSessionSandboxBackend}
                          onSandboxComputeChange={changes =>
                            void updateSessionSandboxCompute(changes)
                          }
                          onSandboxStart={() => void startSessionSandbox()}
                          onSandboxStop={() => void stopSessionSandbox()}
                          onSandboxRestart={() => void restartSessionSandbox()}
                          onLoadLocalSystem={async () => {
                            const report = await client.getServerStatus()
                            return report.system
                          }}
                          onModelSelect={async (provider, model, profileId) => {
                            if (profileId) {
                              try {
                                await client.updateModelProfile(profileId, {
                                  setActive: true
                                })
                              } catch {
                                // Profile activation is best-effort for local models.
                              }
                            }
                            const runtimeProvider =
                              provider === 'local' || profileId ? 'openai' : provider
                            setRuntimeSettings(
                              await client.updateRuntimeSettings({
                                provider: runtimeProvider,
                                model
                              })
                            )
                          }}
                          onReasoningSettingsChange={async changes => {
                            const runtimeProvider =
                              changes.provider === 'local'
                                ? 'openai'
                                : changes.provider
                            setRuntimeSettings(
                              await client.updateRuntimeSettings({
                                provider: runtimeProvider,
                                model: changes.model,
                                reasoningEffort: changes.reasoningEffort,
                                reasoningFast: changes.reasoningFast
                              })
                            )
                            await loadModelOptions()
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>
                {error ? (
                  <div className="bg-destructive text-destructive-foreground absolute bottom-2 left-1/2 -translate-x-1/2 rounded-md px-3 py-1.5 text-xs">
                    {error}
                  </div>
                ) : null}
              </main>
              </ResizablePanel>
              {canShowFilesPanel ? (
                <>
                  <ResizableHandle
                    className={cn(
                      'w-px',
                      filesPanelCollapsed && 'pointer-events-none opacity-0'
                    )}
                  />
                  <ResizablePanel
                    id="files"
                    order={2}
                    ref={filesPanelRef}
                    collapsible
                    collapsedSize={0}
                    defaultSize={35}
                    minSize={20}
                    maxSize={55}
                    onCollapse={() => setFilesPanelCollapsed(true)}
                    onExpand={() => setFilesPanelCollapsed(false)}
                    className="min-w-0"
                  >
                    {sessionId ? (
                      <WorkspacePanel
                        key={sessionId}
                        client={client}
                        sessionId={sessionId}
                        workspaceVersion={workspaceVersion}
                        openPathRequest={pendingOpenPath}
                        onOpenPathRequestHandled={() => setPendingOpenPath(null)}
                        onAddToChat={path => {
                          setComposer(current => `${current}${fileChipToken(path)}`)
                          setComposerFiles([])
                        }}
                        onTogglePanel={() => setFilesPanelCollapsed(true)}
                        terminalOpen={terminalOpen}
                        onCloseTerminal={() => setTerminalOpen(false)}
                        onOpenTerminal={() => setTerminalOpen(true)}
                      />
                    ) : null}
                  </ResizablePanel>
                </>
              ) : null}
            </ResizablePanelGroup>
          )}
        </div>
        </ResizablePanel>
      </ResizablePanelGroup>

      <GlobalSearchDialog
        open={globalSearchOpen}
        onOpenChange={setGlobalSearchOpen}
        client={client}
        sessions={sessions}
        currentSessionId={sessionId}
        currentSessionTitle={session?.title || activeProject?.name}
        workspaceFiles={workspaceFiles}
        onOpenSession={id => {
          openSessionTab(id)
          navigate(`/agents/${id}`)
        }}
        onOpenArtifact={(targetSessionId, path) => {
          openSessionTab(targetSessionId)
          setFilesPanelCollapsed(false)
          setPendingOpenPath(path)
          navigate(`/agents/${targetSessionId}`)
        }}
        onMentionArtifact={(targetSessionId, path) => {
          pendingMentionRef.current = path
          openSessionTab(targetSessionId)
          if (targetSessionId === sessionId) {
            setComposer(current => `${current}${fileChipToken(path)}`)
            setComposerFiles([])
            pendingMentionRef.current = null
          } else {
            navigate(`/agents/${targetSessionId}`)
          }
        }}
        onCreateSession={() => void createSession(activeProjectId)}
        onNavigate={path => navigate(path)}
      />

      <NewProjectDialog
        open={newProjectOpen}
        onOpenChange={setNewProjectOpen}
        onCreate={createProject}
      />

      <ProjectSettingsDialog
        project={activeProject}
        open={projectSettingsOpen}
        onOpenChange={setProjectSettingsOpen}
        onSave={saveProjectSettings}
      />

      <Dialog
        open={Boolean(renameTarget)}
        onOpenChange={open => {
          if (!open) {
            setRenameTarget(null)
            setRenameValue('')
          }
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Rename chat</DialogTitle>
            <DialogDescription>
              Choose a clearer name for this agent session.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={event => setRenameValue(event.target.value)}
            placeholder="Chat name"
            autoFocus
            maxLength={140}
            onKeyDown={event => {
              if (event.key === 'Enter') {
                event.preventDefault()
                void submitRename()
              }
            }}
          />
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setRenameTarget(null)
                setRenameValue('')
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => void submitRename()}
              disabled={!renameValue.trim()}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(deleteTarget)}
        onOpenChange={open => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent className="max-w-sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete chat?</AlertDialogTitle>
            <AlertDialogDescription>
              Delete “{deleteTarget?.title || 'Untitled session'}”? This cannot
              be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => void confirmDelete()}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={batchDeletePending}
        onOpenChange={open => {
          if (!open && !batchBusy) setBatchDeletePending(false)
        }}
      >
        <AlertDialogContent className="max-w-sm">
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selectedSessionIds.size} chats?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes the selected sessions and cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={batchBusy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={batchBusy}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={event => {
                event.preventDefault()
                void confirmBatchDelete()
              }}
            >
              {batchBusy ? 'Deleting…' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
