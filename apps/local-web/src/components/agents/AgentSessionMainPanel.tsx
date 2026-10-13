import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentMessage,
  AgentProject,
  AgentSession,
  SessionGroup
} from '@sandwalk/agent-ui-core'
import {
  type ComponentProps,
  type Dispatch,
  type RefObject,
  type SetStateAction,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState
} from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import { matchPath, type NavigateFunction,useLocation } from 'react-router-dom'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'
import { ChatTilingContainer } from '@/components/agents/ChatTilingContainer'
import { fileChipToken } from '@/components/agents/composer-parts'
import { useSessionSiteAutoPreview } from '@/components/agents/sites/use-session-site-auto-preview'
import { TerminalPlaceholder } from '@/components/agents/terminal-layer'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { WorkspacePanel } from '@/components/agents/WorkspacePanel'
import { SandwalkMark } from '@/components/SandwalkMark'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import { Sheet, SheetContent } from '@/components/ui/sheet'
import { useAppTerminals } from '@/hooks/useAppTerminals'
import { buildGridTree } from '@/hooks/useChatTiling'
import { useIsNarrowWindow } from '@/hooks/useIsNarrowWindow'
import type { PerSessionChatStateArgs } from '@/hooks/usePerSessionChatState'
import { useStableHandlers } from '@/hooks/useStableHandlers'
import {
  dropUnbalancedPanelLayouts,
  SESSION_PANELS_AUTO_SAVE_ID
} from '@/lib/app-storage'
import { isBlankCanvasSessionId, isDraftAgentSessionId } from '@/lib/draft-agent'
import { getMonitorFingerprint } from '@/lib/monitor-fingerprint'
import type { PaneSplitDirection, PaneSplitTarget } from '@/lib/pane-split'
import { perfCount } from '@/lib/perf-probe'
import { planCardFromPath, startPlanBuild } from '@/lib/plan-build'
import { type SessionChatState } from '@/lib/sessions'
import { clearTerminalActivity } from '@/lib/terminal-attention'
import { cn } from '@/lib/utils'

import {
  EmptyStartActions,
  EmptyStartTip,
  openPlusMenu,
  requestPlanMode
} from './empty-start'
import { SessionChatBody } from './session-main/session-chat-body'
import { SessionMainHeader } from './session-main/session-main-header'

export type AgentSessionMainPanelProps = {
  client: LocalAgentClient
  navigate: NavigateFunction
  sidebarCollapsed: boolean
  setSidebarCollapsed: Dispatch<SetStateAction<boolean>>
  openTabs: import('@/lib/sessions').TabItem[]
  openTabIds: string[]
  sessionId: string | null
  session: AgentSession | null
  openSessionTab: (sessionId: string) => void
  prefetchSessionMessages: (sessionId: string) => void | Promise<void>
  closeSessionTab: (sessionId: string) => void
  closeOtherSessionTabs: (sessionId: string) => void
  reorderSessionTabs: (orderedIds: string[]) => void
  openRenameDialog: (target: AgentSession) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  exportTranscript: (target: AgentSession) => void | Promise<void>
  setDeleteTarget: Dispatch<SetStateAction<AgentSession | null>>
  projects: AgentProject[]
  selectProjectScope: (projectId: string) => void
  cliMenuOpen: boolean
  setCliMenuOpen: Dispatch<SetStateAction<boolean>>
  copiedResumeCommand: boolean
  setCopiedResumeCommand: Dispatch<SetStateAction<boolean>>
  terminalOpen: boolean
  setTerminalOpen: Dispatch<SetStateAction<boolean>>
  filesPanelCollapsed: boolean
  setFilesPanelCollapsed: Dispatch<SetStateAction<boolean>>
  isInspect: boolean
  messages: AgentMessage[]
  tools: TranscriptTool[]
  messagesLoaded: boolean
  runActive: boolean
  showChatSkeleton: boolean
  agentComposerSlotProps: ComponentProps<typeof AgentComposerSlot>
  recentProjectIds: string[]
  activeProjectId: string | null
  onNewProject: () => void
  selectAllProjects: () => void
  chatScrollRef: RefObject<HTMLDivElement | null>
  chatEndRef: RefObject<HTMLDivElement | null>
  conversationTimeline: TranscriptEntry[]
  expandedToolRunKeys: Record<string, boolean>
  patchChat: (
    sessionId: string,
    updater: (prev: SessionChatState) => SessionChatState
  ) => void
  runIdByMessageId: Record<string, string>
  usageByRunId: Record<string, { inputTokens: number; outputTokens: number }>
  copiedMessageId: string | null
  setCopiedMessageId: Dispatch<SetStateAction<string | null>>
  activeRunTools: TranscriptTool[]
  activeRunTodos: import('@sandwalk/agent-ui-core').AgentTodo[]
  activeBuildPlan: import('@sandwalk/agent-ui-core').AgentPlanCard | null
  builtPlanPaths: string[]
  liveDelta: string
  pendingApproval: import('@sandwalk/agent-ui-core').PendingHitlApproval | null
  approvalSubmitting: boolean
  onSubmitApprovals: (
    decisions: import('@sandwalk/agent-ui-core').HitlDecision[]
  ) => void | Promise<void>
  showScrollToBottom: boolean
  scrollChatToBottom: () => void
  error: string | null
  canShowFilesPanel: boolean
  filesPanelRef: RefObject<ImperativePanelHandle | null>
  workspaceVersion: number
  draftWorkspaceSessionId: string | null
  setDraftWorkspaceSessionId: Dispatch<SetStateAction<string | null>>
  pendingOpenPath: string | null
  setPendingOpenPath: Dispatch<SetStateAction<string | null>>
  setComposer: (value: string | ((current: string) => string)) => void
  setComposerFiles: (
    value: string[] | ((current: string[]) => string[])
  ) => void
  /** Opens a draft session (draft only, not persisted). */
  createSession?: (projectId?: string | null) => void | Promise<void>
  activeGroup: SessionGroup | null
  perSessionBaseArgs: Omit<
    PerSessionChatStateArgs,
    'sessionId' | 'session' | 'sessionIdRef'
  >
  allSessions: AgentSession[]
  setTabGroupActiveChat: (groupId: string, chatId: string) => void
  setTabGroupLayoutForMonitor: (
    groupId: string,
    fingerprint: string,
    tree: import('@sandwalk/agent-ui-core').PaneNode
  ) => void
  tabGroups: SessionGroup[]
  onSplitWithNextTab: (sourceId: string) => void
  onSplitPane?: (
    sourceId: string,
    direction: PaneSplitDirection,
    target: PaneSplitTarget
  ) => void
  onPickSplitPartner: (partnerId: string) => void
  onCancelPendingSplit: () => void
  onAddChatToSplit: (chatId: string) => void
  onRemoveChatFromSplit: (chatId: string) => void
  /** X2 Fix 1: dispatcher del rename dialog del shell. El strip y el
   *  ChatTilingContainer lo llaman en vez de un `window.prompt` local. */
  promptRenameTerminal: (terminalId: string) => void
  /** X3 Fase 3: handlers del shell (fuente única). Antes había copias
   *  locales que hacían casi lo mismo pero con divergencias sutiles
   *  (por ejemplo el close local llamaba `onRemoveChatFromSplit`
   *  además de `deleteTerminal`, produciendo doble efecto). */
  deleteTerminalPermanently: (terminalId: string) => Promise<void>
  toggleTerminalOrganizeLabel: (
    terminalId: string,
    label: 'pinned' | 'archive'
  ) => Promise<void>
  moveTerminalToProject: (
    terminalId: string,
    projectId: string | null
  ) => Promise<void>
  dissolveTabGroup: (groupId: string) => void
  renameTabGroup: (group: SessionGroup) => void
  setTabGroupColor: (groupId: string, color: string | null) => void
  /** X4.2b: pin/unpin del grupo. */
  setTabGroupPinned: (groupId: string, pinned: boolean) => void
  closeTabGroup: (groupId: string) => void
  selectedChatIds: Set<string>
  toggleSelectChat: (id: string) => void
  clearSelectChats: () => void
  createSplitFromSelection: () => void
}

export function AgentSessionMainPanel(props: AgentSessionMainPanelProps) {
  perfCount('render.AgentSessionMainPanel')
  const location = useLocation()
  // FAS-107 GF3: detect `/terminals/:id` here (rather than prop-drilling
  // from App.tsx) since the shell already reads `location`. When present,
  // the main pane renders TerminalPanel instead of chat/split.
  const terminalRouteMatch = matchPath(
    '/terminals/:terminalId',
    location.pathname
  )
  const terminalId =
    terminalRouteMatch?.params.terminalId?.startsWith('term_')
      ? terminalRouteMatch.params.terminalId
      : null
  // FAS-107 GF9: clear activity dot when the terminal becomes the active
  // pane. New output only counts as "unseen" while it lives elsewhere.
  useEffect(() => {
    if (terminalId) clearTerminalActivity(terminalId)
  }, [terminalId])
  const {
    client,
    navigate,
    sidebarCollapsed,
    setSidebarCollapsed,
    openTabs,
    openTabIds,
    sessionId,
    session,
    openSessionTab,
    prefetchSessionMessages,
    closeSessionTab,
    closeOtherSessionTabs,
    reorderSessionTabs,
    openRenameDialog,
    updateSession,
    exportTranscript,
    setDeleteTarget,
    projects,
    selectProjectScope,
    cliMenuOpen,
    setCliMenuOpen,
    copiedResumeCommand,
    setCopiedResumeCommand,
    terminalOpen,
    setTerminalOpen,
    filesPanelCollapsed,
    setFilesPanelCollapsed,
    isInspect,
    messages,
    tools,
    messagesLoaded,
    runActive,
    showChatSkeleton,
    agentComposerSlotProps,
    recentProjectIds,
    activeProjectId,
    onNewProject,
    selectAllProjects,
    chatScrollRef,
    chatEndRef,
    conversationTimeline,
    expandedToolRunKeys,
    patchChat,
    runIdByMessageId,
    usageByRunId,
    copiedMessageId,
    setCopiedMessageId,
    activeRunTools,
    activeRunTodos,
    activeBuildPlan,
    builtPlanPaths,
    liveDelta,
    pendingApproval,
    approvalSubmitting,
    onSubmitApprovals,
    showScrollToBottom,
    scrollChatToBottom,
    error,
    canShowFilesPanel,
    filesPanelRef,
    workspaceVersion,
    draftWorkspaceSessionId,
    setDraftWorkspaceSessionId,
    pendingOpenPath,
    setPendingOpenPath,
    setComposer,
    setComposerFiles,
    activeGroup,
    perSessionBaseArgs,
    allSessions,
    setTabGroupActiveChat,
    setTabGroupLayoutForMonitor,
    tabGroups,
    onSplitWithNextTab,
    onSplitPane,
    onPickSplitPartner,
    onCancelPendingSplit,
    onAddChatToSplit,
    onRemoveChatFromSplit,
    promptRenameTerminal,
    deleteTerminalPermanently,
    toggleTerminalOrganizeLabel,
    moveTerminalToProject,
    dissolveTabGroup,
    renameTabGroup,
    setTabGroupColor,
    setTabGroupPinned,
    closeTabGroup,
    selectedChatIds,
    toggleSelectChat,
    clearSelectChats,
    createSplitFromSelection
  } = props

  // FAS-107: terminals for the active project. Used by the split
  // picker's "New terminal" card and by the tab strip (when the caller
  // decides to render terminal chips).
  const {
    terminals,
    refresh: refreshTerminals,
    addOptimistic: addTerminalOptimistic
  } = useAppTerminals(client, activeProjectId)

  /**
   * Creates a terminal and returns its id. The caller (ChatTilingContainer
   * via SplitPicker) is responsible for actually splicing the id into the
   * group — this keeps a single source of truth for the pending-vs-not
   * branching and the picker-reset side effect, both of which already
   * live in the container's `handlePicked` flow.
   *
   * Returns `null` on failure so the caller can no-op (leaves the picker
   * open for retry).
   */
  const handlePickTerminal = useCallback(async (): Promise<string | null> => {
    if (!activeGroup) return null
    try {
      const term = await client.createTerminal({
        projectId: activeProjectId,
        originChatId: activeGroup.activeChatId,
        workspacePath: session?.workspacePath ?? null
      })
      // Optimistic insert so the renderer's `terminals?.find(t => t.id
      // === chatId)` detects the new id BEFORE the background refresh
      // completes. Without this the first render after the pending group
      // promotes would fall into ChatLeaf.
      addTerminalOptimistic(term)
      refreshTerminals()
      // FAS-107 X3 Fase 2: registrar el terminal como tab abierto para
      // que sobreviva a la disolución del split. Antes NO se registraba
      // → si el user removía el otro item del split, el terminal quedaba
      // huérfano (survivor invisible en strip y sidebar).
      openSessionTab(term.id)
      return term.id
    } catch (err) {
      console.error('createTerminal failed', err)
      return null
    }
  }, [
    activeGroup,
    client,
    activeProjectId,
    session?.workspacePath,
    addTerminalOptimistic,
    refreshTerminals,
    openSessionTab
  ])

  const handlePickNewChat = useCallback(async (): Promise<string | null> => {
    if (!activeGroup) return null
    try {
      const created = await client.createSession({
        workspacePath: null,
        projectId: activeProjectId ?? null
      })
      return created.id
    } catch (err) {
      console.error('createSession failed', err)
      return null
    }
  }, [activeGroup, client, activeProjectId])

  // FAS-107 X3 Fase 3: los handlers locales se reemplazaron por
  // aliases al dispatcher del shell (fuente única). El close local
  // hacía además `onRemoveChatFromSplit` — ese cleanup ya lo cubre
  // `pruneChatFromGroups` que corre cuando el terminal desaparece del
  // store. Rename ya delegaba desde X2 Fix 1.
  const handleCloseTerminal = deleteTerminalPermanently
  const handleRenameTerminal = promptRenameTerminal
  const handleToggleTerminalOrganizeLabel = toggleTerminalOrganizeLabel
  const handleMoveTerminalToProjectLocal = moveTerminalToProject

  const isNarrow = useIsNarrowWindow(1280)
  // En split view con ventana angosta, el side panel deja de ser una columna
  // resizable (no cabe junto a N chats + composer) y pasa a modal overlay.
  const asSheet = Boolean(activeGroup) && isNarrow
  const isDraft = isDraftAgentSessionId(sessionId)
  const inProject = Boolean(activeProjectId)
  const requestedSiteId = new URLSearchParams(location.search).get('site')
  const [panelView, setPanelView] = useState<'files' | 'preview'>(() =>
    requestedSiteId ? 'preview' : 'files'
  )
  const showSitePreview = useCallback(() => {
    setPanelView('preview')
    setFilesPanelCollapsed(false)
  }, [setFilesPanelCollapsed])

  useSessionSiteAutoPreview({
    client,
    sessionId: isDraft ? null : sessionId,
    workspaceVersion,
    onSiteReady: showSitePreview
  })

  const draftReset =
    location.state &&
    typeof location.state === 'object' &&
    'draftReset' in location.state
      ? Number((location.state as { draftReset?: unknown }).draftReset)
      : 0

  useEffect(() => {
    // Reset when leaving the draft route, switching project scope, or
    // starting a fresh New Agent (same /agents/new URL).
    setDraftWorkspaceSessionId(null)
  }, [activeProjectId, draftReset, isDraft, setDraftWorkspaceSessionId])

  const prevSessionIdRef = useRef<string | null>(null)
  useLayoutEffect(() => {
    setPanelView(requestedSiteId ? 'preview' : 'files')
    if (requestedSiteId) {
      setFilesPanelCollapsed(false)
    } else if (
      isDraft &&
      prevSessionIdRef.current !== sessionId
    ) {
      // Entering New Agent (or first paint on draft): Files closed.
      setFilesPanelCollapsed(true)
    }
    prevSessionIdRef.current = sessionId
  }, [isDraft, requestedSiteId, sessionId, setFilesPanelCollapsed])

  const ensureAgentSession = agentComposerSlotProps.ensureAgentSession
  const setWorkspaceVersion = agentComposerSlotProps.setWorkspaceVersion
  const prepareDraftWorkspace = useCallback(async () => {
    if (!isDraft) return draftWorkspaceSessionId
    if (draftWorkspaceSessionId) return draftWorkspaceSessionId
    const id = await ensureAgentSession(undefined, { navigate: false })
    if (id) setDraftWorkspaceSessionId(id)
    return id
  }, [
    draftWorkspaceSessionId,
    ensureAgentSession,
    isDraft,
    setDraftWorkspaceSessionId
  ])

  // Materialize / refresh workspace index for @ mentions without opening Files.
  const ensureWorkspaceForMentions = useCallback(async () => {
    if (isDraft) {
      const id = await prepareDraftWorkspace()
      if (id) setWorkspaceVersion(current => current + 1)
      return
    }
    setWorkspaceVersion(current => current + 1)
  }, [isDraft, prepareDraftWorkspace, setWorkspaceVersion])

  // Do not auto-materialize on draft mount — that created empty
  // "New research session" rows. Files / Terminal / @ mentions opt in.

  const workspaceSessionId = isDraft ? draftWorkspaceSessionId : sessionId
  // Host terminal only when draft is outside a project.
  const showWorkspaceFiles =
    canShowFilesPanel && Boolean(workspaceSessionId) && (!isDraft || inProject)
  // The Files panel mounts after `workspaceSessionId` resolves, i.e. after
  // the collapse effect in `useAppPanelPersistence` already ran for this
  // session. Without this it paints open at `defaultSize` and only
  // collapses on the next session change — which reflows every pane in a
  // split (and refits every terminal) on the first pane click.
  const filesPanelMounted = showWorkspaceFiles && !asSheet
  // Default sizes must sum to 100 or react-resizable-panels warns.
  const filesDefaultSize =
    filesPanelMounted && !filesPanelCollapsed ? 35 : 0
  const chatDefaultSize = filesDefaultSize === 0 ? 100 : 65
  dropUnbalancedPanelLayouts(SESSION_PANELS_AUTO_SAVE_ID)
  useLayoutEffect(() => {
    if (!filesPanelMounted) return
    const panel = filesPanelRef.current
    if (!panel) return
    if (filesPanelCollapsed) {
      if (!panel.isCollapsed()) panel.collapse()
    } else if (panel.isCollapsed()) {
      panel.expand()
    }
  }, [filesPanelMounted, filesPanelCollapsed, filesPanelRef])

  // El picker vive DENTRO del ChatTilingContainer cuando el grupo activo
  // está en modo pending (recién creado desde "Create split view").
  // Ya no hay flow paralelo: el layout es el mismo del split real, sólo
  // que un panel se pinta como picker en vez de un chat mount.

  /*
   * Builders del header/mount del panel de un split. Se extraen a
   * callbacks reutilizables porque los usa tanto `ChatTilingContainer`
   * (cuando ya hay un grupo real) como el modo picker (cuando armamos
   * el layout visual del split antes de que exista el grupo). Reusarlos
   * garantiza que Chat A se vea idéntico en ambos casos (mismo header,
   * mismo composer embebido, mismos toggles smart).
   *
   * Split Down / Split Right are injected on the leaf via `onSplitPane`,
   * the same choices as the tab menu.
   */
  const buildSplitHeaderProps = useCallback(
    (chatId: string, focused: boolean, onFocusPanel: () => void) => {
      const chatSession =
        allSessions.find(item => item.id === chatId) || null
      return {
        session: chatSession,
        focused,
        onFocusPanel,
        projects,
        onSelectProjectScope: selectProjectScope,
        showFiles: Boolean(chatSession) && !isDraftAgentSessionId(chatId),
        showTerminal: false,
        showPreview: Boolean(chatSession) && !isDraftAgentSessionId(chatId),
        filesPanelCollapsed,
        terminalOpen,
        panelView,
        onToggleFiles: () => {
          const showingFilesHere =
            focused && panelView === 'files' && !filesPanelCollapsed
          if (showingFilesHere) {
            setFilesPanelCollapsed(true)
          } else {
            setPanelView('files')
            setFilesPanelCollapsed(false)
          }
        },
        onToggleTerminal: () => {
          if (focused && terminalOpen) {
            setTerminalOpen(false)
          } else {
            setTerminalOpen(true)
          }
        },
        onOpenPreview: () => {
          const showingPreviewHere =
            focused && panelView === 'preview' && !filesPanelCollapsed
          if (showingPreviewHere) {
            setFilesPanelCollapsed(true)
          } else {
            setPanelView('preview')
            setFilesPanelCollapsed(false)
          }
        },
        showCli: Boolean(chatSession) && !isDraftAgentSessionId(chatId),
        onExport: (target: AgentSession) => void exportTranscript(target),
        onRename: (target: AgentSession) => openRenameDialog(target),
        onInspect: (target: AgentSession) =>
          navigate(`/agents/${target.id}?inspect=1`),
        onArchive: (target: AgentSession) =>
          void updateSession(target, {
            organizeLabel:
              target.organizeLabel === 'archive' ? null : 'archive'
          }),
        onMoveToProject: (target: AgentSession, projectId: string | null) =>
          void updateSession(target, { projectId }),
        // "Close" desde el header de un chat dentro del split = sacar
        // ese chat del grupo (no borra). El handler auto-disuelve si
        // queda con < 2 chats.
        onRemoveFromSplit: (id: string) => onRemoveChatFromSplit(id)
      }
    },
    [
      allSessions,
      projects,
      selectProjectScope,
      filesPanelCollapsed,
      terminalOpen,
      panelView,
      setFilesPanelCollapsed,
      setTerminalOpen,
      setPanelView,
      exportTranscript,
      openRenameDialog,
      onRemoveChatFromSplit,
      navigate,
      updateSession
    ]
  )

  // Handlers arrive recreated on every shell render; pin them so the
  // memoized mounts see stable `shared` fields (see SessionChatMount).
  const sharedGlobals = useStableHandlers({
    isInspect,
    showChatSkeleton,
    projects,
    recentProjectIds,
    onNewProject,
    selectAllProjects,
    selectProjectScope,
    updateSession,
    chatScrollRef,
    chatEndRef,
    expandedToolRunKeys,
    runIdByMessageId,
    usageByRunId,
    copiedMessageId,
    setCopiedMessageId,
    liveDelta,
    showScrollToBottom,
    scrollChatToBottom,
    patchChat,
    ensureWorkspaceForMentions,
    navigate,
    client,
    error
  })
  const buildSplitMountProps = useCallback(
    (chatId: string) => {
      const chatSession =
        allSessions.find(item => item.id === chatId) || null
      return {
        perSessionArgs: {
          ...perSessionBaseArgs,
          sessionId: chatId,
          session: chatSession
        },
        shared: sharedGlobals
      }
    },
    [allSessions, perSessionBaseArgs, sharedGlobals]
  )

  if (isBlankCanvasSessionId(sessionId)) {
    return (
      <div className="relative flex h-full min-h-0 min-w-0 flex-1 flex-col items-center justify-center gap-8 px-6">
        <div className="flex w-full max-w-[44rem] flex-col items-start gap-8 px-5">
        <SandwalkMark className="text-foreground/80 h-16 w-16 self-center" />
        <EmptyStartActions
          className="justify-center"
          onPlan={() => {
            requestPlanMode(true)
            navigate('/agents/new')
          }}
          onNewAgent={() => navigate('/agents/new')}
          onTerminal={() => {
            void (async () => {
              try {
                const term = await client.createTerminal({
                  projectId: activeProjectId ?? null
                })
                addTerminalOptimistic(term)
                openSessionTab(term.id)
                navigate(`/terminals/${term.id}`)
              } catch (err) {
                console.error('createTerminal (blank) failed', err)
              }
            })()
          }}
          onSkills={() => {
            openPlusMenu('skills')
            navigate('/agents/new')
          }}
          onSandbox={() => {
            openPlusMenu('sandbox')
            navigate('/agents/new')
          }}
        />
        </div>
        <EmptyStartTip className="absolute inset-x-0 bottom-8" />
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
      {/*
        Header (tab strip + top action bar) lives OUTSIDE the horizontal
        ResizablePanelGroup so the workspace panel opens BELOW the tabs,
        letting the tabs keep their full width instead of getting squeezed.
      */}
      <SessionMainHeader
        sidebarCollapsed={sidebarCollapsed}
        setSidebarCollapsed={setSidebarCollapsed}
        openTabs={openTabs
          .filter((item): item is Extract<typeof item, { kind: 'chat' }> => item.kind === 'chat')
          .map(item => item.session)}
        openTabIds={openTabIds}
        sessionId={sessionId}
        session={session}
        navigate={navigate}
        openSessionTab={openSessionTab}
        prefetchSessionMessages={prefetchSessionMessages}
        closeSessionTab={closeSessionTab}
        closeOtherSessionTabs={closeOtherSessionTabs}
        reorderSessionTabs={reorderSessionTabs}
        openRenameDialog={openRenameDialog}
        updateSession={updateSession}
        exportTranscript={exportTranscript}
        setDeleteTarget={setDeleteTarget}
        projects={projects}
        activeProjectId={activeProjectId}
        selectProjectScope={selectProjectScope}
        cliMenuOpen={cliMenuOpen}
        setCliMenuOpen={setCliMenuOpen}
        copiedResumeCommand={copiedResumeCommand}
        setCopiedResumeCommand={setCopiedResumeCommand}
        terminalOpen={terminalOpen}
        setTerminalOpen={setTerminalOpen}
        filesPanelCollapsed={filesPanelCollapsed}
        setFilesPanelCollapsed={setFilesPanelCollapsed}
        panelView={panelView}
        setPanelView={setPanelView}
        onPrepareDraftWorkspace={async () => {
          await prepareDraftWorkspace()
        }}
        createSession={props.createSession}
        onCreateTerminal={async () => {
          // FAS-107 GF5: dropdown "+" → create terminal in active project,
          // add it to `openTabIds` so a chip renders in the strip, then
          // navigate to the standalone /terminals/:id route.
          try {
            const term = await client.createTerminal({
              projectId: activeProjectId ?? null
            })
            addTerminalOptimistic(term)
            openSessionTab(term.id)
            navigate(`/terminals/${term.id}`)
          } catch (err) {
            console.error('createTerminal (dropdown) failed', err)
          }
        }}
        terminals={terminals}
        onCloseTerminal={handleCloseTerminal}
        onRenameTerminal={handleRenameTerminal}
        onToggleTerminalOrganizeLabel={handleToggleTerminalOrganizeLabel}
        onMoveTerminalToProject={handleMoveTerminalToProjectLocal}
        groups={tabGroups}
        onSplitWith={onSplitWithNextTab}
        onSplitPane={onSplitPane}
        onDissolveGroup={dissolveTabGroup}
        onRenameGroup={renameTabGroup}
        onSetGroupColor={setTabGroupColor}
        onSetGroupPinned={setTabGroupPinned}
        onArrangeGroup={(groupId, rows, cols) => {
          const group = tabGroups.find(item => item.id === groupId)
          if (!group || group.itemIds.length < 2) return
          setTabGroupLayoutForMonitor(
            groupId,
            getMonitorFingerprint(),
            buildGridTree(group.itemIds, rows, cols)
          )
        }}
        onCloseGroup={closeTabGroup}
        selectedChatIds={selectedChatIds}
        onToggleSelectChat={toggleSelectChat}
        onClearSelection={clearSelectChats}
        onCreateSplitFromSelection={createSplitFromSelection}
        inSplitGroup={Boolean(activeGroup)}
        activeGroupId={activeGroup?.id ?? null}
        activeTerminalId={terminalId ?? null}
      />
      <ResizablePanelGroup
        direction="horizontal"
        // Draft chats must not restore a previous session's open Files layout.
        autoSaveId={isDraft ? undefined : SESSION_PANELS_AUTO_SAVE_ID}
        className="min-h-0 min-w-0 flex-1"
      >
        <ResizablePanel
          id="chat"
          order={1}
          defaultSize={chatDefaultSize}
          minSize={30}
          className="min-w-0"
        >
          {terminalId ? (
            // Terminal-as-main-pane. The chrome tab already names it, so
            // the pane itself is just the shell.
            <main className="relative flex h-full min-w-0 flex-col">
              <TerminalPlaceholder terminalId={terminalId} />
            </main>
          ) : activeGroup ? (
            <ChatTilingContainer
              group={activeGroup}
              sessions={allSessions}
              projects={projects}
              onFocusChat={chatId => {
                setTabGroupActiveChat(activeGroup.id, chatId)
              }}
              buildHeaderProps={buildSplitHeaderProps}
              buildMountProps={buildSplitMountProps}
              pickerContext={{
                client,
                activeProjectId,
                allTabGroups: tabGroups,
                onPickPartner: onPickSplitPartner,
                onCancelPending: onCancelPendingSplit,
                onAddChat: onAddChatToSplit,
                onPickNewChat: handlePickNewChat,
                onPickTerminal: handlePickTerminal
              }}
              onSplitPane={onSplitPane}
              onLayoutChange={(fingerprint, tree) => {
                setTabGroupLayoutForMonitor(activeGroup.id, fingerprint, tree)
              }}
              onCloseChat={chatId => {
                onRemoveChatFromSplit(chatId)
              }}
              terminals={terminals}
              terminalClient={client}
              // X2 Fix 3+4: dentro de un split, "Close pane" y el
              // context-menu del pane deben SACAR el terminal del split
              // (no borrarlo). Antes se pasaba `handleCloseTerminal` que
              // llama `deleteTerminal` → el terminal desaparecía del disco.
              // `onRemoveChatFromSplit` acepta term_ ids y auto-disuelve
              // si el grupo queda con <2 items.
              onCloseTerminal={terminalId => onRemoveChatFromSplit(terminalId)}
              onRenameTerminal={handleRenameTerminal}
              onToggleTerminalOrganizeLabel={handleToggleTerminalOrganizeLabel}
              onMoveTerminalToProject={handleMoveTerminalToProjectLocal}
            />
          ) : (
          <main className="relative flex h-full min-w-0 flex-col">
            <SessionChatBody
            client={client}
            navigate={navigate}
            sessionId={sessionId}
            session={session}
            isInspect={isInspect}
            messages={messages}
            tools={tools}
            messagesLoaded={messagesLoaded}
            runActive={runActive}
            showChatSkeleton={showChatSkeleton}
            agentComposerSlotProps={{
              ...agentComposerSlotProps,
              onEnsureWorkspaceFiles: ensureWorkspaceForMentions
            }}
            projects={projects}
            recentProjectIds={recentProjectIds}
            activeProjectId={activeProjectId}
            onNewProject={onNewProject}
            selectAllProjects={selectAllProjects}
            selectProjectScope={selectProjectScope}
            updateSession={updateSession}
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
            activeBuildPlan={activeBuildPlan}
            builtPlanPaths={builtPlanPaths}
            liveDelta={liveDelta}
            pendingApproval={pendingApproval}
            approvalSubmitting={approvalSubmitting}
            onSubmitApprovals={onSubmitApprovals}
            showScrollToBottom={showScrollToBottom}
            scrollChatToBottom={scrollChatToBottom}
            setFilesPanelCollapsed={setFilesPanelCollapsed}
            setPendingOpenPath={setPendingOpenPath}
            error={error}
          />
        </main>
          )}
      </ResizablePanel>
      {canShowFilesPanel && showWorkspaceFiles && !asSheet ? (
        <>
          <ResizableHandle
            className={cn(
              'w-px bg-transparent after:bg-transparent',
              filesPanelCollapsed && 'pointer-events-none opacity-0'
            )}
          />
          <ResizablePanel
            id="files"
            order={2}
            ref={filesPanelRef}
            collapsible
            collapsedSize={0}
            // Mount collapsed when state says so; otherwise the first paint
            // is open and the collapse effect costs a second layout pass
            // over every pane in the split.
            defaultSize={filesDefaultSize}
            minSize={20}
            maxSize={55}
            onCollapse={() => setFilesPanelCollapsed(true)}
            onExpand={() => {
              // Do not materialize here. Project drafts mount this panel with
              // defaultSize>0, which fires onExpand before layout collapse —
              // that used to create an empty session on every New Agent click.
              // Files / Terminal / upload / send call prepareDraftWorkspace.
              setFilesPanelCollapsed(current => (current ? true : false))
            }}
            className="min-w-0"
          >
            {activeGroup && workspaceSessionId ? (
              <div className="border-border/60 bg-background/95 flex items-center gap-1.5 border-b px-3 py-1.5 text-[11px]">
                <span className="text-foreground truncate font-medium">
                  {allSessions.find(s => s.id === workspaceSessionId)?.title ||
                    'Untitled'}
                </span>
              </div>
            ) : null}
            {showWorkspaceFiles && workspaceSessionId ? (
              <WorkspacePanel
                client={client}
                sessionId={workspaceSessionId}
                workspacePath={isDraft ? null : session?.workspacePath ?? null}
                workspaceVersion={workspaceVersion}
                runActive={runActive}
                openPathRequest={pendingOpenPath}
                onOpenPathRequestHandled={() => setPendingOpenPath(null)}
                onAddToChat={(path, kind) => {
                  setComposer(
                    current => `${current}${fileChipToken(path, kind)}`
                  )
                  setComposerFiles([])
                }}
                onBuildPlan={path => {
                  void startPlanBuild({
                    sessionId: workspaceSessionId,
                    plan: planCardFromPath(path),
                    patchChat,
                    client,
                    setRuntimeSettings:
                      agentComposerSlotProps.setRuntimeSettings,
                    handleComposerSend:
                      agentComposerSlotProps.handleComposerSend
                  })
                }}
                onTogglePanel={() => setFilesPanelCollapsed(true)}
                panelView={panelView}
                siteId={requestedSiteId}
                terminalOpen={terminalOpen}
                onCloseTerminal={() => setTerminalOpen(false)}
                onOpenTerminal={() => setTerminalOpen(true)}
              />
            ) : null}
          </ResizablePanel>
        </>
      ) : null}
      </ResizablePanelGroup>
      {canShowFilesPanel && showWorkspaceFiles && asSheet && workspaceSessionId ? (
        <Sheet
          open={!filesPanelCollapsed}
          onOpenChange={open => setFilesPanelCollapsed(!open)}
        >
          <SheetContent
            side="right"
            className="w-full max-w-[420px] overflow-hidden p-0"
          >
            {activeGroup ? (
              <div className="border-border/60 bg-background/95 flex items-center gap-1.5 border-b px-3 py-1.5 text-[11px]">
                <span className="text-foreground truncate font-medium">
                  {allSessions.find(s => s.id === workspaceSessionId)?.title ||
                    'Untitled'}
                </span>
              </div>
            ) : null}
            <WorkspacePanel
              client={client}
              sessionId={workspaceSessionId}
              workspacePath={isDraft ? null : session?.workspacePath ?? null}
              workspaceVersion={workspaceVersion}
              runActive={runActive}
              openPathRequest={pendingOpenPath}
              onOpenPathRequestHandled={() => setPendingOpenPath(null)}
              onAddToChat={(path, kind) => {
                setComposer(
                  current => `${current}${fileChipToken(path, kind)}`
                )
                setComposerFiles([])
              }}
              onBuildPlan={path => {
                void startPlanBuild({
                  sessionId: workspaceSessionId,
                  plan: planCardFromPath(path),
                  patchChat,
                  client,
                  setRuntimeSettings:
                    agentComposerSlotProps.setRuntimeSettings,
                  handleComposerSend:
                    agentComposerSlotProps.handleComposerSend
                })
              }}
              onTogglePanel={() => setFilesPanelCollapsed(true)}
              panelView={panelView}
              siteId={requestedSiteId}
              terminalOpen={terminalOpen}
              onCloseTerminal={() => setTerminalOpen(false)}
              onOpenTerminal={() => setTerminalOpen(true)}
            />
          </SheetContent>
        </Sheet>
      ) : null}
    </div>
  )
}
