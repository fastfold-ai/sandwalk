import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentMessage, AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import { lazy, Suspense, type ComponentProps, type Dispatch, type RefObject, type SetStateAction } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'
import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { ChatTranscript } from '@/components/agents/ChatTranscript'
import { startPlanBuild } from '@/lib/plan-build'
import {
  ChatPageSkeleton,
  DetailPageSkeleton
} from '@/components/agents/PageSkeletons'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type TranscriptEntry } from '@/components/agents/transcript'
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
  messagesLoaded,
  runActive,
  showChatSkeleton,
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
  showScrollToBottom,
  scrollChatToBottom,
  setFilesPanelCollapsed,
  setPendingOpenPath,
  error
}: SessionChatBodyProps) {
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
        {!messagesLoaded && !runActive ? (
          showChatSkeleton ? (
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <ChatPageSkeleton />
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col" />
          )
        ) : messages.length === 0 && !runActive ? (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-5 pb-20">
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
          <div className="flex min-h-0 flex-1 flex-col">
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
              onBuildPlan={plan => {
                if (!sessionId) return
                void startPlanBuild({
                  sessionId,
                  plan,
                  patchChat,
                  client,
                  setRuntimeSettings: agentComposerSlotProps.setRuntimeSettings,
                  handleComposerSend: agentComposerSlotProps.handleComposerSend
                })
              }}
              onInterrupt={
                sessionId
                  ? () => void agentComposerSlotProps.handleStop()
                  : undefined
              }
              activeRunTools={activeRunTools}
              activeRunTodos={activeRunTodos}
              activeBuildPlan={activeBuildPlan}
              builtPlanPaths={builtPlanPaths}
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
    </>
  )
}
