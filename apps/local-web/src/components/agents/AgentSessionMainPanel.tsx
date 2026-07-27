import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentMessage, AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  type ComponentProps,
  type Dispatch,
  type RefObject,
  type SetStateAction,
  useCallback,
  useEffect
} from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import type { NavigateFunction } from 'react-router-dom'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'
import { fileChipToken } from '@/components/agents/composer-parts'
import { TerminalPanel } from '@/components/agents/TerminalPanel'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { WorkspacePanel } from '@/components/agents/WorkspacePanel'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
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
  openTabs: AgentSession[]
  sessionId: string | null
  session: AgentSession | null
  openSessionTab: (sessionId: string) => void
  prefetchSessionMessages: (sessionId: string) => void | Promise<void>
  closeSessionTab: (sessionId: string) => void
  closeOtherSessionTabs: (sessionId: string) => void
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
  setComposerFiles: (value: string[] | ((current: string[]) => string[])) => void
}

export function AgentSessionMainPanel(props: AgentSessionMainPanelProps) {
  const {
    client,
    navigate,
    sidebarCollapsed,
    setSidebarCollapsed,
    openTabs,
    sessionId,
    session,
    openSessionTab,
    prefetchSessionMessages,
    closeSessionTab,
    closeOtherSessionTabs,
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
    setComposerFiles
  } = props

  const isDraft = isDraftAgentSessionId(sessionId)
  const inProject = Boolean(activeProjectId)

  useEffect(() => {
    // Reset when leaving the draft route or switching project scope.
    setDraftWorkspaceSessionId(null)
  }, [activeProjectId, isDraft, setDraftWorkspaceSessionId])

  const ensureAgentSession = agentComposerSlotProps.ensureAgentSession
  const prepareDraftWorkspace = useCallback(async () => {
    if (!isDraft || !inProject) return draftWorkspaceSessionId
    if (draftWorkspaceSessionId) return draftWorkspaceSessionId
    const id = await ensureAgentSession(undefined, { navigate: false })
    if (id) setDraftWorkspaceSessionId(id)
    return id
  }, [
    draftWorkspaceSessionId,
    ensureAgentSession,
    inProject,
    isDraft,
    setDraftWorkspaceSessionId
  ])

  // Do not auto-materialize on draft mount / open files panel — that created
  // empty "New research session" rows whenever New Agent ran inside a project.
  // Materialize only when the user explicitly opens Files or Terminal.

  const workspaceSessionId = isDraft ? draftWorkspaceSessionId : sessionId
  // Host terminal only when draft is outside a project.
  const showDraftTerminal = isDraft && !inProject && terminalOpen
  const showWorkspaceFiles =
    canShowFilesPanel &&
    Boolean(workspaceSessionId) &&
    (!isDraft || inProject)

  return (
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
          <SessionMainHeader
            sidebarCollapsed={sidebarCollapsed}
            setSidebarCollapsed={setSidebarCollapsed}
            openTabs={openTabs}
            sessionId={sessionId}
            session={session}
            navigate={navigate}
            openSessionTab={openSessionTab}
            prefetchSessionMessages={prefetchSessionMessages}
            closeSessionTab={closeSessionTab}
            closeOtherSessionTabs={closeOtherSessionTabs}
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
            onPrepareDraftWorkspace={prepareDraftWorkspace}
          />
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
            agentComposerSlotProps={agentComposerSlotProps}
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
            onExpand={() => {
              setFilesPanelCollapsed(false)
              if (isDraft && inProject) void prepareDraftWorkspace()
            }}
            className="min-w-0"
          >
            {showWorkspaceFiles && workspaceSessionId ? (
              <WorkspacePanel
                key={workspaceSessionId}
                client={client}
                sessionId={workspaceSessionId}
                workspacePath={
                  isDraft
                    ? null
                    : (session?.workspacePath ?? null)
                }
                workspaceVersion={workspaceVersion}
                runActive={runActive}
                openPathRequest={pendingOpenPath}
                onOpenPathRequestHandled={() => setPendingOpenPath(null)}
                onAddToChat={path => {
                  setComposer(current => `${current}${fileChipToken(path)}`)
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
                onNewFiles={added => {
                  // Chat composer uploads land under uploads/ — keep those in
                  // the composer preview only. Auto-open Files for other new
                  // workspace files (agent artifacts, etc.).
                  const noteworthy = added.filter(file => {
                    const path = file.path.replace(/\\/g, '/')
                    return (
                      !path.startsWith('uploads/') && path !== 'uploads'
                    )
                  })
                  if (noteworthy.length === 0) return
                  setFilesPanelCollapsed(false)
                  const previewable = [...noteworthy]
                    .reverse()
                    .find(file =>
                      /\.(svg|png|jpe?g|gif|webp|pdb|cif|mmcif|sdf|json|md|txt|csv|tsv)$/i.test(
                        file.name
                      )
                    )
                  if (previewable) {
                    setPendingOpenPath(previewable.path)
                    return
                  }
                  const artifactDir = noteworthy.find(file =>
                    file.path.replace(/\\/g, '/').startsWith('artifacts/')
                  )
                  if (artifactDir) setPendingOpenPath('artifacts/')
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
            <aside className="bg-card relative z-20 flex h-full w-full min-h-0 min-w-0 flex-col">
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
  )
}
