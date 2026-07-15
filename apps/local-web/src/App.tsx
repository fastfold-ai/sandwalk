import { useCallback, useMemo, useRef, useState, type SetStateAction } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import { useLocation, useNavigate } from 'react-router-dom'

import {
  buildConversationTimeline
} from '@/components/agents/transcript'
import { AppGates } from '@/components/AppGates'
import { AppShell } from '@/components/AppShell'
import {
  FILES_PANEL_COLLAPSED_STORAGE_KEY,
  projectTabsKey,
  readCollapsedSidebarSections,
  readLastSessionByScope,
  readOpenTabsByProject,
  readProjectScopeId,
  readRecentProjectIds,
  SIDEBAR_COLLAPSED_STORAGE_KEY,
  TERMINAL_OPEN_STORAGE_KEY,
  writeOpenTabsByProject
} from '@/lib/app-storage'
import { useAppBootstrap } from '@/hooks/useAppBootstrap'
import { useAppRouting } from '@/hooks/useAppRouting'
import { useAppSessionEffects } from '@/hooks/useAppSessionEffects'
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

  const {
    legacySkillRoute,
    legacyIntegrationRoute,
    onOnboardingPath,
    onboardingStep,
    skillRouteName,
    catalogSkillRoute,
    decodedIntegrationRouteName,
    normalizedIntegrationRouteName,
    routeProjectId,
    specialistsViewMode,
    specialistsEditId,
    isDashboard,
    dashboardSection,
    isSkills,
    skillsViewMode,
    isIntegrations,
    isDashboardStatus,
    isDashboardGeneral,
    isDashboardAgentRuntime,
    isDashboardAgentSandbox,
    isDashboardAgentPrompts,
    isDashboardModels,
    isDashboardData,
    isDashboardTools,
    isDashboardDoctor,
    isDashboardStorage,
    isDashboardEnvironment,
    isDashboardMcp,
    mcpCatalogDetailId,
    mcpServerDetailId,
    isMcpDetail,
    isSandboxLocalDetail,
    isSandboxModalDetail,
    isDashboardSpecialists,
    isDashboardOverview,
    isHome,
    isProjectHome,
    isInspect,
    dashboardSkeletonKind,
    sessionId,
    isCatalogSearchPath
  } = useAppRouting(location)

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
  const activeProjectId = projectScopeId
  const tabsScopeKey = projectTabsKey(activeProjectId)
  const openTabIds = openTabsByProject[tabsScopeKey] || []
  const activeProject =
    projects.find(project => project.id === activeProjectId) || null
  const activeIntegration =
    integrations.find(item => item.key === selectedIntegrationKey) || null
  const mcpDetailCatalogEntry = mcpCatalogDetailId
    ? mcpCatalog.find(entry => entry.id === mcpCatalogDetailId) || null
    : null
  const mcpDetailServer = mcpServerDetailId
    ? mcpServers.find(server => server.id === mcpServerDetailId) || null
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

  useAppSessionEffects({
    setIntegrationValues,
    selectedIntegrationKey,
    isIntegrations,
    integrations,
    navigate,
    sessionId,
    sessions,
    activeProjectId,
    openSessionTab,
    setOpenTabsByProject,
    setLastSessionByScope,
    tabsScopeKey,
    projectScopeId,
    client,
    workspaceVersion,
    setWorkspaceFiles,
    skillRouteName,
    setSkillDetail,
    setError,
    pendingMentionRef,
    setComposer,
    setComposerFiles
  })

  const loadSkillDetail = useCallback(
    (name: string) => client.getSkill(name),
    [client]
  )

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
    <AppShell
      sidebarPanelRef={sidebarPanelRef}
      isDashboard={isDashboard}
      dashboardSection={dashboardSection}
      sidebarUserName={sidebarUserName}
      setSidebarCollapsed={setSidebarCollapsed}
      logoutSession={logoutSession}
      refreshCloudUserName={refreshCloudUserName}
      health={health}
      backendUrl={backendUrl}
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
      navigate={navigate}
      setProjectScopeId={setProjectScopeId}
      selectAllProjects={selectAllProjects}
      selectProjectScope={selectProjectScope}
      setProjectSettingsOpen={setProjectSettingsOpen}
      setNewProjectOpen={setNewProjectOpen}
      setGlobalSearchOpen={setGlobalSearchOpen}
      createSession={createSession}
      setFilesPanelCollapsed={setFilesPanelCollapsed}
      clearSessionSelection={clearSessionSelection}
      batchArchiveSelected={batchArchiveSelected}
      batchMoveSelected={batchMoveSelected}
      batchExportSelected={batchExportSelected}
      setBatchDeletePending={setBatchDeletePending}
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
      sidebarCollapsed={sidebarCollapsed}
      showConnectionLimitWarning={showConnectionLimitWarning}
      runningCount={runningCount}
      setConnectionLimitDismissed={setConnectionLimitDismissed}
      showSessionTabs={showSessionTabs}
      isHome={isHome}
      isProjectHome={isProjectHome}
      activeTitle={activeTitle}
      isDashboardOverview={isDashboardOverview}
      isDashboardStatus={isDashboardStatus}
      isDashboardGeneral={isDashboardGeneral}
      isDashboardAgentRuntime={isDashboardAgentRuntime}
      isDashboardAgentSandbox={isDashboardAgentSandbox}
      isDashboardAgentPrompts={isDashboardAgentPrompts}
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
      client={client}
      location={location}
      dashboardSkeletonKind={dashboardSkeletonKind}
      connecting={connecting}
      sessions={sessions}
      sessionPreviews={sessionPreviews}
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
      togglePinProject={togglePinProject}
      deleteProject={deleteProject}
      openTabs={openTabs}
      session={session}
      closeSessionTab={closeSessionTab}
      closeOtherSessionTabs={closeOtherSessionTabs}
      cliMenuOpen={cliMenuOpen}
      setCliMenuOpen={setCliMenuOpen}
      copiedResumeCommand={copiedResumeCommand}
      setCopiedResumeCommand={setCopiedResumeCommand}
      terminalOpen={terminalOpen}
      setTerminalOpen={setTerminalOpen}
      isInspect={isInspect}
      messages={messages}
      tools={tools}
      messagesLoaded={messagesLoaded}
      runActive={runActive}
      showChatSkeleton={showChatSkeleton}
      agentComposerSlotProps={agentComposerSlotProps}
      recentProjectIds={recentProjectIds}
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
      filesPanelRef={filesPanelRef}
      workspaceVersion={workspaceVersion}
      pendingOpenPath={pendingOpenPath}
      setPendingOpenPath={setPendingOpenPath}
      setComposer={setComposer}
      setComposerFiles={setComposerFiles}
      globalSearchOpen={globalSearchOpen}
      newProjectOpen={newProjectOpen}
      activeProject={activeProject}
      workspaceFiles={workspaceFiles}
      pendingMentionRef={pendingMentionRef}
      createProject={createProject}
      projectSettingsOpen={projectSettingsOpen}
      saveProjectSettings={saveProjectSettings}
      renameTarget={renameTarget}
      renameValue={renameValue}
      setRenameTarget={setRenameTarget}
      setRenameValue={setRenameValue}
      submitRename={submitRename}
      deleteTarget={deleteTarget}
      confirmDelete={confirmDelete}
      batchDeletePending={batchDeletePending}
      confirmBatchDelete={confirmBatchDelete}
    />
  )
}
