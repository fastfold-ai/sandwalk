import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentMessage, AgentPlanCard, AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import { type ComponentProps, type Dispatch, lazy, type RefObject, type SetStateAction,Suspense, useCallback, useMemo, useRef } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'
import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { ChatTranscript } from '@/components/agents/ChatTranscript'
import { DetailPageSkeleton } from '@/components/agents/PageSkeletons'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { startPlanBuild } from '@/lib/plan-build'
import { type SessionChatState } from '@/lib/sessions'
import { cn } from '@/lib/utils'

const InspectView = lazy(() =>
  import('@/components/agents/InspectView').then(m => ({
    default: m.InspectView
  }))
)

export type SessionChatBodyProps = {
  client: LocalAgentClient
  navigate: NavigateFunction
  sessionId: string | null
  session: AgentSession | null
  isInspect: boolean
  messages: AgentMessage[]
  tools: TranscriptTool[]
  messagesLoaded: boolean
  runActive: boolean
  showChatSkeleton: boolean
  agentComposerSlotProps: ComponentProps<typeof AgentComposerSlot>
  projects: AgentProject[]
  recentProjectIds: string[]
  activeProjectId: string | null
  onNewProject: () => void
  selectAllProjects: () => void
  selectProjectScope: (projectId: string) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
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
  setFilesPanelCollapsed: Dispatch<SetStateAction<boolean>>
  setPendingOpenPath: Dispatch<SetStateAction<string | null>>
  error: string | null
}

export function SessionChatBody({
  client,
  navigate,
  sessionId,
  session,
  isInspect,
  messages,
  tools,
  messagesLoaded: _messagesLoaded,
  runActive,
  showChatSkeleton: _showChatSkeleton,
  agentComposerSlotProps,
  projects,
  recentProjectIds,
  activeProjectId,
  onNewProject,
  selectAllProjects,
  selectProjectScope,
  updateSession,
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
  setFilesPanelCollapsed,
  setPendingOpenPath,
  error
}: SessionChatBodyProps) {
  // Stable callbacks: memoized transcript rows must not re-render per stream
  // delta because a lambda got a new identity. Composer props change every
  // render, so reach them through a ref.
  const composerPropsRef = useRef(agentComposerSlotProps)
  composerPropsRef.current = agentComposerSlotProps

  const handleToggleToolRunExpanded = useCallback(
    (key: string) => {
      if (!sessionId) return
      patchChat(sessionId, prev => ({
        ...prev,
        expandedToolRunKeys: {
          ...prev.expandedToolRunKeys,
          [key]: !(prev.expandedToolRunKeys[key] === true)
        }
      }))
    },
    [patchChat, sessionId]
  )

  const handleOpenFile = useCallback(
    (path: string) => {
      setFilesPanelCollapsed(false)
      setPendingOpenPath(path)
    },
    [setFilesPanelCollapsed, setPendingOpenPath]
  )

  const handleBuildPlan = useCallback(
    (plan: AgentPlanCard) => {
      if (!sessionId) return
      void startPlanBuild({
        sessionId,
        plan,
        patchChat,
        client,
        setRuntimeSettings: composerPropsRef.current.setRuntimeSettings,
        handleComposerSend: composerPropsRef.current.handleComposerSend
      })
    },
    [client, patchChat, sessionId]
  )

  const handleInterrupt = useMemo(
    () =>
      sessionId
        ? () => void composerPropsRef.current.handleStop()
        : undefined,
    [sessionId]
  )

  // One continuous layout: empty = composer centered; active = transcript +
  // composer docked at the bottom. No skeleton swap — flex-grow animates.
  const showTranscript = messages.length > 0 || runActive

  return (
    <>
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
        <div
          className="flex min-h-0 flex-col overflow-hidden transition-[flex-grow,opacity] duration-500 ease-out"
          style={{
            flexGrow: showTranscript ? 1 : 0,
            flexShrink: 1,
            flexBasis: 0,
            opacity: showTranscript ? 1 : 0
          }}
        >
          {showTranscript ? (
            <ChatTranscript
              chatScrollRef={chatScrollRef}
              chatEndRef={chatEndRef}
              conversationTimeline={conversationTimeline}
              expandedToolRunKeys={expandedToolRunKeys}
              sessionId={sessionId}
              client={client}
              onToggleToolRunExpanded={handleToggleToolRunExpanded}
              runActive={runActive}
              tools={tools}
              runIdByMessageId={runIdByMessageId}
              usageByRunId={usageByRunId}
              messages={messages}
              copiedMessageId={copiedMessageId}
              setCopiedMessageId={setCopiedMessageId}
              session={session}
              onOpenFile={handleOpenFile}
              onBuildPlan={handleBuildPlan}
              onInterrupt={handleInterrupt}
              activeRunTools={activeRunTools}
              activeRunTodos={activeRunTodos}
              activeBuildPlan={activeBuildPlan}
              builtPlanPaths={builtPlanPaths}
              liveDelta={liveDelta}
              pendingApproval={pendingApproval}
              approvalSubmitting={approvalSubmitting}
              onSubmitApprovals={onSubmitApprovals}
              showScrollToBottom={showScrollToBottom}
              onScrollToBottom={scrollChatToBottom}
              skills={agentComposerSlotProps.skills}
              mcpServers={agentComposerSlotProps.mcpServers}
              workspaceFiles={agentComposerSlotProps.workspaceFiles}
            />
          ) : null}
        </div>

        <div
          className={cn(
            'bg-background mx-auto flex w-full max-w-[44rem] flex-col px-5 transition-[flex-grow,padding] duration-500 ease-out',
            showTranscript ? 'justify-end' : 'justify-center'
          )}
          style={{
            flexGrow: showTranscript ? 0 : 1,
            flexShrink: 0,
            flexBasis: 'auto',
            paddingBottom: showTranscript ? '1.5rem' : '5rem',
            paddingTop: showTranscript ? '0.5rem' : 0
          }}
        >
          <div
            className={cn(
              'flex flex-col items-center overflow-hidden transition-[max-height,opacity,margin] duration-300 ease-out',
              showTranscript
                ? 'mb-0 max-h-0 opacity-0'
                : 'mb-2 max-h-40 opacity-100'
            )}
          >
            <AuraIconPulse className="text-muted-foreground/70 mb-6 h-12 w-12" />
            <div className="mb-2 flex w-full items-center px-1">
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
          </div>
          <AgentComposerSlot {...agentComposerSlotProps} />
        </div>
      </div>
      {error ? (
        <div className="bg-destructive text-destructive-foreground absolute bottom-2 left-1/2 -translate-x-1/2 rounded-md px-3 py-1.5 text-xs">
          {error}
        </div>
      ) : null}
    </>
  )
}
