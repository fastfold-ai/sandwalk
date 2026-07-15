import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentMessage, AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Check,
  Copy,
  Download,
  Folder,
  PanelLeft,
  PanelRight,
  SquareTerminal,
  Terminal
} from 'lucide-react'
import {
  type ComponentProps,
  type Dispatch,
  lazy,
  type RefObject,
  type SetStateAction,
  Suspense} from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import type { NavigateFunction } from 'react-router-dom'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'
import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { ChatTranscript } from '@/components/agents/ChatTranscript'
import { fileChipToken } from '@/components/agents/composer-parts'
import {
  ChatPageSkeleton,
  DetailPageSkeleton
} from '@/components/agents/PageSkeletons'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { SessionTabs } from '@/components/agents/SessionTabs'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { WorkspacePanel } from '@/components/agents/WorkspacePanel'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import { SESSION_PANELS_AUTO_SAVE_ID } from '@/lib/app-storage'
import { type SessionChatState } from '@/lib/sessions'
import { cn } from '@/lib/utils'

const InspectView = lazy(() =>
  import('@/components/agents/InspectView').then(m => ({
    default: m.InspectView
  }))
)

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
  liveDelta: string
  showScrollToBottom: boolean
  scrollChatToBottom: () => void
  error: string | null
  canShowFilesPanel: boolean
  filesPanelRef: RefObject<ImperativePanelHandle | null>
  workspaceVersion: number
  pendingOpenPath: string | null
  setPendingOpenPath: Dispatch<SetStateAction<string | null>>
  setComposer: (value: string | ((current: string) => string)) => void
  setComposerFiles: (value: string[] | ((current: string[]) => string[])) => void
}

export function AgentSessionMainPanel({
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
  liveDelta,
  showScrollToBottom,
  scrollChatToBottom,
  error,
  canShowFilesPanel,
  filesPanelRef,
  workspaceVersion,
  pendingOpenPath,
  setPendingOpenPath,
  setComposer,
  setComposerFiles
}: AgentSessionMainPanelProps) {
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
        <div className="flex h-10 shrink-0 items-center gap-1 px-1.5 md:px-2">
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
          <SessionTabs
            tabs={openTabs}
            activeId={sessionId}
            onSelect={id => {
              openSessionTab(id)
              void prefetchSessionMessages(id)
              navigate(`/agents/${id}`)
            }}
            onClose={closeSessionTab}
            onCloseOthers={closeOtherSessionTabs}
            onRename={openRenameDialog}
            onTogglePin={item =>
              void updateSession(item, {
                organizeLabel:
                  item.organizeLabel === 'pinned' ? null : 'pinned'
              })
            }
            onExport={item => void exportTranscript(item)}
            onInspect={item => navigate(`/agents/${item.id}?inspect=1`)}
            onArchive={item =>
              void updateSession(item, {
                organizeLabel:
                  item.organizeLabel === 'archive' ? null : 'archive'
              })
            }
            onDelete={item => setDeleteTarget(item)}
          />
          <div className="ml-auto flex shrink-0 items-center gap-0.5">
            {session?.projectId
              ? (() => {
                  const projectName =
                    projects.find(p => p.id === session.projectId)
                      ?.name || null
                  if (!projectName) return null
                  return (
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground mr-1 inline-flex max-w-[12rem] items-center gap-1.5 rounded-md px-1.5 py-1 text-xs"
                      title={projectName}
                      onClick={() =>
                        selectProjectScope(session.projectId!)
                      }
                    >
                      <Folder className="size-3.5 shrink-0" />
                      <span className="truncate">{projectName}</span>
                    </button>
                  )
                })()
              : null}
            <DropdownMenu
              open={cliMenuOpen}
              onOpenChange={open => {
                setCliMenuOpen(open)
                if (!open) setCopiedResumeCommand(false)
              }}
            >
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-8"
                  aria-label="Resume in Agent CLI"
                  title="Resume in Agent CLI"
                  disabled={!sessionId}
                >
                  <Terminal className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                sideOffset={6}
                className="w-[22rem] overflow-hidden rounded-xl p-0"
                onCloseAutoFocus={event => event.preventDefault()}
              >
                <div className="px-4 pt-3">
                  <p className="text-foreground text-sm font-semibold">
                    Resume in Agent CLI
                  </p>
                </div>
                <div className="px-4 pb-3 pt-2">
                  <div className="border-border/80 bg-muted/35 flex items-center gap-2 rounded-lg border p-2.5">
                    <Terminal className="text-muted-foreground size-4 shrink-0" />
                    <code className="min-w-0 flex-1 truncate font-mono text-[13px]">
                      {sessionId
                        ? `sandwalk --resume ${sessionId}`
                        : 'sandwalk --resume <chat_id>'}
                    </code>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-7 shrink-0 rounded-md"
                      disabled={!sessionId}
                      onClick={event => {
                        event.preventDefault()
                        event.stopPropagation()
                        if (!sessionId) return
                        void navigator.clipboard.writeText(
                          `sandwalk --resume ${sessionId}`
                        )
                        setCopiedResumeCommand(true)
                        window.setTimeout(
                          () => setCopiedResumeCommand(false),
                          2000
                        )
                      }}
                      aria-label="Copy resume command"
                      title="Copy resume command"
                    >
                      {copiedResumeCommand ? (
                        <Check className="size-3.5" />
                      ) : (
                        <Copy className="size-3.5" />
                      )}
                    </Button>
                  </div>
                  <p className="text-muted-foreground mt-2 text-xs">
                    Continue this session in your local sandwalk CLI.
                  </p>
                </div>
                <div className="border-border/70 border-t px-4 py-3">
                  <DropdownMenuItem
                    className="h-10 cursor-pointer gap-2 rounded-lg px-3 text-sm"
                    disabled={!session}
                    onSelect={() => {
                      if (!session) return
                      void exportTranscript(session)
                    }}
                  >
                    <Download className="size-4" />
                    Export transcript
                  </DropdownMenuItem>
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8"
              disabled={!sessionId}
              onClick={() => {
                if (terminalOpen) {
                  setTerminalOpen(false)
                  return
                }
                setFilesPanelCollapsed(false)
                setTerminalOpen(true)
              }}
              aria-label={
                terminalOpen ? 'Hide terminal' : 'Show terminal'
              }
              title={terminalOpen ? 'Hide terminal' : 'Show terminal'}
            >
              <SquareTerminal
                className={cn(
                  'size-4',
                  terminalOpen && 'text-foreground'
                )}
              />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8"
              onClick={() =>
                setFilesPanelCollapsed(current => !current)
              }
              aria-label={
                filesPanelCollapsed
                  ? 'Show files panel'
                  : 'Hide files panel'
              }
              title={
                filesPanelCollapsed
                  ? 'Show files panel'
                  : 'Hide files panel'
              }
            >
              <PanelRight
                className={cn(
                  'size-4',
                  !filesPanelCollapsed && 'text-foreground'
                )}
              />
            </Button>
          </div>
        </div>
        {isInspect ? (
          <Suspense fallback={<DetailPageSkeleton />}>
            <InspectView
              messages={messages}
              tools={tools}
              onClose={() => navigate(`/agents/${sessionId}`)}
            />
          </Suspense>
        ) : null}
        <div
          className={cn(
            'flex min-h-0 flex-1 flex-col',
            isInspect && 'hidden'
          )}
        >
          {!messagesLoaded && !runActive ? (
            showChatSkeleton ? (
              <div className="animate-in fade-in flex min-h-0 flex-1 flex-col overflow-hidden duration-200">
                <ChatPageSkeleton />
              </div>
            ) : (
              <div className="flex min-h-0 flex-1 flex-col" />
            )
          ) : messages.length === 0 && !runActive ? (
            <div className="animate-in fade-in flex min-h-0 flex-1 flex-col items-center justify-center px-5 pb-20 duration-200">
              <AuraIconPulse className="text-muted-foreground/70 mb-6 h-12 w-12" />
              <div className="bg-background w-full max-w-[44rem]">
                <div className="mb-2 flex items-center px-1">
                  <ProjectPicker
                    projects={projects}
                    value={session?.projectId ?? activeProjectId}
                    recentIds={recentProjectIds}
                    noneLabel="All"
                    onNewProject={onNewProject}
                    onChange={projectId => {
                      if (session) {
                        void updateSession(session, { projectId })
                      }
                      if (projectId) selectProjectScope(projectId)
                      else selectAllProjects()
                    }}
                  />
                </div>
                <AgentComposerSlot {...agentComposerSlotProps} />
              </div>
            </div>
          ) : (
            <div className="animate-in fade-in flex min-h-0 flex-1 flex-col duration-200">
              <ChatTranscript
                chatScrollRef={chatScrollRef}
                chatEndRef={chatEndRef}
                conversationTimeline={conversationTimeline}
                expandedToolRunKeys={expandedToolRunKeys}
                sessionId={sessionId}
                onToggleToolRunExpanded={key => {
                  if (!sessionId) return
                  patchChat(sessionId, prev => ({
                    ...prev,
                    expandedToolRunKeys: {
                      ...prev.expandedToolRunKeys,
                      [key]: !(prev.expandedToolRunKeys[key] === true)
                    }
                  }))
                }}
                runActive={runActive}
                tools={tools}
                runIdByMessageId={runIdByMessageId}
                usageByRunId={usageByRunId}
                messages={messages}
                copiedMessageId={copiedMessageId}
                setCopiedMessageId={setCopiedMessageId}
                session={session}
                onOpenFile={path => {
                  setFilesPanelCollapsed(false)
                  setPendingOpenPath(path)
                }}
                onInterrupt={
                  sessionId
                    ? () => void client.interrupt(sessionId)
                    : undefined
                }
                activeRunTools={activeRunTools}
                activeRunTodos={activeRunTodos}
                liveDelta={liveDelta}
                showScrollToBottom={showScrollToBottom}
                onScrollToBottom={scrollChatToBottom}
              />
              <div className="bg-background mx-auto w-full max-w-[44rem] shrink-0 px-5 pb-6 pt-2">
                <AgentComposerSlot {...agentComposerSlotProps} />
              </div>
            </div>
          )}
        </div>
        {error ? (
          <div className="bg-destructive text-destructive-foreground absolute bottom-2 left-1/2 -translate-x-1/2 rounded-md px-3 py-1.5 text-xs">
            {error}
          </div>
        ) : null}
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
            onExpand={() => setFilesPanelCollapsed(false)}
            className="min-w-0"
          >
            {sessionId ? (
              <WorkspacePanel
                key={sessionId}
                client={client}
                sessionId={sessionId}
                workspaceVersion={workspaceVersion}
                openPathRequest={pendingOpenPath}
                onOpenPathRequestHandled={() => setPendingOpenPath(null)}
                onAddToChat={path => {
                  setComposer(current => `${current}${fileChipToken(path)}`)
                  setComposerFiles([])
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
    </ResizablePanelGroup>
  )
}
