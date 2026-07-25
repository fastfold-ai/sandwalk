import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentMessage,
  AgentPlanCard,
  AgentSession,
  AgentSkill,
  AgentTodo,
  HitlDecision,
  McpServer,
  PendingHitlApproval
} from '@sandwalk/agent-ui-core'
import { ArrowDown } from 'lucide-react'
import type { Dispatch, RefObject, SetStateAction } from 'react'
import { useDeferredValue, useMemo } from 'react'

import { AgentStatusText } from '@/components/agents/AgentStatusText'
import { BuildPlanStatusCard } from '@/components/agents/BuildPlanStatusCard'
import { HitlDecisionCard } from '@/components/agents/hitl/HitlDecisionCard'
import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { TodoListInline } from '@/components/agents/TodoListInline'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { buildChatTimelineItems } from '@/components/agents/chat-transcript-timeline'
import { ChatTranscriptTimelineItem } from '@/components/agents/chat-transcript-timeline-item'
import { LiveToolStack } from '@/components/agents/live-tool-stack'
import { ScrollArea } from '@/components/ui/scroll-area'

type ChatTranscriptProps = {
  chatScrollRef: RefObject<HTMLDivElement | null>
  chatEndRef: RefObject<HTMLDivElement | null>
  conversationTimeline: TranscriptEntry[]
  expandedToolRunKeys: Record<string, boolean>
  sessionId: string | null
  client?: LocalAgentClient | null
  onToggleToolRunExpanded: (key: string) => void
  runActive: boolean
  tools: TranscriptTool[]
  runIdByMessageId: Record<string, string>
  usageByRunId: Record<string, { inputTokens: number; outputTokens: number }>
  messages: AgentMessage[]
  copiedMessageId: string | null
  setCopiedMessageId: Dispatch<SetStateAction<string | null>>
  session: AgentSession | null | undefined
  onOpenFile: (path: string) => void
  onBuildPlan?: (plan: AgentPlanCard) => void
  onInterrupt: (() => void) | undefined
  activeRunTools: TranscriptTool[]
  activeRunTodos: AgentTodo[]
  activeBuildPlan?: AgentPlanCard | null
  builtPlanPaths?: string[]
  liveDelta: string
  pendingApproval?: PendingHitlApproval | null
  approvalSubmitting?: boolean
  onSubmitApprovals?: (decisions: HitlDecision[]) => void | Promise<void>
  showScrollToBottom: boolean
  onScrollToBottom: () => void
  skills?: AgentSkill[]
  mcpServers?: McpServer[]
}

export function ChatTranscript({
  chatScrollRef,
  chatEndRef,
  conversationTimeline,
  expandedToolRunKeys,
  sessionId,
  client,
  onToggleToolRunExpanded,
  runActive,
  tools,
  runIdByMessageId,
  usageByRunId,
  messages,
  copiedMessageId,
  setCopiedMessageId,
  session,
  onOpenFile,
  onBuildPlan,
  onInterrupt,
  activeRunTools,
  activeRunTodos,
  activeBuildPlan = null,
  builtPlanPaths = [],
  liveDelta,
  pendingApproval = null,
  approvalSubmitting = false,
  onSubmitApprovals,
  showScrollToBottom,
  onScrollToBottom,
  skills = [],
  mcpServers = []
}: ChatTranscriptProps) {
  const timelineItems = useMemo(
    () => buildChatTimelineItems(conversationTimeline),
    [conversationTimeline]
  )
  // Deferred: the markdown re-parse of the growing stream renders at low
  // priority so typing/scrolling stays responsive during fast token bursts.
  const deferredDelta = useDeferredValue(liveDelta)
  const hiddenPlanPaths = useMemo(() => {
    const paths = new Set(builtPlanPaths)
    if (activeBuildPlan?.path) paths.add(activeBuildPlan.path)
    return paths
  }, [activeBuildPlan?.path, builtPlanPaths])

  // Status tracks the same cards the user sees, plus any pending tools that
  // arrived without a runId (still rendered via the pending filter).
  const statusTools = useMemo(() => {
    const pending = tools.filter(tool => tool.status === 'pending')
    if (pending.length === 0) return activeRunTools
    const seen = new Set(activeRunTools.map(tool => tool.id))
    const extras = pending.filter(tool => !seen.has(tool.id))
    if (extras.length === 0) return activeRunTools
    return [...activeRunTools, ...extras]
  }, [activeRunTools, tools])

  return (
    <div className="relative min-h-0 flex-1">
      <ScrollArea
        ref={chatScrollRef}
        className="chat-scrollbar h-full min-h-0"
      >
        <div className="mx-auto flex w-full max-w-[44rem] flex-col px-5 py-6">
          <div className="mb-4 flex min-w-0 flex-1 flex-col gap-y-2 empty:hidden">
            {timelineItems.map(timelineItem => (
              <ChatTranscriptTimelineItem
                key={timelineItem.key}
                timelineItem={timelineItem}
                sessionId={sessionId}
                client={client}
                expandedToolRunKeys={expandedToolRunKeys}
                onToggleToolRunExpanded={onToggleToolRunExpanded}
                runActive={runActive}
                tools={tools}
                runIdByMessageId={runIdByMessageId}
                usageByRunId={usageByRunId}
                messages={messages}
                copiedMessageId={copiedMessageId}
                setCopiedMessageId={setCopiedMessageId}
                session={session}
                onOpenFile={onOpenFile}
                onBuildPlan={onBuildPlan}
                onInterrupt={onInterrupt}
                hiddenPlanPaths={hiddenPlanPaths}
                skills={skills}
                mcpServers={mcpServers}
              />
            ))}
            {runActive && activeBuildPlan ? (
              <div className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150">
                <BuildPlanStatusCard
                  plan={activeBuildPlan}
                  todos={activeRunTodos}
                />
              </div>
            ) : null}
            <LiveToolStack
              tools={activeRunTools}
              runActive={runActive}
              onInterrupt={onInterrupt}
            />
            {pendingApproval && onSubmitApprovals ? (
              <div className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150">
                <HitlDecisionCard
                  actionRequests={pendingApproval.actionRequests}
                  reviewConfigs={pendingApproval.reviewConfigs}
                  submitting={approvalSubmitting}
                  onSubmit={onSubmitApprovals}
                />
              </div>
            ) : null}
            {deferredDelta ? (
              <div className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150">
                <MarkdownContent
                  content={deferredDelta}
                  streaming
                  onOpenFile={onOpenFile}
                  workspacePath={session?.workspacePath}
                  skills={skills}
                  className="max-w-full space-y-3 [&_*]:max-w-full"
                />
              </div>
            ) : null}
            {runActive && !deferredDelta ? (
              <div className="mx-auto flex w-full max-w-[44rem] items-center px-2 py-2 text-sm">
                {pendingApproval ? (
                  <span className="animate-text-shimmer font-light">
                    Pending approval
                  </span>
                ) : (
                  <AgentStatusText tools={statusTools} />
                )}
              </div>
            ) : null}
            {activeRunTodos.length > 0 && !activeBuildPlan ? (
              <div className="mx-auto w-full max-w-[44rem] px-2 pt-1">
                <TodoListInline todos={activeRunTodos} />
              </div>
            ) : null}
          </div>
          <div
            ref={chatEndRef}
            aria-hidden
            className="h-px w-full shrink-0"
          />
        </div>
      </ScrollArea>
      {showScrollToBottom ? (
        <button
          type="button"
          onClick={() => onScrollToBottom()}
          aria-label="Scroll to latest message"
          title="Scroll to latest message"
          className="bg-background text-foreground border-border/70 absolute bottom-3 left-1/2 z-20 flex size-9 -translate-x-1/2 items-center justify-center rounded-full border shadow-[0_4px_16px_-4px_rgba(0,0,0,0.18)] transition-opacity hover:bg-background dark:shadow-[0_6px_20px_-6px_rgba(0,0,0,0.65)]"
        >
          <ArrowDown className="size-4" />
        </button>
      ) : null}
    </div>
  )
}
