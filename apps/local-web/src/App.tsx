import type { SessionGroup } from '@sandwalk/agent-ui-core'
import { isSessionGroupId } from '@sandwalk/agent-ui-core'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
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
import { useGlobalSessionEvents } from '@/hooks/useGlobalSessionEvents'
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
import { setChatDateBoosts } from '@/lib/chat-date-boost'
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
  const hideLauncherAfterOpen = Boolean(
    bootstrap.connectionPaused && !bootstrap.health
  )
  const windowMenu = useDesktopWindowMenu({ hideLauncherAfterOpen })

  const tabs = useAppOpenTabs(
    ui.projectScopeId,
    ui.openTabsByProject,
    ui.setOpenTabsByProject
  )
  const tabGroupsStore = useAppTabGroups(
    ui.projectScopeId,
    bootstrap.sessions,
    ui.allTabGroups,
    ui.setAllTabGroups,
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

  /*
   * Al navegar a un grupo (`route.sessionId === grp_xxx`), persistimos su
   * id en `openTabsByProject` del scope activo — mismo patrón que ya usa
   * `useAppSessionEffects` con chats individuales via `openSessionTab`.
   * Efecto: el chip del grupo aparece en la strip del proyecto donde el
   * user navegó, y al recargar se restaura. Si el user visita el mismo
   * grupo desde otro proyecto, se persiste ahí también, sin duplicar.
   */
  useEffect(() => {
    if (!activeGroup) return
    tabs.openSessionTab(activeGroup.id)
  }, [activeGroup, tabs.openSessionTab])

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

  // Single global SSE for session-level events (create/update/delete/
  // status_changed/run.*). Replaces the previous 2-second poll + snapshot
  // diff approach that produced false-positive attention marks whenever
  // two independent fetch sources (loadSessions + loadForeignSessions)
  // returned stale overlapping views of the same chat's status.
  useGlobalSessionEvents({
    client: bootstrap.client,
    health: bootstrap.health,
    sessionIdRef: ui.sessionIdRef,
    setSessions: bootstrap.setSessions
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
  /*
   * Al crear un split view, "refrescamos" la fecha visible de cada chat
   * hijo al momento actual — así los chats viejos suben a Today junto con
   * el grupo nuevo (sin quedar dispersos en Yesterday/Older). El boost es
   * local (localStorage) porque el server no acepta PATCH sobre
   * `last_message_at`; se limpia solo cuando el chat recibe actividad real
   * que iguala o supera el boost. Ver `lib/chat-date-boost.ts`.
   */
  const createSplitGroup = useCallback(
    (chatIds: string[]): string | null => {
      const groupId = tabGroupsStore.createGroup(chatIds)
      if (!groupId) return null
      const now = new Date().toISOString()
      setChatDateBoosts(chatIds, now)
      bootstrap.setSessions(current =>
        current.map(s =>
          chatIds.includes(s.id) ? { ...s, lastMessageAt: now } : s
        )
      )
      return groupId
    },
    [tabGroupsStore, bootstrap]
  )

  const createSplitFromSelection = useCallback(() => {
    const ids = Array.from(selectedChatIds).filter(
      id => !isSessionGroupId(id)
    )
    if (ids.length < 2) return
    const groupId = createSplitGroup(ids)
    if (groupId) {
      setSelectedChatIds(new Set())
      navigate(`/agents/${groupId}`)
    }
  }, [selectedChatIds, createSplitGroup, navigate])

  /*
   * "Create split view" desde el context menu de un chat: crea un grupo
   * REAL con isPending=true (un solo chat + placeholder). El
   * `ChatSplitContainer` pinta el chat A en el panel izquierdo y el
   * picker en el derecho. Al elegir un compañero → promotePendingGroup
   * agrega el chat y limpia el flag. Al cancelar (X del picker) →
   * dissolveGroup elimina el grupo (chat A vuelve suelto).
   */
  const handleCreateSplitFromChat = useCallback(
    (sourceId: string) => {
      const groupId = tabGroupsStore.createPendingGroup(sourceId)
      if (groupId) navigate(`/agents/${groupId}`)
    },
    [tabGroupsStore, navigate]
  )

  const handlePickSplitPartner = useCallback(
    (partnerId: string) => {
      const groupId = route.sessionId
      if (!groupId || !isSessionGroupId(groupId)) return
      const group = tabGroupsStore.allTabGroups.find(g => g.id === groupId)
      if (!group || !group.isPending) return
      const sourceId = group.chatIds[0]
      if (sourceId === partnerId) return
      // Boost la fecha del compañero como si el split se hubiera creado
      // con los dos desde el principio — así el chat entrante también
      // sube a Today (mismo comportamiento que createSplitGroup).
      const now = new Date().toISOString()
      setChatDateBoosts([partnerId], now)
      bootstrap.setSessions(current =>
        current.map(s =>
          s.id === partnerId ? { ...s, lastMessageAt: now } : s
        )
      )
      tabGroupsStore.promotePendingGroup(groupId, partnerId)
    },
    [route.sessionId, tabGroupsStore, bootstrap]
  )

  const handleCancelPendingSplit = useCallback(() => {
    const groupId = route.sessionId
    if (!groupId || !isSessionGroupId(groupId)) return
    const group = tabGroupsStore.allTabGroups.find(g => g.id === groupId)
    if (!group || !group.isPending) return
    const sourceId = group.chatIds[0]
    tabGroupsStore.dissolveGroup(groupId)
    if (sourceId) navigate(`/agents/${sourceId}`)
  }, [route.sessionId, tabGroupsStore, navigate])

  /*
   * "Add chat to split" desde el botón "+" en la derecha del split ya
   * armado: agrega el chat elegido al grupo existente (via `addToGroup`),
   * boost su fecha para que suba a Today (mismo comportamiento que
   * createSplitGroup), y setea ese chat como activo dentro del grupo
   * (para que se vea en foco cuando el split se re-renderiza).
   */
  /*
   * "Close" desde el header de un chat DENTRO del split: saca el chat
   * del grupo (no lo borra). El chat vuelve a estar suelto en su
   * proyecto. Si el grupo queda con menos de 2 chats, se auto-disuelve
   * (no tiene sentido un split con 1 sólo chat) y navegamos al que
   * queda.
   */
  const handleRemoveChatFromSplit = useCallback(
    (chatId: string) => {
      const groupId = route.sessionId
      if (!groupId || !isSessionGroupId(groupId)) return
      const group = tabGroupsStore.allTabGroups.find(g => g.id === groupId)
      if (!group) return
      const survivor = group.chatIds.find(id => id !== chatId) ?? null
      const nextSize = tabGroupsStore.removeFromGroup(groupId, chatId)
      if (nextSize >= 0 && nextSize < 2) {
        tabGroupsStore.dissolveGroup(groupId)
        if (survivor) navigate(`/agents/${survivor}`)
      }
    },
    [route.sessionId, tabGroupsStore, navigate]
  )

  const handleAddChatToSplit = useCallback(
    (chatId: string) => {
      const groupId = route.sessionId
      if (!groupId || !isSessionGroupId(groupId)) return
      const group = tabGroupsStore.allTabGroups.find(g => g.id === groupId)
      if (!group || group.isPending) return
      if (group.chatIds.includes(chatId)) return
      const now = new Date().toISOString()
      setChatDateBoosts([chatId], now)
      bootstrap.setSessions(current =>
        current.map(s =>
          s.id === chatId ? { ...s, lastMessageAt: now } : s
        )
      )
      tabGroupsStore.addToGroup(groupId, chatId)
      tabGroupsStore.setGroupActiveChat(groupId, chatId)
    },
    [route.sessionId, tabGroupsStore, bootstrap]
  )

  /*
   * Close split (strip only): quita el chip de la strip del scope activo.
   * El grupo sigue existiendo — sólo desaparece la pestaña. Se puede
   * volver a abrir desde el sidebar.
   */
  const handleCloseTabGroup = useCallback(
    (groupId: string) => {
      layer.actions.closeSessionTab(groupId)
    },
    [layer.actions]
  )

  // Estado del dialog "Rename split view". Análogo a `renameTarget` de
  // chats: el target guarda el grupo cuyo nombre se edita; el value es el
  // input controlado. `submitRenameGroup` llama al store cuando el trim
  // del value no queda vacío. La única validación es "no vacío".
  const [renameGroupTarget, setRenameGroupTarget] =
    useState<SessionGroup | null>(null)
  const [renameGroupValue, setRenameGroupValue] = useState('')
  const submitRenameGroup = useCallback(() => {
    const name = renameGroupValue.trim()
    if (!renameGroupTarget || !name) return
    tabGroupsStore.renameGroup(renameGroupTarget.id, name)
    setRenameGroupTarget(null)
    setRenameGroupValue('')
  }, [renameGroupTarget, renameGroupValue, tabGroupsStore])
  const openRenameGroupDialog = useCallback((group: SessionGroup) => {
    setRenameGroupTarget(group)
    setRenameGroupValue(group.name || '')
  }, [])

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

  /*
   * Set de todos los chatIds que viven adentro de cualquier grupo.
   * Se computa antes de `useAppSessionEffects` porque su callback
   * `chatIsInsideAnyGroup` lo reusa para hacer lookup O(1) en vez de
   * escanear grupos en cada llamada (`.some(...includes(...))` era
   * O(grupos × chatsPerGrupo) por invocación).
   *
   * También lo usa el filtro de `openTabIds` más abajo — mismo Set,
   * misma referencia estable mientras `allTabGroups` no cambie.
   */
  const chatsInsideGroupIds = useMemo(() => {
    const set = new Set<string>()
    for (const g of tabGroupsStore.allTabGroups) {
      for (const id of g.chatIds) set.add(id)
    }
    return set
  }, [tabGroupsStore.allTabGroups])

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
    chatIsInsideAnyGroup: (chatId: string) => chatsInsideGroupIds.has(chatId),
    tabGroups: tabGroupsStore.allTabGroups
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

  const cleanedOpenTabIds = useMemo(
    () => tabs.openTabIds.filter(id => !chatsInsideGroupIds.has(id)),
    [tabs.openTabIds, chatsInsideGroupIds]
  )

  /*
   * Cross-project split groups: `bootstrap.sessions` is fetched scoped to
   * `activeProjectId`, so any chat inside a group that belongs to a
   * different project is absent from the sessions cache. That absence
   * turns the split panel header into "Untitled / Sin proyecto asociado"
   * (with actions hidden) and drops the chat from the sidebar tree of
   * the group. This effect resolves those "foreign" chats via the bulk
   * endpoint so headers + sidebar stay coherent regardless of scope.
   *
   * The effect fires on:
   *   - Bootstrap (initial `sessions` populate)
   *   - Scope change (sessions list gets replaced)
   *   - addToGroup / promotePendingGroup (chatsInsideGroupIds grows)
   *   - removeFromGroup / dissolveGroup (no-op if all present, else prune)
   *
   * `loadForeignSessions` internally dedupes against the current cache
   * and in-flight lookups so re-firing on every render is cheap.
   */
  useEffect(() => {
    const knownIds = new Set(bootstrap.sessions.map(s => s.id))
    const missing: string[] = []
    for (const id of chatsInsideGroupIds) {
      if (!knownIds.has(id)) missing.push(id)
    }
    if (missing.length === 0) return
    void bootstrap.loadForeignSessions(missing)
  }, [bootstrap.sessions, chatsInsideGroupIds, bootstrap.loadForeignSessions])

  /*
   * Auto-redirect eliminado: causaba loop infinito de "Maximum update
   * depth exceeded" porque `tabGroupsStore` re-referenciaba en cada
   * render (efecto se auto-disparaba). El comportamiento equivalente
   * ahora se maneja pasivamente: el chat suelto queda filtrado del
   * strip y del sidebar, y `effectiveSessionId` sigue mostrando el
   * grupo si `activeGroup` se resuelve. Si el user tiene la URL
   * directa al chat individual, ve el split del grupo con ese chat
   * activo — sin redirect.
   */

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
    autoRestoring: bootstrap.autoRestoring,
    setConnectionPaused: bootstrap.setConnectionPaused,
    backendUrl: bootstrap.backendUrl,
    setBackendUrl: bootstrap.setBackendUrl,
    backendApiKey: bootstrap.backendApiKey,
    setBackendApiKey: bootstrap.setBackendApiKey,
    error: bootstrap.error,
    errorStack: bootstrap.errorStack,
    localStarting: bootstrap.localStarting,
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
      hideLauncherAfterOpen={hideLauncherAfterOpen}
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
          effectiveSessionId,
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
          onSplitWithNextTab: handleCreateSplitFromChat,
          onPickSplitPartner: handlePickSplitPartner,
          onCancelPendingSplit: handleCancelPendingSplit,
          onAddChatToSplit: handleAddChatToSplit,
          onRemoveChatFromSplit: handleRemoveChatFromSplit,
          closeTabGroup: handleCloseTabGroup,
          renameGroupTarget,
          renameGroupValue,
          setRenameGroupTarget,
          setRenameGroupValue,
          submitRenameGroup,
          selectedChatIds,
          toggleSelectChat,
          clearSelectChats,
          createSplitFromSelection,
          createSplitFromSidebar: () => {
            const ids = Array.from(layer.actions.selectedSessionIds).filter(
              id => !isSessionGroupId(id)
            )
            if (ids.length < 2) return
            const groupId = createSplitGroup(ids)
            if (groupId) {
              layer.actions.clearSessionSelection()
              navigate(`/agents/${groupId}`)
            }
          },
          canSplitFromSidebar:
            layer.actions.selectedSessionIds.size >= 2 &&
            Array.from(layer.actions.selectedSessionIds).filter(
              id => !isSessionGroupId(id)
            ).length >= 2,
          onSelectTabGroup: (groupId: string) => {
            navigate(`/agents/${groupId}`)
          },
          onRenameTabGroup: openRenameGroupDialog,
          /*
           * "Go to project" desde el menú de un chat invitado del split:
           * cambia el scope al proyecto natal del chat y navega al chat
           * (no al split). El chat pasa a verse como una conversación
           * suelta en su proyecto — para volver al split, el usuario
           * regresa al scope original desde el sidebar.
           */
          onGoToChatProject: chat => {
            if (chat.projectId) {
              layer.actions.selectProjectScope(chat.projectId)
            } else {
              layer.actions.selectAllProjects()
            }
            navigate(`/agents/${chat.id}`)
          }
        })}
      />
      {remoteDialog}
    </>
  )
}
