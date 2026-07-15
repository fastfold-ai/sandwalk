import { PanelLeft } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type SetStateAction } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import { matchPath, useLocation, useNavigate } from 'react-router-dom'

import { AgentSessionMainPanel } from '@/components/agents/AgentSessionMainPanel'
import { AgentSessionSidebar } from '@/components/agents/AgentSessionSidebar'
import { fileChipToken } from '@/components/agents/composer-parts'
import { DashboardMainViews } from '@/components/agents/DashboardMainViews'
import {
  type DashboardSection,
  DashboardSidebar
} from '@/components/agents/DashboardSidebar'
import {
  isOnboardingPath,
  onboardingStepFromSlug
} from '@/lib/onboarding'
import { type DashboardSkeletonKind } from '@/components/agents/PageSkeletons'
import {
  buildConversationTimeline
} from '@/components/agents/transcript'
import { AppDialogs } from '@/components/AppDialogs'
import { AppGates } from '@/components/AppGates'
import { Button } from '@/components/ui/button'
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
  writeLastSessionByScope,
  writeOpenTabsByProject,
  writeProjectScopeId
} from '@/lib/app-storage'
import { useAppBootstrap } from '@/hooks/useAppBootstrap'
import { useAppShellEffects } from '@/hooks/useAppShellEffects'
import { useChatScroll } from '@/hooks/useChatScroll'
import { useSessionActions } from '@/hooks/useSessionActions'
import { useSessionChatState } from '@/hooks/useSessionChatState'
import { useSessionChatSend } from '@/hooks/useSessionChatSend'
import { useSessionChatStream } from '@/hooks/useSessionChatStream'
import { useSessionSandbox } from '@/hooks/useSessionSandbox'
import {
  groupSessions,
  type SessionChatState,
  visibleSessionIds
} from '@/lib/sessions'
import {
  parseCatalogSkillId,
  type SkillsViewMode
} from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'
import type {
  AgentSession,
  AgentSkillDetail,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'

const CONCURRENT_RUN_SOFT_LIMIT = 3

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const [connectionLimitDismissed, setConnectionLimitDismissed] =
    useState(false)
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
  const [skillDetail, setSkillDetail] = useState<AgentSkillDetail | null>(null)
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
  const sessionIdRef = useRef<string | null>(null)

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
  const setChatBySessionIdRef = useRef(
    (_value: SetStateAction<Record<string, SessionChatState>>) => {}
  )
  const setChatBySessionIdBridge = useCallback(
    (value: SetStateAction<Record<string, SessionChatState>>) => {
      setChatBySessionIdRef.current(value)
    },
    []
  )
  const {
    backendUrl,
    setBackendUrl,
    backendApiKey,
    setBackendApiKey,
    client,
    health,
    sidebarUserName,
    needsAuthLogin,
    authBootstrapped,
    authLoggingIn,
    authLoginError,
    setAuthLoginError,
    connecting,
    error,
    errorStack,
    setError,
    sessions,
    setSessions,
    projects,
    sessionPreviews,
    skills,
    integrations,
    mcpServers,
    mcpCatalog,
    mcpCatalogLoading,
    specialists,
    specialistsLoading,
    runtimeSettings,
    setRuntimeSettings,
    sandboxSettings,
    setSandboxSettings,
    modelOptions,
    loadSessionsRef,
    loadSessions,
    loadProjects,
    loadSkills,
    loadIntegrations,
    loadMcpServers,
    loadMcpCatalog,
    refreshMcp,
    loadSpecialists,
    loadModelOptions,
    loadAccountForUi,
    logoutAccount,
    refreshCloudUserName,
    loadStorage,
    loadEnvironment,
    loadServerStatus,
    connect,
    submitAuthLogin,
    logoutSession
  } = useAppBootstrap({
    navigate,
    location,
    setChatBySessionId: setChatBySessionIdBridge,
    isDashboardModels
  })
  const catalogSearchEnabled = useMemo(
    () => integrations.find(item => item.key === 'skills-sh')?.configured ?? false,
    [integrations]
  )
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
  const activeProject =
    projects.find(project => project.id === activeProjectId) || null
  const activeIntegration =
    integrations.find(item => item.key === selectedIntegrationKey) || null
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
  setChatBySessionIdRef.current = setChatBySessionId

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

  const { showChatSkeleton } = useAppShellEffects({
    locationPathname: location.pathname,
    navigate,
    legacySkillRouteName: legacySkillRoute?.params.skillName,
    legacyIntegrationRouteKey: legacyIntegrationRoute?.params.integrationKey,
    onOnboardingPath,
    onboardingStep,
    sessionTitle: session?.title,
    activeIntegration,
    activeProject,
    isDashboardOverview,
    isDashboardStatus,
    isDashboardGeneral,
    isDashboardModels,
    isDashboardTools,
    isDashboardDoctor,
    isDashboardStorage,
    isDashboardEnvironment,
    isSkills,
    isDashboardSpecialists,
    isIntegrations,
    isDashboardData,
    isDashboardAgentSandbox,
    isSandboxLocalDetail,
    isSandboxModalDetail,
    isDashboardAgentPrompts,
    isDashboardAgentRuntime,
    isDashboardMcp,
    sidebarCollapsed,
    filesPanelCollapsed,
    terminalOpen,
    sidebarPanelRef,
    filesPanelRef,
    collapsedSidebarSections,
    runningCount,
    concurrentRunSoftLimit: CONCURRENT_RUN_SOFT_LIMIT,
    setConnectionLimitDismissed,
    routeProjectId,
    setProjectScopeId,
    messagesLoaded,
    runActive,
    sessionId,
    client,
    messages,
    setSessions
  })

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

  const gate = AppGates({
    authBootstrapped,
    needsAuthLogin,
    authLoggingIn,
    connecting,
    authLoginError,
    setAuthLoginError,
    connect,
    submitAuthLogin,
    health,
    backendUrl,
    setBackendUrl,
    backendApiKey,
    setBackendApiKey,
    error,
    errorStack,
    onOnboardingPath,
    onboardingStep,
    client,
    navigate,
    loadModelOptions,
    loadIntegrations,
    loadSkills,
    loadMcpServers,
    loadMcpCatalog
  })
  if (gate) return gate

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

      <AppDialogs
        client={client}
        navigate={navigate}
        globalSearchOpen={globalSearchOpen}
        setGlobalSearchOpen={setGlobalSearchOpen}
        sessions={sessions}
        sessionId={sessionId}
        sessionTitle={session?.title}
        activeProject={activeProject}
        activeProjectId={activeProjectId}
        workspaceFiles={workspaceFiles}
        openSessionTab={openSessionTab}
        setFilesPanelCollapsed={setFilesPanelCollapsed}
        setPendingOpenPath={setPendingOpenPath}
        pendingMentionRef={pendingMentionRef}
        setComposer={setComposer}
        setComposerFiles={setComposerFiles}
        createSession={createSession}
        newProjectOpen={newProjectOpen}
        setNewProjectOpen={setNewProjectOpen}
        createProject={createProject}
        projectSettingsOpen={projectSettingsOpen}
        setProjectSettingsOpen={setProjectSettingsOpen}
        saveProjectSettings={saveProjectSettings}
        renameTarget={renameTarget}
        renameValue={renameValue}
        setRenameTarget={setRenameTarget}
        setRenameValue={setRenameValue}
        submitRename={submitRename}
        deleteTarget={deleteTarget}
        setDeleteTarget={setDeleteTarget}
        confirmDelete={confirmDelete}
        batchDeletePending={batchDeletePending}
        setBatchDeletePending={setBatchDeletePending}
        batchBusy={batchBusy}
        selectedSessionIds={selectedSessionIds}
        confirmBatchDelete={confirmBatchDelete}
      />
    </>
  )
}
