import type { SessionGroup, TerminalSession } from '@sandwalk/agent-ui-core'
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { AboutUpdateWindow } from '@/components/AboutUpdateWindow'
import { CapyOverlay } from '@/components/agents/capy/CapyOverlay'
import { OpenRemoteWindowDialog } from '@/components/agents/OpenRemoteWindowDialog'
import { PaneContextMenu } from '@/components/agents/PaneContextMenu'
import {
  buildSessionSidebarModel,
  computeShowSessionTabs,
  resolveActiveTitle
} from '@/components/app/app-display'
import { AppShellConnected } from '@/components/app/AppShellConnected'
import { buildAppShellProps } from '@/components/app/build-app-shell-props'
import { OfflineBanner } from '@/components/app/OfflineBanner'
import { AppGates } from '@/components/AppGates'
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
import { useAppTabGroups } from '@/hooks/useAppTabGroups'
import { useAppTerminals } from '@/hooks/useAppTerminals'
import { useAppUiState } from '@/hooks/useAppUiState'
import { buildGridTree, splitPane } from '@/hooks/useChatTiling'
import { useDesktopNavigate } from '@/hooks/useDesktopNavigate'
import { useDesktopWindowMenu } from '@/hooks/useDesktopWindowMenu'
import { useEventsMux } from '@/hooks/useEventsMux'
import { useGlobalSessionEvents } from '@/hooks/useGlobalSessionEvents'
import { useLatestRef } from '@/hooks/useLatestRef'
import { useMacDesktopOverlay } from '@/hooks/useMacDesktopOverlay'
import { useOfflineStatus } from '@/hooks/useOfflineStatus'
import { notifyMissedCompletions } from '@/lib/browser-notifications'
import { applyCapyOpenSplit, parseGridLayout } from '@/lib/capy-ui'
import { setChatDateBoosts } from '@/lib/chat-date-boost'
import { isAboutDesktopWindow } from '@/lib/desktop'
import { isDraftAgentSessionId, sessionRoutePath } from '@/lib/draft-agent'
import {
  refreshInstalledAgents,
  useExternalAgentActions
} from '@/lib/external-agent-actions'
import { setFocusedItemId } from '@/lib/focused-item'
import { setItemOpener } from '@/lib/item-opener'
import { getMonitorFingerprint } from '@/lib/monitor-fingerprint'
import {
  cliHarnessPreset,
  type PaneSplitDirection,
  type PaneSplitTarget
} from '@/lib/pane-split'
import { perfCount } from '@/lib/perf-probe'
import { resolveItemLocation } from '@/lib/resolve-item-location'
import { useChatActivity } from '@/lib/session-activity'
import {
  pruneSessionAttention,
  recoverUnreadFromSessions
} from '@/lib/session-attention'
import { visibleSessionIds } from '@/lib/sessions'
import { resolveStripActiveId } from '@/lib/strip-active'
import { clearTerminalActivity } from '@/lib/terminal-attention'
import { queueTerminalStartup } from '@/lib/terminal-startup'
import { useTerminalsStore } from '@/lib/terminals-store'

/** Stable empty list so the sidebar-only model never sees a new array. */
const EMPTY_TAB_IDS: string[] = []

export default function App() {
  perfCount('render.App')
  // Shell-level chat signal: flips only when a run starts/stops or asks for
  // approval — per-token updates stay inside each pane's own subscription.
  const activityBySessionId = useChatActivity()
  const location = useLocation()
  const navigate = useNavigate()
  useMacDesktopOverlay()
  // Poll for offline status to show the banner
  const { status: offlineStatus } = useOfflineStatus(5000)
  // Reserve the tiling split shortcuts (⌘D / ⇧⌘D / ⌘W) so the WebView
  // never falls back to its default meanings (Add Bookmark, Close Tab)
  // on pages where the ChatTilingContainer isn't mounted (Welcome,
  // Library, Bench, Settings, ...). The actual split logic still lives
  // in ChatTilingContainer; this guard just kills the default action —
  // a no-op is always safer than surprising Chromium behavior.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey
      if (!meta) return
      const key = e.key.toLowerCase()
      if (key === 'd' || key === 'w') e.preventDefault()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
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

  // FAS-107 GF1/GF6: terminals for the active project, shared source of
  // truth for both the sidebar list and the tab strip (so a fresh
  // create appears everywhere without per-consumer fetching).
  const terminalsLive = useAppTerminals(
    bootstrap.client,
    ui.projectScopeId ?? null
  )
  const handleDeleteTerminalGlobal = useCallback(
    async (terminalId: string) => {
      if (!bootstrap.client) return
      try {
        terminalsLive.removeOptimistic(terminalId)
        await bootstrap.client.deleteTerminal(terminalId)
        clearTerminalActivity(terminalId)
        terminalsLive.refresh()
      } catch (err) {
        console.error('deleteTerminal (global) failed', err)
      }
    },
    [bootstrap.client, terminalsLive]
  )

  const handleMoveTerminalToProject = useCallback(
    async (terminalId: string, projectId: string | null) => {
      if (!bootstrap.client) return
      try {
        await bootstrap.client.updateTerminal(terminalId, { projectId })
        terminalsLive.refresh()
      } catch (err) {
        console.error('updateTerminal (move) failed', err)
      }
    },
    [bootstrap.client, terminalsLive]
  )

  const handleRenameTerminal = useCallback(
    async (terminalId: string, nextTitle: string) => {
      if (!bootstrap.client) return
      const cleaned = nextTitle.trim()
      if (!cleaned) return
      // FAS-107 X4.2: patch optimista al store singleton para
      // actualización instantánea del UI. Antes esperábamos el
      // round-trip del backend + un refresh (~400ms de lag visible).
      // El refresh queda como reconciliación de fondo.
      useTerminalsStore.getState().patch(terminalId, { title: cleaned })
      try {
        await bootstrap.client.updateTerminal(terminalId, { title: cleaned })
        terminalsLive.refresh()
      } catch (err) {
        console.error('updateTerminal (rename) failed', err)
      }
    },
    [bootstrap.client, terminalsLive]
  )

  // X2 Fix 1: dialog Radix para renombrar terminal (antes window.prompt,
  // roto en Tauri Mac). Estado + submit + dispatcher que abre el dialog.
  const [renameTerminalTarget, setRenameTerminalTarget] =
    useState<TerminalSession | null>(null)
  const [renameTerminalValue, setRenameTerminalValue] = useState('')

  const submitRenameTerminal = useCallback(async () => {
    const target = renameTerminalTarget
    if (!target) return
    const cleaned = renameTerminalValue.trim()
    if (!cleaned) return
    setRenameTerminalTarget(null)
    setRenameTerminalValue('')
    await handleRenameTerminal(target.id, cleaned)
  }, [renameTerminalTarget, renameTerminalValue, handleRenameTerminal])

  const promptRenameTerminal = useCallback(
    (terminalId: string) => {
      const current = terminalsLive.terminals.find(t => t.id === terminalId)
      if (!current) return
      setRenameTerminalTarget(current)
      setRenameTerminalValue(current.title ?? '')
    },
    [terminalsLive.terminals]
  )

  const handleToggleTerminalOrganizeLabel = useCallback(
    async (terminalId: string, label: 'pinned' | 'archive') => {
      if (!bootstrap.client) return
      const current = terminalsLive.terminals.find(t => t.id === terminalId)
      // Empty string = clear (the store maps `"" -> None` to null out the
      // column). Explicit label = set. Toggles between the label and null.
      const nextLabel: string = current?.organizeLabel === label ? '' : label
      try {
        await bootstrap.client.updateTerminal(terminalId, {
          organizeLabel: nextLabel
        })
        terminalsLive.refresh()
      } catch (err) {
        console.error('updateTerminal (organize) failed', err)
      }
    },
    [bootstrap.client, terminalsLive]
  )

  // FAS-107 GF10: `⌘⇧T` opens a new terminal in the active project and
  // navigates to it. Handled at the shell so it works from any page.
  // Declared AFTER `bootstrap` so `bootstrap.client` isn't in TDZ.
  const bootstrapClientForShortcut = bootstrap.client
  const bootstrapActiveProjectIdForShortcut = ui.projectScopeId
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey
      if (!meta || !e.shiftKey) return
      if (e.key.toLowerCase() !== 't') return
      e.preventDefault()
      const client = bootstrapClientForShortcut
      if (!client) return
      void client
        .createTerminal({
          projectId: bootstrapActiveProjectIdForShortcut ?? null
        })
        .then(term => {
          // FAS-107 P6: register the new terminal in the strip BEFORE
          // navigating, so a chip appears (parity with the "+ New
          // terminal" dropdown flow).
          openSessionTabRef.current?.(term.id)
          navigate(`/terminals/${term.id}`)
        })
        .catch(err => console.error('⌘⇧T createTerminal failed', err))
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [
    bootstrapClientForShortcut,
    bootstrapActiveProjectIdForShortcut,
    navigate
  ])

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
  // FAS-107 P6: expose `openSessionTab` to the ⌘⇧T effect declared above
  // (which sits before `tabs` for TDZ reasons). The ref lets the effect
  // register the new terminal id in the strip right after creation so a
  // chip appears — parity with the "+" dropdown flow in
  // AgentSessionMainPanel.
  const openSessionTabRef = useRef(tabs.openSessionTab)
  useEffect(() => {
    openSessionTabRef.current = tabs.openSessionTab
  }, [tabs.openSessionTab])

  // Claude Code / Codex / OpenCode / fx bridge: menus deep in the tree call
  // `continueSessionIn` / `convertTerminalToSession`; give them the client
  // and a way to open the resulting chat or terminal.
  const openItemFromExternal = useCallback(
    (id: string) => {
      openSessionTabRef.current?.(id)
      navigate(id.startsWith('term_') ? `/terminals/${id}` : `/agents/${id}`)
    },
    [navigate]
  )
  const externalClient = bootstrap.client
  const reloadSessionsForExternal = bootstrap.loadSessions
  const setSessionsForExternal = bootstrap.setSessions
  // Refs so this effect does not re-bind (and briefly drop the client) on
  // every session-list identity change. A dropped binding makes the "+" CLI
  // rows toast and return without opening a terminal.
  const openItemFromExternalRef = useRef(openItemFromExternal)
  openItemFromExternalRef.current = openItemFromExternal
  const reloadSessionsForExternalRef = useRef(reloadSessionsForExternal)
  reloadSessionsForExternalRef.current = reloadSessionsForExternal
  const setSessionsForExternalRef = useRef(setSessionsForExternal)
  setSessionsForExternalRef.current = setSessionsForExternal
  useEffect(() => {
    if (!externalClient) {
      useExternalAgentActions.getState().bind(null)
      return
    }
    useExternalAgentActions.getState().bind({
      client: externalClient,
      openItem: id => openItemFromExternalRef.current(id),
      upsertSession: session =>
        setSessionsForExternalRef.current(current =>
          current.some(item => item.id === session.id)
            ? current.map(item => (item.id === session.id ? session : item))
            : [session, ...current]
        ),
      reloadSessions: () => reloadSessionsForExternalRef.current({ force: true })
    })
    void refreshInstalledAgents(externalClient)
    return () => useExternalAgentActions.getState().bind(null)
  }, [externalClient])
  const tabGroupsStore = useAppTabGroups(
    ui.projectScopeId,
    bootstrap.sessions,
    ui.allTabGroups,
    ui.setAllTabGroups,
    tabs.setOpenTabIds
  )

  // Groups are "virtual tabs": when the route points to a group, the
  // shell uses its active child chat for all per-session concerns, then
  // AgentSessionMainPanel decides whether to render split view or
  // single-tab.
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
  // What the strip renders as active — el id del chip resaltado en el
  // strip (chat, terminal o grupo).
  //
  // FAS-107 X5.1: consolidado en `resolveStripActiveId`. Antes esto era
  // `route.sessionId ?? route.terminalId ?? null` inline en varios
  // sitios y era fácil olvidarse de un tipo (hotfix `8f38fa9` corrigió
  // uno de esos olvidos). Ahora la lógica vive en un solo lugar; si en
  // el futuro agregamos un tipo nuevo (`note`, `canvas`, `mcp`), se
  // toca `lib/strip-active.ts` y punto.
  const stripSessionId = resolveStripActiveId(
    { sessionId: route.sessionId, terminalId: route.terminalId },
    null
  )

  // Stable membership check for session effects. Was an inline arrow
  // that changed identity every render, which re-fired
  // `useAppSessionEffects`' auto-open effect on every keystroke and
  // sometimes re-added a tab in the same batch it was being closed.
  const chatIsInsideAnyGroupMemo = useCallback(
    (chatId: string) =>
      tabGroupsStore.allTabGroups.some(g => g.itemIds.includes(chatId)),
    [tabGroupsStore.allTabGroups]
  )

  /*
   * Hydrate the group chip into the strip when the user navigates to
   * `/agents/grp_xxx` (fresh route, sidebar click, reload). Depends
   * ONLY on `route.sessionId` — never on `activeGroup`, because
   * mutating `allTabGroups` (pin toggle, rename, addToGroup, activeChat
   * change) rebuilds the `activeGroup` reference and the old effect
   * fired on every such mutation, racing `closeSessionTab` and
   * silently re-adding the group chip the user just closed.
   *
   * Reading `allTabGroups` through a ref keeps the guard "does this
   * group still exist" without pulling the whole store into the effect
   * dependencies (which would defeat the whole point).
   */
  const allTabGroupsRef = useRef(tabGroupsStore.allTabGroups)
  allTabGroupsRef.current = tabGroupsStore.allTabGroups
  useEffect(() => {
    const id = route.sessionId
    if (!id || !id.startsWith('grp_')) return
    const exists = allTabGroupsRef.current.some(g => g.id === id)
    if (!exists) return
    tabs.openSessionTab(id)
  }, [route.sessionId, tabs.openSessionTab])

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
    stripSessionId,
    enableTranscriptStream: !activeGroup,
    subscribeActiveChat: !activeGroup,
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
    openTabIds: tabs.openTabIds,
    setOpenTabIds: tabs.setOpenTabIds,
    tabGroups: tabGroupsStore.allTabGroups,
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
  const [capySessionId, setCapySessionId] = React.useState<string | null>(null)

  // Multi-select for split view: any Shift/Meta click on a tab, a
  // sidebar chat or a dropdown item adds/removes that chatId here.
  // When 2+ chats are selected, an action bar appears that creates
  // the group with all of them.
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
  /**
   * FAS-107 X4.4-hotfix (bug D): entrar a un grupo suelta el pin
   * individual del item. Rationale: al pinear un chat/terminal, el user
   * pinea ese ítem específico. Al meterlo a un grupo pasa a ser hijo de
   * otra entidad, y el pin del grupo (si se activa) es lo que ordena.
   * Mantener el pin viejo genera confusión (aparece pineado dentro del
   * grupo Y como suelto al disolver).
   */
  const unpinItemIfPinned = useCallback(
    async (id: string) => {
      if (!bootstrap.client) return
      try {
        if (id.startsWith('term_')) {
          const term = terminalsLive.terminals.find(t => t.id === id)
          if (term?.organizeLabel !== 'pinned') return
          await bootstrap.client.updateTerminal(id, { organizeLabel: '' })
          useTerminalsStore.getState().patch(id, { organizeLabel: null })
        } else {
          const chat = bootstrap.sessions.find(s => s.id === id)
          if (chat?.organizeLabel !== 'pinned') return
          await bootstrap.client.updateSession(id, { organizeLabel: null })
          bootstrap.setSessions(current =>
            current.map(s =>
              s.id === id ? { ...s, organizeLabel: null } : s
            )
          )
        }
      } catch (err) {
        console.error('unpinItemIfPinned failed', err)
      }
    },
    [bootstrap, terminalsLive.terminals]
  )

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
      // X4.4-hotfix bug D: despinar ítems al confirmar el split.
      for (const id of chatIds) void unpinItemIfPinned(id)
      return groupId
    },
    [tabGroupsStore, bootstrap, unpinItemIfPinned]
  )

  useEffect(() => {
    if (!bootstrap.health || bootstrap.sessions.length === 0) return
    const missed = recoverUnreadFromSessions(
      bootstrap.sessions,
      effectiveSessionId
    )
    if (missed.length > 0) notifyMissedCompletions(missed.length)
  }, [bootstrap.health, bootstrap.sessions, effectiveSessionId])

  // Unread ids are persisted; forget the ones whose chat no longer exists so
  // the Bell / Dock badge can actually go dark (FAS-120). Only when the list
  // is unscoped — a project scope hides other projects' chats.
  const sessionsScopeForPrune = ui.projectScopeId
  useEffect(() => {
    if (!bootstrap.health || sessionsScopeForPrune || bootstrap.sessions.length === 0) return
    pruneSessionAttention(bootstrap.sessions.map(s => s.id))
  }, [bootstrap.health, bootstrap.sessions, sessionsScopeForPrune])

  useGlobalSessionEvents({
    client: bootstrap.client,
    health: bootstrap.health,
    sessionIdRef: ui.sessionIdRef,
    setSessions: bootstrap.setSessions,
    onUiCommand: payload => {
      if (payload.action === 'open_item') {
        // Capy launched a CLI terminal or imported a chat server-side;
        // bring it into the strip and route to it.
        const itemId =
          typeof payload.itemId === 'string' ? payload.itemId : null
        if (!itemId) return
        const isTerminal = itemId.startsWith('term_')
        const ready = isTerminal
          ? (() => {
              const seen = useTerminalsStore.getState().revision
              return externalClient?.listTerminals().then(list => {
                useTerminalsStore.getState().setAll(list, seen)
              })
            })()
          : bootstrap.loadSessions({ force: true })
        void Promise.resolve(ready).then(() => openItemFromExternal(itemId))
        return
      }
      if (payload.action !== 'open_split') return
      const ids = Array.isArray(payload.sessionIds)
        ? payload.sessionIds.filter((id): id is string => typeof id === 'string')
        : []
      // Optional `layout: { rows, cols }` (POST /v1/ui/commands, dev-grid
      // script, e2e harness) — otherwise the default single row.
      const layout = parseGridLayout(payload.layout)
      void bootstrap.loadSessions({ force: true }).then(() => {
        const groupId = applyCapyOpenSplit(ids, createSplitGroup, path =>
          navigate(path)
        )
        if (groupId && layout) {
          tabGroupsStore.setGroupLayoutForMonitor(
            groupId,
            getMonitorFingerprint(),
            buildGridTree(ids, layout.rows, layout.cols)
          )
        }
      })
    }
  })
  useEventsMux({
    client: bootstrap.client,
    health: bootstrap.health,
    pinnedSessionIds: [
      ...(activeGroup?.itemIds ?? []),
      ...(capySessionId ? [capySessionId] : [])
    ]
  })

  const createSplitFromSelection = useCallback(() => {
    const ids = Array.from(selectedChatIds).filter(
      id => !id.startsWith('grp_')
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
   * `ChatTilingContainer` pinta el chat A en el panel izquierdo y el
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

  const handleSplitPane = useCallback(
    (sourceId: string, direction: PaneSplitDirection, target: PaneSplitTarget) => {
      void (async () => {
        const source = isDraftAgentSessionId(sourceId)
          ? await layer.actions.ensureAgentSession(undefined, { navigate: false })
          : sourceId
        if (!source) return
        const projectId =
          bootstrap.sessions.find(item => item.id === source)?.projectId ??
          context.activeProjectId
        let partnerId: string
        if (target === 'agent') {
          const created = await bootstrap.client.createSession({
            title: 'New Agent',
            projectId,
            clientSurface: 'ui'
          })
          bootstrap.setSessions(current =>
            current.some(item => item.id === created.id)
              ? current
              : [created, ...current]
          )
          partnerId = created.id
        } else {
          const preset = cliHarnessPreset(target)
          const term = await bootstrap.client.createTerminal({
            title: preset?.title ?? 'Terminal',
            projectId
          })
          useTerminalsStore.getState().addOptimistic(term)
          if (preset) queueTerminalStartup(term.id, preset.command)
          partnerId = term.id
        }
        const existing = tabGroupsStore.allTabGroups.find(
          group => !group.isPending && group.itemIds.includes(source)
        )
        const fingerprint = getMonitorFingerprint()
        const sourceLeaf = source.startsWith('term_')
          ? { type: 'terminal' as const, terminalId: source }
          : { type: 'chat' as const, chatId: source }
        if (existing) {
          const base =
            existing.layout?.perMonitor?.[fingerprint] ??
            buildGridTree(existing.itemIds, 1, Math.max(1, existing.itemIds.length))
          tabGroupsStore.addToGroup(existing.id, partnerId)
          tabGroupsStore.setGroupLayoutForMonitor(
            existing.id,
            fingerprint,
            splitPane(base, source, direction, partnerId, 'after')
          )
          navigate(`/agents/${existing.id}`)
          return
        }
        const groupId = tabGroupsStore.createGroup([source, partnerId])
        if (!groupId) return
        tabGroupsStore.setGroupLayoutForMonitor(
          groupId,
          fingerprint,
          splitPane(sourceLeaf, source, direction, partnerId, 'after')
        )
        navigate(`/agents/${groupId}`)
      })().catch(err => console.error('split pane failed', err))
    },
    [
      bootstrap,
      context.activeProjectId,
      layer.actions,
      navigate,
      tabGroupsStore
    ]
  )

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const meta = event.metaKey || event.ctrlKey
      if (!meta || event.altKey || event.key.toLowerCase() !== 'd') return
      const active = document.activeElement
      if (
        active instanceof HTMLElement &&
        active.closest(
          '.xterm, input, textarea, select, [contenteditable="true"]'
        )
      ) {
        return
      }
      const source =
        route.terminalId ??
        (activeGroup ? activeGroup.activeChatId : route.sessionId)
      if (!source) return
      event.preventDefault()
      handleSplitPane(
        source,
        event.shiftKey ? 'vertical' : 'horizontal',
        source.startsWith('term_') ? 'terminal' : 'agent'
      )
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [activeGroup, handleSplitPane, route.sessionId, route.terminalId])

  const handlePickSplitPartner = useCallback(
    (partnerId: string) => {
      const groupId = route.sessionId
      if (!groupId || !groupId.startsWith('grp_')) return
      const group = tabGroupsStore.allTabGroups.find(g => g.id === groupId)
      if (!group || !group.isPending) return
      const sourceId = group.itemIds[0]
      if (sourceId === partnerId) return
      // Boost the partner's date as if the split had been created with
      // both chats from the start — this way the incoming chat also
      // bubbles up to Today (same behavior as createSplitGroup).
      const now = new Date().toISOString()
      setChatDateBoosts([partnerId], now)
      bootstrap.setSessions(current =>
        current.map(s =>
          s.id === partnerId ? { ...s, lastMessageAt: now } : s
        )
      )
      tabGroupsStore.promotePendingGroup(groupId, partnerId)
      // X4.4-hotfix bug D: al confirmar el split, despinar ambos ítems.
      // El sourceId estaba dentro del pending group (efímero, sin
      // despinar) y ahora se confirma junto con el partner.
      void unpinItemIfPinned(sourceId)
      void unpinItemIfPinned(partnerId)
    },
    [route.sessionId, tabGroupsStore, bootstrap, unpinItemIfPinned]
  )

  const handleCancelPendingSplit = useCallback(() => {
    const groupId = route.sessionId
    if (!groupId || !groupId.startsWith('grp_')) return
    const group = tabGroupsStore.allTabGroups.find(g => g.id === groupId)
    if (!group || !group.isPending) return
    const sourceId = group.itemIds[0]
    tabGroupsStore.dissolveGroup(groupId)
    if (sourceId) navigate(sessionRoutePath(sourceId))
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
  /*
   * FAS-107 X4.4: sacar un terminal del split desde el sidebar SIN
   * borrarlo del disco. Antes el sidebar mostraba "Delete" que llamaba
   * `handleDeleteTerminalGlobal` (destructivo real), asimetría vs los
   * chats que sí distinguían "Remove from split" del delete real.
   *
   * Busca en qué grupo vive el terminal (a diferencia de
   * `handleRemoveChatFromSplit`, que depende de `route.sessionId` porque
   * se dispara desde dentro del split activo — este handler puede
   * dispararse desde el sidebar viendo cualquier grupo).
   */
  const handleRemoveTerminalFromSplit = useCallback(
    (terminalId: string) => {
      const group = tabGroupsStore.allTabGroups.find(g =>
        g.itemIds.includes(terminalId)
      )
      if (!group) return
      const survivor = group.itemIds.find(id => id !== terminalId) ?? null
      const nextSize = tabGroupsStore.removeFromGroup(group.id, terminalId)
      if (nextSize >= 0 && nextSize < 2) {
        tabGroupsStore.dissolveGroup(group.id)
        if (survivor) {
          openSessionTabRef.current?.(survivor)
          // Solo navegar si el user estaba viendo ese grupo específicamente.
          if (route.sessionId === group.id) {
            navigate(sessionRoutePath(survivor))
          }
        }
      }
      // El terminal survivor (o el terminal que se quita si el grupo
      // tenía >2) ya queda en openTabIds via `removeFromGroup`. NO se
      // llama `deleteTerminal` — el terminal sigue vivo.
      openSessionTabRef.current?.(terminalId)
    },
    [route.sessionId, tabGroupsStore, navigate]
  )

  const handleRemoveChatFromSplit = useCallback(
    (chatId: string) => {
      const groupId = route.sessionId
      if (!groupId || !groupId.startsWith('grp_')) return
      const group = tabGroupsStore.allTabGroups.find(g => g.id === groupId)
      if (!group) return
      const survivor = group.itemIds.find(id => id !== chatId) ?? null
      const nextSize = tabGroupsStore.removeFromGroup(groupId, chatId)
      if (nextSize >= 0 && nextSize < 2) {
        tabGroupsStore.dissolveGroup(groupId)
        if (survivor) {
          // FAS-107 X3 Fase 2: garantizar que el survivor esté en
          // openTabIds antes de navegar. `dissolveGroup` re-inserta
          // solo los "nativos" del scope (chats con projectId matching),
          // y los terminales quedan afuera porque su mapa de projectId
          // vive en otro store. Llamarlo acá cubre ambos tipos.
          openSessionTabRef.current?.(survivor)
          navigate(sessionRoutePath(survivor))
        }
      }
    },
    [route.sessionId, tabGroupsStore, navigate]
  )

  /*
   * X1: "Delete Split View" desde el menú del chip del strip o del sidebar.
   * Antes esto llamaba `tabGroupsStore.dissolveGroup` directo — el grupo
   * desaparecía pero la ruta seguía en `/agents/grp_xxx`, quedando en
   * pantalla vacía porque el id ya no existía.
   *
   * Ahora: tomamos el `activeChatId` del grupo (lo que el user tenía en
   * foco dentro del split) ANTES de disolver, corremos el dissolve, y si
   * la ruta actual apuntaba a ese mismo grupo, navegamos al ítem activo
   * como tab suelto — a `/agents/:id` si es chat, a `/terminals/:id` si
   * empieza con `term_`. El user sigue viendo la misma cosa, solo que
   * ya no adentro del split.
   */
  const handleDissolveTabGroup = useCallback(
    (groupId: string) => {
      const group = tabGroupsStore.allTabGroups.find(g => g.id === groupId)
      const activeChild = group?.activeChatId ?? group?.itemIds[0] ?? null
      const wasViewingThisGroup = route.sessionId === groupId
      tabGroupsStore.dissolveGroup(groupId)
      if (wasViewingThisGroup && activeChild) {
        // FAS-107 X3 Fase 2: mismo motivo que en handleRemoveChatFromSplit.
        openSessionTabRef.current?.(activeChild)
        navigate(sessionRoutePath(activeChild))
      }
    },
    [route.sessionId, tabGroupsStore, navigate]
  )

  const handleAddChatToSplit = useCallback(
    (chatId: string) => {
      const groupId = route.sessionId
      if (!groupId || !groupId.startsWith('grp_')) return
      const group = tabGroupsStore.allTabGroups.find(g => g.id === groupId)
      if (!group || group.isPending) return
      if (group.itemIds.includes(chatId)) return
      const now = new Date().toISOString()
      setChatDateBoosts([chatId], now)
      bootstrap.setSessions(current =>
        current.map(s =>
          s.id === chatId ? { ...s, lastMessageAt: now } : s
        )
      )
      tabGroupsStore.addToGroup(groupId, chatId)
      tabGroupsStore.setGroupActiveChat(groupId, chatId)
      // X4.4-hotfix bug D: al agregar un item a un split existente,
      // despinar el ítem (mismo criterio que crear split).
      void unpinItemIfPinned(chatId)
    },
    [route.sessionId, tabGroupsStore, bootstrap, unpinItemIfPinned]
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

  // Dialog state for "Rename split view". Analogous to `renameTarget`
  // for chats: `target` holds the group whose name is being edited;
  // `value` is the controlled input. `submitRenameGroup` calls the
  // store when the trimmed value isn't empty. Only validation is "not
  // empty".
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

  // Common args that every split-view `SessionChatMount` combines with
  // its own chatId + session. Computed once so secondary mounts within
  // a group can boot their pipeline with the same shared handles the
  // active mount uses.
  // Panes read the sessions list by ref (see usePerSessionChatState) so
  // a row update in one chat doesn't re-render every other pane.
  const sessionsRef = useLatestRef(bootstrap.sessions)
  const tabGroupsRef = useLatestRef(tabGroupsStore.allTabGroups)
  const perSessionBaseArgs = useMemo(
    () => ({
      client: bootstrap.client,
      health: bootstrap.health,
      navigate,
      activeProjectId: context.activeProjectId,
      activeProject: context.activeProject,
      tabsScopeKey: tabs.tabsScopeKey,
      sessionsRef,
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
      setLastSessionByScope: ui.setLastSessionByScope,
      setProjectScopeId: ui.setProjectScopeId,
      setRecentProjectIds: ui.setRecentProjectIds,
      patchOpenTabs: tabs.patchOpenTabs,
      openTabIds: tabs.openTabIds,
      setOpenTabIds: tabs.setOpenTabIds,
      tabGroupsRef,
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
      sessionsRef,
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
      ui.setLastSessionByScope,
      ui.setProjectScopeId,
      ui.setRecentProjectIds,
      tabs.patchOpenTabs,
      tabs.openTabIds,
      tabs.setOpenTabIds,
      tabGroupsRef,
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
  // FAS-107 · Fix pre-fase1: expone el ítem con foco visible a módulos
  // sin acceso al store (p. ej. `TerminalPortalHost` — vive en un layer
  // portal aparte y no puede consultar tab groups). Cuando el usuario
  // está en un split, `effectiveSessionId` YA es el `activeChatId` del
  // group; si no, es la ruta directa.
  setFocusedItemId(effectiveSessionId ?? null)
  // FAS-107 · Fase 1f: bridge global para "abrir un ítem por id" desde
  // el handler de click de notif nativas macOS (y cualquier otro
  // módulo fuera del árbol React). El resolver decide si es standalone
  // (navegar directo) o hijo de split (navegar al group + setear
  // activeChatId del pane, así el chat/terminal queda visible dentro
  // del split de una).
  useEffect(() => {
    setItemOpener((itemId: string) => {
      const location = resolveItemLocation(itemId, allTabGroupsRef.current)
      if (location.kind === 'split-child') {
        tabGroupsStore.setGroupActiveChat(
          location.groupId,
          location.activeChatId
        )
      }
      navigate(location.routePath)
    })
    return () => {
      setItemOpener(null)
    }
  }, [navigate, tabGroupsStore.setGroupActiveChat])

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
    isDashboardLogs: route.isDashboardLogs,
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
    chatIsInsideAnyGroup: chatIsInsideAnyGroupMemo,
    tabGroups: tabGroupsStore.allTabGroups,
    terminals: terminalsLive.terminals,
    sessionsInitialLoadDone: bootstrap.sessionsInitialLoadDone
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
   * grupo — el grupo es la única representación válida. Antes teníamos
   * una excepción para el chat activo pero eso causaba render duplicado
   * (chat suelto + chat como children del grupo → React keys duplicadas
   * → todo el estado del sidebar/strip se rompía).
   */
  const chatsInsideGroupIds = useMemo(() => {
    const set = new Set<string>()
    for (const g of tabGroupsStore.allTabGroups) {
      for (const id of g.itemIds) set.add(id)
    }
    return set
  }, [tabGroupsStore.allTabGroups])
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

  // Memoized: App re-renders on every streamed token (chat store lives in
  // a root context), and this walks every session. Stable identities here
  // also let the sidebar list and tab strip skip re-rendering per token.
  const sidebarModelSessions = bootstrap.sessions
  const sidebarModelGroups = tabGroupsStore.allTabGroups
  const sidebarModelProjectId = context.activeProjectId
  const sidebarModelActiveId = route.sessionId
  const sidebarModelTerminals = terminalsLive.terminals
  // Sidebar sections do not depend on which chat is open. Building them
  // apart from the tab strip keeps their identity across a click, so the
  // memoized list and every group row stay mounted instead of flashing.
  const { sections } = useMemo(
    () =>
      buildSessionSidebarModel({
        sessions: sidebarModelSessions,
        tabGroups: sidebarModelGroups,
        activeProjectId: sidebarModelProjectId,
        openTabIds: EMPTY_TAB_IDS,
        terminals: sidebarModelTerminals
      }),
    [
      sidebarModelSessions,
      sidebarModelGroups,
      sidebarModelProjectId,
      sidebarModelTerminals
    ]
  )
  const { openTabs } = useMemo(
    () =>
      buildSessionSidebarModel({
        sessions: sidebarModelSessions,
        // Pass ALL groups (across every scope) so the model can resolve a
        // `grp_xxx` even when the active project doesn't match the scope
        // the group was created in. `buildSessionSidebarModel` filters
        // internally by scope, but it can still recognize a cross-scope
        // group in `openTabIds`.
        tabGroups: sidebarModelGroups,
        activeProjectId: sidebarModelProjectId,
        openTabIds: cleanedOpenTabIds,
        activeSessionId: sidebarModelActiveId,
        terminals: sidebarModelTerminals
      }),
    [
      sidebarModelSessions,
      sidebarModelGroups,
      sidebarModelProjectId,
      cleanedOpenTabIds,
      sidebarModelActiveId,
      sidebarModelTerminals
    ]
  )
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
    isDashboardLogs: route.isDashboardLogs,
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

  if (isAboutDesktopWindow() || location.pathname === '/about') {
    return <AboutUpdateWindow />
  }

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
      <div className="flex h-full w-full flex-col">
        <div className="min-h-0 flex-1">{gate}</div>
        <OfflineBanner
          isOffline={offlineStatus.isOffline}
          justOnline={offlineStatus.justOnline}
          message={offlineStatus.message}
          featuresAffected={offlineStatus.featuresAffected}
        />
        {remoteDialog}
      </div>
    )
  }

  return (
    <>
      <AppShellConnected
        terminals={terminalsLive.terminals}
        onCloseTerminal={handleDeleteTerminalGlobal}
        onRemoveTerminalFromSplit={handleRemoveTerminalFromSplit}
        activeTerminalId={route.terminalId ?? null}
        onMoveTerminalToProject={handleMoveTerminalToProject}
        onRenameTerminal={promptRenameTerminal}
        onToggleTerminalOrganizeLabel={handleToggleTerminalOrganizeLabel}
        {...buildAppShellProps({
          offlineStatus,
          ui,
          route,
          bootstrap,
          context,
          chat: layer.chat,
          activityBySessionId,
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
          onSplitPane: handleSplitPane,
          onPickSplitPartner: handlePickSplitPartner,
          onCancelPendingSplit: handleCancelPendingSplit,
          onAddChatToSplit: handleAddChatToSplit,
          onRemoveChatFromSplit: handleRemoveChatFromSplit,
          closeTabGroup: handleCloseTabGroup,
          dissolveTabGroup: handleDissolveTabGroup,
          renameGroupTarget,
          renameGroupValue,
          setRenameGroupTarget,
          setRenameGroupValue,
          submitRenameGroup,
          renameTerminalTarget,
          renameTerminalValue,
          setRenameTerminalTarget,
          setRenameTerminalValue,
          submitRenameTerminal,
          selectedChatIds,
          toggleSelectChat,
          clearSelectChats,
          createSplitFromSelection,
          createSplitFromSidebar: () => {
            const ids = Array.from(layer.actions.selectedSessionIds).filter(
              id => !id.startsWith('grp_')
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
              id => !id.startsWith('grp_')
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
      <CapyOverlay
        client={bootstrap.client}
        health={bootstrap.health}
        chats={bootstrap.sessions}
        skills={bootstrap.skills}
        mcpServers={bootstrap.mcpServers}
        modelOptions={bootstrap.modelOptions}
        runtimeSettings={bootstrap.runtimeSettings}
        setRuntimeSettings={bootstrap.setRuntimeSettings}
        loadModelOptions={bootstrap.loadModelOptions}
        onSessionId={setCapySessionId}
        activeProjectId={context.activeProjectId}
        activeChatId={effectiveSessionId}
      />
      <PaneContextMenu />
    </>
  )
}
