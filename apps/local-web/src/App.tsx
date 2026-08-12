import React, { useCallback, useEffect, useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { OpenRemoteWindowDialog } from '@/components/agents/OpenRemoteWindowDialog'
import {
  buildSessionSidebarModel,
  computeShowSessionTabs,
  resolveActiveTitle
} from '@/components/app/app-display'
import { AppShellConnected } from '@/components/app/AppShellConnected'
import { buildAppShellProps } from '@/components/app/build-app-shell-props'
import { AppGates } from '@/components/AppGates'
import { useAppBootstrap } from '@/hooks/useAppBootstrap'
import { useAppOpenTabs } from '@/hooks/useAppOpenTabs'
import { useAppTabGroups } from '@/hooks/useAppTabGroups'
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
  const tabGroupsStore = useAppTabGroups(
    ui.projectScopeId,
    ui.tabGroupsByProject,
    ui.setTabGroupsByProject,
    tabs.setOpenTabIds
  )

  // Grupos son "tabs virtuales": cuando la ruta apunta a un grupo, el shell
  // trabaja con su chat activo para todos los efectos por-sesión y luego el
  // AgentSessionMainPanel decide si renderiza vista split o single-tab.
  const activeGroup = useMemo(
    () =>
      route.sessionId
        ? tabGroupsStore.allTabGroups.find(g => g.id === route.sessionId) ||
          null
        : null,
    [route.sessionId, tabGroupsStore.allTabGroups]
  )
  const effectiveSessionId = activeGroup
    ? activeGroup.activeChatId
    : route.sessionId

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
    sessionId: effectiveSessionId,
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
    sessionId: effectiveSessionId,
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

  // Multi-select para split view: cualquier click con Shift/Meta en una
  // pestaña, chat del sidebar o item del dropdown agrega/quita ese chatId
  // aquí. Cuando hay >= 2 seleccionados aparece un action bar que crea el
  // grupo con todos.
  const [selectedChatIds, setSelectedChatIds] = React.useState<Set<string>>(
    () => new Set()
  )
  const toggleSelectChat = useCallback((id: string) => {
    setSelectedChatIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])
  const clearSelectChats = useCallback(() => {
    setSelectedChatIds(prev => (prev.size === 0 ? prev : new Set()))
  }, [])
  const createSplitFromSelection = useCallback(() => {
    const ids = Array.from(selectedChatIds).filter(
      id => !id.startsWith('grp_')
    )
    if (ids.length < 2) return
    const groupId = tabGroupsStore.createGroup(ids)
    if (groupId) {
      setSelectedChatIds(new Set())
      navigate(`/agents/${groupId}`)
    }
  }, [selectedChatIds, tabGroupsStore, navigate])

  // Punto de entrada MVP para crear un grupo: "Split with next tab" agrupa
  // el chat sobre el que se hizo click con el siguiente tab abierto (o el
  // anterior, si es el último). Los pickers ricos (multi-select) vienen en
  // Fase 3 completa; esto habilita testear el flujo end-to-end mientras
  // tanto.
  const handleSplitWithNextTab = useCallback(
    (sourceId: string) => {
      const ids = tabs.openTabIds
      const idx = ids.indexOf(sourceId)
      if (idx < 0) return
      // Prefer next; wrap to previous if the source is the last tab.
      const partnerId =
        ids
          .slice(idx + 1)
          .find(id => id !== sourceId && !id.startsWith('grp_')) ||
        ids
          .slice(0, idx)
          .reverse()
          .find(id => id !== sourceId && !id.startsWith('grp_'))
      if (!partnerId) return
      const groupId = tabGroupsStore.createGroup([sourceId, partnerId])
      if (groupId) {
        navigate(`/agents/${groupId}`)
      }
    },
    [tabs.openTabIds, tabGroupsStore, navigate]
  )

  // Args comunes que todo `SessionChatMount` de split view va a instanciar
  // combinándolos con su chatId + session propia. Se calcula una vez para que
  // los mounts secundarios de un grupo puedan levantar su pipeline con los
  // mismos handles compartidos que ya usa el mount activo.
  const perSessionBaseArgs = useMemo(
    () => ({
      client: bootstrap.client,
      health: bootstrap.health,
      navigate,
      activeProjectId: context.activeProjectId,
      activeProject: context.activeProject,
      tabsScopeKey: tabs.tabsScopeKey,
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
      openTabsByProject: ui.openTabsByProject,
      setOpenTabsByProject: ui.setOpenTabsByProject,
      lastSessionByScope: ui.lastSessionByScope,
      setLastSessionByScope: ui.setLastSessionByScope,
      setProjectScopeId: ui.setProjectScopeId,
      setRecentProjectIds: ui.setRecentProjectIds,
      patchOpenTabs: tabs.patchOpenTabs,
      setOpenTabIds: tabs.setOpenTabIds,
      setCollapsedSidebarSections: ui.setCollapsedSidebarSections,
      setWorkspaceVersion: ui.setWorkspaceVersion,
      workspaceFiles: ui.workspaceFiles,
      setFilesPanelCollapsed: ui.setFilesPanelCollapsed,
      setTerminalOpen: ui.setTerminalOpen,
      setPendingOpenPath: ui.setPendingOpenPath,
      pendingAttachmentsRef: ui.pendingAttachmentsRef,
      setChatBySessionIdRef
    }),
    [
      bootstrap.client,
      bootstrap.health,
      navigate,
      context.activeProjectId,
      context.activeProject,
      tabs.tabsScopeKey,
      bootstrap.sessions,
      bootstrap.setSessions,
      bootstrap.setError,
      bootstrap.loadSessions,
      bootstrap.loadSessionsRef,
      bootstrap.loadSkillsRef,
      bootstrap.loadProjects,
      bootstrap.setSandboxSettings,
      bootstrap.skills,
      bootstrap.mcpServers,
      bootstrap.modelOptions,
      bootstrap.specialists,
      bootstrap.runtimeSettings,
      bootstrap.setRuntimeSettings,
      bootstrap.loadModelOptions,
      ui.openTabsByProject,
      ui.setOpenTabsByProject,
      ui.lastSessionByScope,
      ui.setLastSessionByScope,
      ui.setProjectScopeId,
      ui.setRecentProjectIds,
      tabs.patchOpenTabs,
      tabs.setOpenTabIds,
      ui.setCollapsedSidebarSections,
      ui.setWorkspaceVersion,
      ui.workspaceFiles,
      ui.setFilesPanelCollapsed,
      ui.setTerminalOpen,
      ui.setPendingOpenPath,
      ui.pendingAttachmentsRef,
      setChatBySessionIdRef
    ]
  )

  // Route wins. Draft materialization uses a separate ref inside session CRUD
  // so /agents/new never "sticks" to a previous real session id.
  ui.sessionIdRef.current = effectiveSessionId

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
    sessionId: effectiveSessionId,
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
    sessionId: effectiveSessionId,
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
    setComposerFiles: layer.chat.setComposerFiles,
    chatIsInsideAnyGroup: (chatId: string) =>
      tabGroupsStore.allTabGroups.some(g => g.chatIds.includes(chatId))
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

  /*
   * `openTabIds` puede tener chatIds sueltos que en realidad ya viven
   * dentro de un grupo (residuos de storage viejo, o carreras al crear
   * un grupo). Los filtramos aquí para que nunca se vean afuera del
   * grupo — el grupo es la única representación válida. Excepción: si
   * el usuario está navegando explícitamente al chat suelto
   * (`route.sessionId`), lo dejamos pasar para no ocultarlo en su misma
   * cara.
   */
  const chatsInsideGroupIds = useMemo(() => {
    const set = new Set<string>()
    for (const g of tabGroupsStore.allTabGroups) {
      for (const id of g.chatIds) set.add(id)
    }
    return set
  }, [tabGroupsStore.allTabGroups])
  const cleanedOpenTabIds = useMemo(
    () =>
      tabs.openTabIds.filter(
        id => id === route.sessionId || !chatsInsideGroupIds.has(id)
      ),
    [tabs.openTabIds, route.sessionId, chatsInsideGroupIds]
  )

  const { sections, openTabs } = buildSessionSidebarModel({
    sessions: bootstrap.sessions,
    // Pasamos los grupos GLOBALES (todos los scopes) para que el modelo
    // pueda resolver un `grp_xxx` aunque el proyecto activo no coincida
    // con el scope donde el grupo se creó. `buildSessionSidebarModel`
    // internamente filtra por lo aplicable al scope actual — pero puede
    // reconocer un grupo que atraviesa scopes en `openTabIds`.
    tabGroups: tabGroupsStore.allTabGroups,
    activeProjectId: context.activeProjectId,
    openTabIds: cleanedOpenTabIds,
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
    connectionPaused: bootstrap.connectionPaused,
    setConnectionPaused: bootstrap.setConnectionPaused,
    backendUrl: bootstrap.backendUrl,
    setBackendUrl: bootstrap.setBackendUrl,
    backendApiKey: bootstrap.backendApiKey,
    setBackendApiKey: bootstrap.setBackendApiKey,
    error: bootstrap.error,
    errorStack: bootstrap.errorStack,
    setError: bootstrap.setError,
    onOnboardingPath: route.onOnboardingPath,
    onboardingStep: route.onboardingStep,
    client: bootstrap.client,
    navigate,
    loadModelOptions: bootstrap.loadModelOptions,
    loadIntegrations: bootstrap.loadIntegrations,
    loadSkills: bootstrap.loadSkills,
    loadMcpServers: bootstrap.loadMcpServers,
    loadMcpCatalog: bootstrap.loadMcpCatalog,
    onOpenRemote: prefillUrl => {
      windowMenu.setRemoteInitialUrl(prefillUrl ?? null)
      windowMenu.setRemoteOpen(true)
    }
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
          openTabIds: cleanedOpenTabIds,
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
          showChatSkeleton,
          tabGroupsStore,
          activeGroup,
          perSessionBaseArgs,
          allSessions: bootstrap.sessions,
          onSplitWithNextTab: handleSplitWithNextTab,
          selectedChatIds,
          toggleSelectChat,
          clearSelectChats,
          createSplitFromSelection,
          createSplitFromSidebar: () => {
            const ids = Array.from(layer.actions.selectedSessionIds).filter(
              id => !id.startsWith('grp_')
            )
            if (ids.length < 2) return
            const groupId = tabGroupsStore.createGroup(ids)
            if (groupId) {
              layer.actions.clearSessionSelection()
              navigate(`/agents/${groupId}`)
            }
          },
          canSplitFromSidebar:
            layer.actions.selectedSessionIds.size >= 2 &&
            Array.from(layer.actions.selectedSessionIds).filter(
              id => !id.startsWith('grp_')
            ).length >= 2,
          onSelectTabGroup: (groupId: string) => {
            navigate(`/agents/${groupId}`)
          }
        })}
      />
      {remoteDialog}
    </>
  )
}
