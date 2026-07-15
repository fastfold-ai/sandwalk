import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
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
  Specialist,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import { Loader2, PanelLeft } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import { matchPath, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { AgentSessionMainPanel } from '@/components/agents/AgentSessionMainPanel'
import { AgentSessionSidebar } from '@/components/agents/AgentSessionSidebar'
import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { fileChipToken } from '@/components/agents/composer-parts'
import { DashboardMainViews } from '@/components/agents/DashboardMainViews'
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
import { NewProjectDialog } from '@/components/agents/NewProjectDialog'
import { type DashboardSkeletonKind } from '@/components/agents/PageSkeletons'
import { ProjectSettingsDialog } from '@/components/agents/ProjectSettingsDialog'
import {
  buildConversationTimeline
} from '@/components/agents/transcript'
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
import { Input } from '@/components/ui/input'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import {
  FILES_PANEL_COLLAPSED_STORAGE_KEY,
  projectTabsKey,
  readCollapsedSidebarSections,
  readLastSessionByScope,
  readOpenTabsByProject,
  readProjectScopeId,
  readRecentProjectIds,
  SHELL_PANELS_AUTO_SAVE_ID,
  SIDEBAR_COLLAPSED_STORAGE_KEY,
  TERMINAL_OPEN_STORAGE_KEY,
  writeCollapsedSidebarSections,
  writeLastSessionByScope,
  writeOpenTabsByProject,
  writeProjectScopeId
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
import { useChatScroll } from '@/hooks/useChatScroll'
import { useSessionActions } from '@/hooks/useSessionActions'
import { useSessionChatState } from '@/hooks/useSessionChatState'
import { useSessionChatSend } from '@/hooks/useSessionChatSend'
import { useSessionChatStream } from '@/hooks/useSessionChatStream'
import { useSessionSandbox } from '@/hooks/useSessionSandbox'
import {
  AUTO_TITLE_FIRST_RESPONSE_THRESHOLD,
  groupSessions,
  isLowSignalTitle,
  visibleSessionIds
} from '@/lib/sessions'
import {
  cloudAccountDisplayName,
  parseCatalogSkillId,
  type SkillsViewMode
} from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8787'
/** Soft warn: live SSE streams start crowding the browser's ~6 conn/host limit. */
const CONCURRENT_RUN_SOFT_LIMIT = 3

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
  const [modelOptions, setModelOptions] = useState<ComposerModelOption[]>([])
  const [globalSearchOpen, setGlobalSearchOpen] = useState(false)
  const [pendingOpenPath, setPendingOpenPath] = useState<string | null>(null)
  const pendingMentionRef = useRef<string | null>(null)
  const sidebarPanelRef = useRef<ImperativePanelHandle>(null)
  const filesPanelRef = useRef<ImperativePanelHandle>(null)
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
  const [openTabsByProject, setOpenTabsByProject] = useState<
    Record<string, string[]>
  >(() => readOpenTabsByProject())
  const [workspaceVersion, setWorkspaceVersion] = useState(0)
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([])
  const [integrationValues, setIntegrationValues] = useState<
    Record<string, string>
  >({})
  const onboardingAutoOpenedRef = useRef(false)
  const sessionIdRef = useRef<string | null>(null)
  const loadSessionsRef = useRef<(() => Promise<void>) | null>(null)
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

  const {
    chatBySessionId,
    setChatBySessionId,
    chatBySessionIdRef,
    patchChat,
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
    messagesLoaded,
    setComposer,
    setComposerSkills,
    setComposerFiles,
    composerLiveRef,
    editingQueuedId,
    setEditingQueuedId,
    pendingImmediateSendRef,
    drainingQueueRef
  } = useSessionChatState(sessionId)

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

  useSessionChatStream({
    client,
    health,
    sessionId,
    sessionIdRef,
    sessions,
    runningSessionIdsKey,
    chatBySessionIdRef,
    patchChat,
    setSessions,
    setWorkspaceVersion,
    setError,
    loadSessionsRef
  })

  const {
    handleComposerSend,
    editQueuedMessage,
    cancelEditQueuedMessage,
    removeQueuedMessage,
    sendQueuedMessageNow
  } = useSessionChatSend({
    client,
    sessionId,
    sessions,
    runActive,
    composer,
    composerSkills,
    composerFiles,
    composerLiveRef,
    queuedMessages,
    editingQueuedId,
    setEditingQueuedId,
    pendingImmediateSendRef,
    drainingQueueRef,
    chatBySessionIdRef,
    patchChat,
    setSessions,
    setError,
    setConnectionLimitDismissed
  })

  sessionIdRef.current = sessionId

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

  const {
    sessionSandboxStatus,
    sessionSandboxPhase,
    refreshSessionSandbox,
    selectSessionSandboxBackend,
    startSessionSandbox,
    stopSessionSandbox,
    restartSessionSandbox,
    updateSessionSandboxCompute
  } = useSessionSandbox({
    client,
    health,
    sessionId,
    sessionIdRef,
    session,
    loadSessions,
    loadProjects,
    setSandboxSettings,
    setError
  })

  const {
    renameTarget,
    renameValue,
    setRenameTarget,
    setRenameValue,
    deleteTarget,
    setDeleteTarget,
    selectedSessionIds,
    setSelectionAnchorId,
    batchBusy,
    batchDeletePending,
    setBatchDeletePending,
    createSession,
    closeSessionTab,
    closeOtherSessionTabs,
    updateSession,
    selectSessionSpecialist,
    createProject,
    saveProjectSettings,
    selectAllProjects,
    selectProjectScope,
    togglePinProject,
    deleteProject,
    openRenameDialog,
    submitRename,
    confirmDelete,
    exportTranscript,
    clearSessionSelection,
    selectSessionRange,
    toggleSessionSelected,
    batchArchiveSelected,
    batchMoveSelected,
    batchExportSelected,
    confirmBatchDelete
  } = useSessionActions({
    client,
    navigate,
    activeProjectId,
    tabsScopeKey,
    sessionId,
    session,
    sessions,
    setSessions,
    activeProject,
    openTabsByProject,
    setOpenTabsByProject,
    lastSessionByScope,
    setLastSessionByScope,
    setProjectScopeId,
    setRecentProjectIds,
    patchOpenTabs,
    setOpenTabIds,
    patchChat,
    setChatBySessionId,
    loadSessions,
    loadProjects,
    setError,
    setCollapsedSidebarSections
  })

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

  const loadSkillDetail = useCallback(
    (name: string) => client.getSkill(name),
    [client]
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

  const {
    chatScrollRef,
    chatEndRef,
    showScrollToBottom,
    scrollChatToBottom
  } = useChatScroll({
    sessionId,
    messagesLoaded,
    messagesLength: messages.length,
    conversationTimelineLength: conversationTimeline.length
  })

  const agentComposerSlotProps = {
    sessionId,
    session,
    client,
    navigate,
    composerLiveRef,
    queuedMessages,
    editingQueuedId,
    editQueuedMessage,
    sendQueuedMessageNow,
    removeQueuedMessage,
    cancelEditQueuedMessage,
    composer,
    runActive,
    skills,
    mcpServers,
    composerSkills,
    composerFiles,
    workspaceFiles,
    modelOptions,
    specialists,
    sessionSandboxStatus,
    sessionSandboxPhase,
    setComposer,
    setComposerSkills,
    setComposerFiles,
    setFilesPanelCollapsed,
    setPendingOpenPath,
    handleComposerSend,
    loadSkillDetail,
    setWorkspaceVersion,
    runtimeSettings,
    tokenUsage,
    selectSessionSpecialist,
    selectSessionSandboxBackend,
    updateSessionSandboxCompute,
    startSessionSandbox,
    stopSessionSandbox,
    restartSessionSandbox,
    setRuntimeSettings,
    loadModelOptions
  }

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
            <AgentSessionSidebar
              projects={projects}
              activeProjectId={activeProjectId}
              sections={sections}
              collapsedSidebarSections={collapsedSidebarSections}
              sessionId={sessionId}
              chatBySessionId={chatBySessionId}
              orderedVisibleSessionIds={orderedVisibleSessionIds}
              selectedSessionIds={selectedSessionIds}
              threadMenuOpenId={threadMenuOpenId}
              batchBusy={batchBusy}
              canShowFilesPanel={canShowFilesPanel}
              filesPanelCollapsed={filesPanelCollapsed}
              sidebarUserName={sidebarUserName}
              health={health}
              backendUrl={backendUrl}
              navigate={navigate}
              onNavigateHome={() => {
                setProjectScopeId(null)
                navigate('/')
              }}
              onSelectAllProjects={selectAllProjects}
              onSelectProject={selectProjectScope}
              onOpenProjectSettings={() => setProjectSettingsOpen(true)}
              onNewProject={() => setNewProjectOpen(true)}
              onOpenGlobalSearch={() => setGlobalSearchOpen(true)}
              onCollapseSidebar={() => setSidebarCollapsed(true)}
              onCreateSession={() => createSession(activeProjectId)}
              onToggleFilesPanel={() =>
                setFilesPanelCollapsed(current => !current)
              }
              onClearSessionSelection={clearSessionSelection}
              onBatchArchiveSelected={batchArchiveSelected}
              onBatchMoveSelected={batchMoveSelected}
              onBatchExportSelected={batchExportSelected}
              onBatchDeletePending={() => setBatchDeletePending(true)}
              setCollapsedSidebarSections={setCollapsedSidebarSections}
              selectSessionRange={selectSessionRange}
              toggleSessionSelected={toggleSessionSelected}
              setSelectionAnchorId={setSelectionAnchorId}
              openSessionTab={openSessionTab}
              prefetchSessionMessages={prefetchSessionMessages}
              setThreadMenuOpenId={setThreadMenuOpenId}
              openRenameDialog={openRenameDialog}
              updateSession={updateSession}
              exportTranscript={exportTranscript}
              setDeleteTarget={setDeleteTarget}
              onLogout={logoutSession}
              onRefreshUser={refreshCloudUserName}
            />
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
            <DashboardMainViews
              client={client}
              navigate={navigate}
              location={location}
              dashboardSection={dashboardSection}
              dashboardSkeletonKind={dashboardSkeletonKind}
              backendUrl={backendUrl}
              health={health}
              connecting={connecting}
              sessions={sessions}
              projects={projects}
              sessionPreviews={sessionPreviews}
              activeProjectId={activeProjectId}
              skills={skills}
              skillDetail={skillDetail}
              catalogSkillRoute={catalogSkillRoute}
              catalogSearchEnabled={catalogSearchEnabled}
              isCatalogSearchPath={isCatalogSearchPath}
              skillsViewMode={skillsViewMode}
              integrations={integrations}
              integrationValues={integrationValues}
              selectedIntegrationKey={selectedIntegrationKey}
              mcpServers={mcpServers}
              mcpCatalog={mcpCatalog}
              mcpCatalogLoading={mcpCatalogLoading}
              mcpCatalogDetailId={mcpCatalogDetailId}
              mcpServerDetailId={mcpServerDetailId}
              mcpDetailCatalogEntry={mcpDetailCatalogEntry}
              mcpDetailServer={mcpDetailServer}
              isMcpDetail={isMcpDetail}
              specialists={specialists}
              specialistsLoading={specialistsLoading}
              specialistsViewMode={specialistsViewMode}
              specialistsEditId={specialistsEditId}
              runtimeSettings={runtimeSettings}
              sandboxSettings={sandboxSettings}
              isDashboardOverview={isDashboardOverview}
              isDashboardStatus={isDashboardStatus}
              isDashboardGeneral={isDashboardGeneral}
              isDashboardAgentRuntime={isDashboardAgentRuntime}
              isDashboardAgentPrompts={isDashboardAgentPrompts}
              isDashboardAgentSandbox={isDashboardAgentSandbox}
              isDashboardModels={isDashboardModels}
              isDashboardData={isDashboardData}
              isDashboardTools={isDashboardTools}
              isDashboardDoctor={isDashboardDoctor}
              isDashboardStorage={isDashboardStorage}
              isDashboardEnvironment={isDashboardEnvironment}
              isSkills={isSkills}
              isIntegrations={isIntegrations}
              isDashboardMcp={isDashboardMcp}
              isDashboardSpecialists={isDashboardSpecialists}
              isHome={isHome}
              isProjectHome={isProjectHome}
              isSandboxLocalDetail={isSandboxLocalDetail}
              isSandboxModalDetail={isSandboxModalDetail}
              setSkillDetail={setSkillDetail}
              setIntegrationValues={setIntegrationValues}
              setRuntimeSettings={setRuntimeSettings}
              setSandboxSettings={setSandboxSettings}
              loadSkills={loadSkills}
              loadIntegrations={loadIntegrations}
              loadMcpServers={loadMcpServers}
              refreshMcp={refreshMcp}
              loadSpecialists={loadSpecialists}
              loadModelOptions={loadModelOptions}
              loadSessions={loadSessions}
              loadServerStatus={loadServerStatus}
              loadAccountForUi={loadAccountForUi}
              logoutAccount={logoutAccount}
              loadStorage={loadStorage}
              loadEnvironment={loadEnvironment}
              refreshSessionSandbox={refreshSessionSandbox}
              onCreateProject={() => setNewProjectOpen(true)}
              createSession={createSession}
              onOpenProject={id => {
                setProjectScopeId(id)
                navigate(`/projects/${id}`)
              }}
              togglePinProject={togglePinProject}
              deleteProject={deleteProject}
            />
          ) : (
            <AgentSessionMainPanel
              client={client}
              navigate={navigate}
              sidebarCollapsed={sidebarCollapsed}
              setSidebarCollapsed={setSidebarCollapsed}
              openTabs={openTabs}
              sessionId={sessionId}
              session={session}
              openSessionTab={openSessionTab}
              prefetchSessionMessages={prefetchSessionMessages}
              closeSessionTab={closeSessionTab}
              closeOtherSessionTabs={closeOtherSessionTabs}
              openRenameDialog={openRenameDialog}
              updateSession={updateSession}
              exportTranscript={exportTranscript}
              setDeleteTarget={setDeleteTarget}
              projects={projects}
              selectProjectScope={selectProjectScope}
              cliMenuOpen={cliMenuOpen}
              setCliMenuOpen={setCliMenuOpen}
              copiedResumeCommand={copiedResumeCommand}
              setCopiedResumeCommand={setCopiedResumeCommand}
              terminalOpen={terminalOpen}
              setTerminalOpen={setTerminalOpen}
              filesPanelCollapsed={filesPanelCollapsed}
              setFilesPanelCollapsed={setFilesPanelCollapsed}
              isInspect={isInspect}
              messages={messages}
              tools={tools}
              messagesLoaded={messagesLoaded}
              runActive={runActive}
              showChatSkeleton={showChatSkeleton}
              agentComposerSlotProps={agentComposerSlotProps}
              recentProjectIds={recentProjectIds}
              activeProjectId={activeProjectId}
              onNewProject={() => setNewProjectOpen(true)}
              selectAllProjects={selectAllProjects}
              chatScrollRef={chatScrollRef}
              chatEndRef={chatEndRef}
              conversationTimeline={conversationTimeline}
              expandedToolRunKeys={expandedToolRunKeys}
              patchChat={patchChat}
              runIdByMessageId={runIdByMessageId}
              usageByRunId={usageByRunId}
              copiedMessageId={copiedMessageId}
              setCopiedMessageId={setCopiedMessageId}
              activeRunTools={activeRunTools}
              activeRunTodos={activeRunTodos}
              liveDelta={liveDelta}
              showScrollToBottom={showScrollToBottom}
              scrollChatToBottom={scrollChatToBottom}
              error={error}
              canShowFilesPanel={canShowFilesPanel}
              filesPanelRef={filesPanelRef}
              workspaceVersion={workspaceVersion}
              pendingOpenPath={pendingOpenPath}
              setPendingOpenPath={setPendingOpenPath}
              setComposer={setComposer}
              setComposerFiles={setComposerFiles}
            />
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
