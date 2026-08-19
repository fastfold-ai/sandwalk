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
import { type NavigateFunction,useLocation } from 'react-router-dom'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'
import { ChatTilingContainer } from '@/components/agents/ChatTilingContainer'
import { fileChipToken } from '@/components/agents/composer-parts'
import { useSessionSiteAutoPreview } from '@/components/agents/sites/use-session-site-auto-preview'
import { TerminalPanel } from '@/components/agents/TerminalPanel'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { WorkspacePanel } from '@/components/agents/WorkspacePanel'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import { Sheet, SheetContent } from '@/components/ui/sheet'
import { useIsNarrowWindow } from '@/hooks/useIsNarrowWindow'
import type { PerSessionChatStateArgs } from '@/hooks/usePerSessionChatState'
import { SESSION_PANELS_AUTO_SAVE_ID } from '@/lib/app-storage'
import {
  HOST_TERMINAL_SESSION_ID,
  isDraftAgentSessionId
} from '@/lib/draft-agent'
import { planCardFromPath, startPlanBuild } from '@/lib/plan-build'
import { type SessionChatState } from '@/lib/sessions'
import { cn } from '@/lib/utils'

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
  onPickSplitPartner: (partnerId: string) => void
  onCancelPendingSplit: () => void
  onAddChatToSplit: (chatId: string) => void
  onRemoveChatFromSplit: (chatId: string) => void
  dissolveTabGroup: (groupId: string) => void
  renameTabGroup: (group: SessionGroup) => void
  setTabGroupColor: (groupId: string, color: string | null) => void
  closeTabGroup: (groupId: string) => void
  selectedChatIds: Set<string>
  toggleSelectChat: (id: string) => void
  clearSelectChats: () => void
  createSplitFromSelection: () => void
}

export function AgentSessionMainPanel(props: AgentSessionMainPanelProps) {
  const location = useLocation()
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
    onPickSplitPartner,
    onCancelPendingSplit,
    onAddChatToSplit,
    onRemoveChatFromSplit,
    dissolveTabGroup,
    renameTabGroup,
    setTabGroupColor,
    closeTabGroup,
    selectedChatIds,
    toggleSelectChat,
    clearSelectChats,
    createSplitFromSelection
  } = props

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
  const showDraftTerminal = isDraft && !inProject && terminalOpen
  const showWorkspaceFiles =
    canShowFilesPanel && Boolean(workspaceSessionId) && (!isDraft || inProject)

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
   * INVARIANT: `onSplitLeft/Right/Up/Down` are NOT populated here. They
   * live inside `ChatTilingContainer.ChatLeaf` where the tree ops are
   * in scope; the leaf spreads this builder's result then overrides
   * those four keys. If you add another consumer of this builder outside
   * the tiling container, either re-inject the four handlers there or
   * lift them into this builder (in that case pass the tree helpers as
   * dependencies). Without either, the ellipsis menu silently loses the
   * four split entries — no compile error, no runtime error.
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
        shared: {
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
        }
      }
    },
    [
      allSessions,
      perSessionBaseArgs,
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
    ]
  )

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
        groups={tabGroups}
        onSplitWith={onSplitWithNextTab}
        onDissolveGroup={dissolveTabGroup}
        onRenameGroup={renameTabGroup}
        onSetGroupColor={setTabGroupColor}
        onCloseGroup={closeTabGroup}
        selectedChatIds={selectedChatIds}
        onToggleSelectChat={toggleSelectChat}
        onClearSelection={clearSelectChats}
        onCreateSplitFromSelection={createSplitFromSelection}
        inSplitGroup={Boolean(activeGroup)}
        activeGroupId={activeGroup?.id ?? null}
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
          defaultSize={65}
          minSize={30}
          className="min-w-0"
        >
          {activeGroup ? (
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
                onAddChat: onAddChatToSplit
              }}
              onLayoutChange={(fingerprint, tree) => {
                setTabGroupLayoutForMonitor(activeGroup.id, fingerprint, tree)
              }}
              onCloseChat={chatId => {
                onRemoveChatFromSplit(chatId)
              }}
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
            defaultSize={35}
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
      {showDraftTerminal ? (
        <>
          <ResizableHandle className="w-px" />
          <ResizablePanel
            id="draft-terminal"
            order={3}
            defaultSize={40}
            minSize={25}
            maxSize={70}
            className="min-w-0"
          >
            <aside className="bg-card relative z-20 flex h-full min-h-0 w-full min-w-0 flex-col">
              <TerminalPanel
                client={client}
                sessionId={HOST_TERMINAL_SESSION_ID}
                visible={terminalOpen}
                autoCreateOnEmpty
                onClose={() => setTerminalOpen(false)}
                className="border-t-0"
              />
            </aside>
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
