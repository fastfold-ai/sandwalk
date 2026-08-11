import { useCallback, useEffect, useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import {
  buildSessionSidebarModel,
  computeShowSessionTabs,
  resolveActiveTitle
} from '@/components/app/app-display'
import { AppShellConnected } from '@/components/app/AppShellConnected'
import { buildAppShellProps } from '@/components/app/build-app-shell-props'
import { AppGates } from '@/components/AppGates'
import { OpenRemoteWindowDialog } from '@/components/agents/OpenRemoteWindowDialog'
import { useAppBootstrap } from '@/hooks/useAppBootstrap'
import { useAppOpenTabs } from '@/hooks/useAppOpenTabs'
import {
  useAppRouteContext,
  useChatBySessionIdBridge
} from '@/hooks/useAppRouteContext'
import { useAppRouting } from '@/hooks/useAppRouting'
import { useAppSessionEffects } from '@/hooks/useAppSessionEffects'
import { useAppSessionLayer } from '@/hooks/useAppSessionLayer'
import { useAppShellEffects } from '@/hooks/useAppShellEffects'
import { useAppUiState } from '@/hooks/useAppUiState'
import { useDesktopNavigate } from '@/hooks/useDesktopNavigate'
import { useDesktopWindowMenu } from '@/hooks/useDesktopWindowMenu'
import { useMacDesktopOverlay } from '@/hooks/useMacDesktopOverlay'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import { visibleSessionIds } from '@/lib/sessions'

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()
  useMacDesktopOverlay()
  const ui = useAppUiState()
  const route = useAppRouting(location)
  const { setChatBySessionIdRef, setChatBySessionIdBridge } =
    useChatBySessionIdBridge()

  const bootstrap = useAppBootstrap({
    navigate,
    location,
    setChatBySessionId: setChatBySessionIdBridge,
    isDashboardModels: route.isDashboardModels
  })

  const onDesktopRoute = useCallback(
    (path: string) => {
      // Menubar New Agent / recent chats create sessions outside this window —
      // force-refresh so the sidebar + tab strip include them immediately.
      if (path.startsWith('/agents/')) {
        void bootstrap.loadSessions({ force: true })
      }
    },
    [bootstrap.loadSessions]
  )
  useDesktopNavigate(navigate, onDesktopRoute)
  const windowMenu = useDesktopWindowMenu()

  const tabs = useAppOpenTabs(
    ui.projectScopeId,
    ui.openTabsByProject,
    ui.setOpenTabsByProject
  )

  const context = useAppRouteContext({
    decodedIntegrationRouteName: route.decodedIntegrationRouteName,
    normalizedIntegrationRouteName: route.normalizedIntegrationRouteName,
    integrations: bootstrap.integrations,
    projectScopeId: ui.projectScopeId,
    openTabIds: tabs.openTabIds,
    projects: bootstrap.projects,
    mcpCatalogDetailId: route.mcpCatalogDetailId,
    mcpCatalog: bootstrap.mcpCatalog,
    mcpServerDetailId: route.mcpServerDetailId,
    mcpServers: bootstrap.mcpServers,
    sessionId: route.sessionId,
    sessions: bootstrap.sessions
  })

  const layer = useAppSessionLayer({
    client: bootstrap.client,
    health: bootstrap.health,
    sessions: bootstrap.sessions,
    setSessions: bootstrap.setSessions,
    setError: bootstrap.setError,
    loadSessions: bootstrap.loadSessions,
    loadSessionsRef: bootstrap.loadSessionsRef,
    loadSkillsRef: bootstrap.loadSkillsRef,
    loadProjects: bootstrap.loadProjects,
    setSandboxSettings: bootstrap.setSandboxSettings,
    skills: bootstrap.skills,
    mcpServers: bootstrap.mcpServers,
    modelOptions: bootstrap.modelOptions,
    specialists: bootstrap.specialists,
    runtimeSettings: bootstrap.runtimeSettings,
    setRuntimeSettings: bootstrap.setRuntimeSettings,
    loadModelOptions: bootstrap.loadModelOptions,
    sessionId: route.sessionId,
    sessionIdRef: ui.sessionIdRef,
    session: context.session,
    activeProjectId: context.activeProjectId,
    activeProject: context.activeProject,
    navigate,
    location,
    tabsScopeKey: tabs.tabsScopeKey,
    openTabsByProject: ui.openTabsByProject,
    setOpenTabsByProject: ui.setOpenTabsByProject,
    patchOpenTabs: tabs.patchOpenTabs,
    setOpenTabIds: tabs.setOpenTabIds,
    lastSessionByScope: ui.lastSessionByScope,
    setLastSessionByScope: ui.setLastSessionByScope,
    setProjectScopeId: ui.setProjectScopeId,
    setRecentProjectIds: ui.setRecentProjectIds,
    setCollapsedSidebarSections: ui.setCollapsedSidebarSections,
    setWorkspaceVersion: ui.setWorkspaceVersion,
    workspaceFiles: ui.workspaceFiles,
    setFilesPanelCollapsed: ui.setFilesPanelCollapsed,
    setTerminalOpen: ui.setTerminalOpen,
    setPendingOpenPath: ui.setPendingOpenPath,
    pendingAttachmentsRef: ui.pendingAttachmentsRef,
    setChatBySessionIdRef
  })

  // Route wins. Draft materialization uses a separate ref inside session CRUD
  // so /agents/new never "sticks" to a previous real session id.
  ui.sessionIdRef.current = route.sessionId

  const { showChatSkeleton } = useAppShellEffects({
    locationPathname: location.pathname,
    navigate,
    legacySkillRouteName: route.legacySkillRoute?.params.skillName,
    legacyIntegrationRouteKey: route.legacyIntegrationRoute?.params.integrationKey,
    onOnboardingPath: route.onOnboardingPath,
    onboardingStep: route.onboardingStep,
    sessionTitle: context.session?.title,
    titleSource: context.session?.titleSource,
    activeIntegration: context.activeIntegration,
    activeProject: context.activeProject,
    isDashboardOverview: route.isDashboardOverview,
    isDashboardStatus: route.isDashboardStatus,
    isDashboardGeneral: route.isDashboardGeneral,
    isDashboardAppearance: route.isDashboardAppearance,
    isDashboardModels: route.isDashboardModels,
    isDashboardTools: route.isDashboardTools,
    isDashboardDoctor: route.isDashboardDoctor,
    isDashboardBench: route.isDashboardBench,
    isDashboardStorage: route.isDashboardStorage,
    isDashboardEnvironment: route.isDashboardEnvironment,
    isSkills: route.isSkills,
    isDashboardSpecialists: route.isDashboardSpecialists,
    isIntegrations: route.isIntegrations,
    isDashboardData: route.isDashboardData,
    isDashboardAgentSandbox: route.isDashboardAgentSandbox,
    isDashboardAgentSecurity: route.isDashboardAgentSecurity,
    isSandboxLocalDetail: route.isSandboxLocalDetail,
    isSandboxModalDetail: route.isSandboxModalDetail,
    isDashboardAgentPrompts: route.isDashboardAgentPrompts,
    isDashboardVoice: route.isDashboardVoice,
    isDashboardAgentRuntime: route.isDashboardAgentRuntime,
    isDashboardMcp: route.isDashboardMcp,
    isLibrary: route.isLibrary,
    isSites: route.isSites,
    sidebarCollapsed: ui.sidebarCollapsed,
    filesPanelCollapsed: ui.filesPanelCollapsed,
    terminalOpen: ui.terminalOpen,
    sidebarPanelRef: ui.sidebarPanelRef,
    filesPanelRef: ui.filesPanelRef,
    collapsedSidebarSections: ui.collapsedSidebarSections,
    routeProjectId: route.routeProjectId,
    setProjectScopeId: ui.setProjectScopeId,
    messagesLoaded: layer.chat.messagesLoaded,
    runActive: layer.chat.runActive,
    sessionId: route.sessionId,
    client: bootstrap.client,
    messages: layer.chat.messages,
    setSessions: bootstrap.setSessions
  })

  useAppSessionEffects({
    setIntegrationValues: ui.setIntegrationValues,
    selectedIntegrationKey: context.selectedIntegrationKey,
    isIntegrations: route.isIntegrations,
    integrations: bootstrap.integrations,
    navigate,
    sessionId: route.sessionId,
    sessions: bootstrap.sessions,
    activeProjectId: context.activeProjectId,
    openSessionTab: tabs.openSessionTab,
    setOpenTabsByProject: ui.setOpenTabsByProject,
    setLastSessionByScope: ui.setLastSessionByScope,
    tabsScopeKey: tabs.tabsScopeKey,
    projectScopeId: ui.projectScopeId,
    client: bootstrap.client,
    workspaceVersion: ui.workspaceVersion,
    draftWorkspaceSessionId: ui.draftWorkspaceSessionId,
    setWorkspaceFiles: ui.setWorkspaceFiles,
    skillRouteName: route.skillRouteName,
    setSkillDetail: ui.setSkillDetail,
    setError: bootstrap.setError,
    pendingMentionRef: ui.pendingMentionRef,
    setComposer: layer.chat.setComposer,
    setComposerFiles: layer.chat.setComposerFiles
  })

  // Bench sessions are omitted from the global list (sidebar noise). When a
  // project is selected, reload with projectId so Project Home + scoped
  // sidebar show those chats.
  useEffect(() => {
    void bootstrap.loadSessions({
      force: true,
      projectId: ui.projectScopeId
    })
  }, [bootstrap.loadSessions, ui.projectScopeId])

  const { sections, openTabs } = buildSessionSidebarModel({
    sessions: bootstrap.sessions,
    activeProjectId: context.activeProjectId,
    openTabIds: tabs.openTabIds,
    activeSessionId: route.sessionId
  })
  const orderedVisibleSessionIds = useMemo(
    () => visibleSessionIds(sections, ui.collapsedSidebarSections),
    [sections, ui.collapsedSidebarSections]
  )
  const showSessionTabs = computeShowSessionTabs({
    isDashboard: route.isDashboard,
    isHome: route.isHome,
    isLibrary: route.isLibrary,
    isSites: route.isSites,
    isProjectHome: route.isProjectHome,
    isSkills: route.isSkills,
    isIntegrations: route.isIntegrations,
    sessionId: route.sessionId,
    openTabsLength: openTabs.length
  })
  const activeTitle = resolveActiveTitle({
    isDashboardOverview: route.isDashboardOverview,
    isDashboardStatus: route.isDashboardStatus,
    isDashboardGeneral: route.isDashboardGeneral,
    isDashboardAppearance: route.isDashboardAppearance,
    isDashboardAgentRuntime: route.isDashboardAgentRuntime,
    isDashboardAgentSecurity: route.isDashboardAgentSecurity,
    isDashboardAgentPrompts: route.isDashboardAgentPrompts,
    isDashboardVoice: route.isDashboardVoice,
    isDashboardModels: route.isDashboardModels,
    isDashboardData: route.isDashboardData,
    isDashboardTools: route.isDashboardTools,
    isDashboardDoctor: route.isDashboardDoctor,
    isDashboardBench: route.isDashboardBench,
    isDashboardStorage: route.isDashboardStorage,
    isDashboardEnvironment: route.isDashboardEnvironment,
    isSkills: route.isSkills,
    isDashboardSpecialists: route.isDashboardSpecialists,
    isIntegrations: route.isIntegrations,
    isDashboardMcp: route.isDashboardMcp,
    isHome: route.isHome,
    isLibrary: route.isLibrary,
    isSites: route.isSites,
    isProjectHome: route.isProjectHome,
    sessionTitle: context.session?.title
  })
  // Draft chats in a project get Files so shared project folder is reachable.
  const canShowFilesPanel = Boolean(
    route.sessionId &&
      (!isDraftAgentSessionId(route.sessionId) ||
        Boolean(context.activeProjectId))
  )

  const gate = AppGates({
    authBootstrapped: bootstrap.authBootstrapped,
    needsAuthLogin: bootstrap.needsAuthLogin,
    authLoggingIn: bootstrap.authLoggingIn,
    connecting: bootstrap.connecting,
    authLoginError: bootstrap.authLoginError,
    setAuthLoginError: bootstrap.setAuthLoginError,
    connect: bootstrap.connect,
    submitAuthLogin: bootstrap.submitAuthLogin,
    changeBackend: bootstrap.changeBackend,
    health: bootstrap.health,
    backendUrl: bootstrap.backendUrl,
    setBackendUrl: bootstrap.setBackendUrl,
    backendApiKey: bootstrap.backendApiKey,
    setBackendApiKey: bootstrap.setBackendApiKey,
    error: bootstrap.error,
    errorStack: bootstrap.errorStack,
    onOnboardingPath: route.onOnboardingPath,
    onboardingStep: route.onboardingStep,
    client: bootstrap.client,
    navigate,
    loadModelOptions: bootstrap.loadModelOptions,
    loadIntegrations: bootstrap.loadIntegrations,
    loadSkills: bootstrap.loadSkills,
    loadMcpServers: bootstrap.loadMcpServers,
    loadMcpCatalog: bootstrap.loadMcpCatalog
  })
  const remoteDialog = (
    <OpenRemoteWindowDialog
      open={windowMenu.remoteOpen}
      onOpenChange={windowMenu.setRemoteOpen}
      initialUrl={windowMenu.remoteInitialUrl}
    />
  )

  if (gate) {
    return (
      <>
        {gate}
        {remoteDialog}
      </>
    )
  }

  return (
    <>
      <AppShellConnected
        {...buildAppShellProps({
          ui,
          route,
          bootstrap,
          context,
          chat: layer.chat,
          tabs,
          actions: layer.actions,
          sandbox: layer.sandbox,
          scroll: layer.scroll,
          location,
          navigate,
          sections,
          openTabs,
          orderedVisibleSessionIds,
          showSessionTabs,
          activeTitle,
          canShowFilesPanel,
          conversationTimeline: layer.conversationTimeline,
          agentComposerSlotProps: layer.agentComposerSlotProps,
          activeRunTodos: layer.activeRunTodos,
          activeRunTools: layer.activeRunTools,
          activeBuildPlan: layer.activeBuildPlan,
          builtPlanPaths: layer.builtPlanPaths,
          submitApprovals: layer.submitApprovals,
          prefetchSessionMessages: layer.prefetchSessionMessages,
          showChatSkeleton
        })}
      />
      {remoteDialog}
    </>
  )
}
