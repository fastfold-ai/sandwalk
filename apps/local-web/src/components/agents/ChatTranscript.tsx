import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentMessage,
  AgentPlanCard,
  AgentSession,
  AgentSkill,
  AgentTodo,
  HitlDecision,
  McpServer,
  PendingHitlApproval,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import { ArrowDown } from 'lucide-react'
import type { Dispatch, RefObject, SetStateAction } from 'react'
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'

import { AgentStatusText } from '@/components/agents/AgentStatusText'
import { BuildPlanStatusCard } from '@/components/agents/BuildPlanStatusCard'
import {
  buildChatTimelineItems,
  reuseTimelineItems
} from '@/components/agents/chat-transcript-timeline'
import { useStableCallback } from '@/hooks/useStableCallback'
import { ChatTranscriptTimelineItem } from '@/components/agents/chat-transcript-timeline-item'
import { HitlDecisionCard } from '@/components/agents/hitl/HitlDecisionCard'
import { LiveToolStack } from '@/components/agents/live-tool-stack'
import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { TodoListInline } from '@/components/agents/TodoListInline'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { perfCount } from '@/lib/perf-probe'

// Stable empty-array singletons for the ?= defaults below. A fresh `[]`
// per render changes identity, which cascades into MarkdownContent's
// useMemo → new markdown component object → MarkdownCodeBlock unmounts
// → shiki re-runs → height swap → visible jitter.
const EMPTY_PLAN_PATHS: string[] = []
const EMPTY_SKILLS: AgentSkill[] = []
const EMPTY_MCP_SERVERS: McpServer[] = []
const EMPTY_WORKSPACE_FILES: WorkspaceFile[] = []
const EMPTY_MENTION_CHATS: AgentSession[] = []

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
  /** Server status for the active run, e.g. waiting in the capacity queue. */
  liveStatus?: string | null
  /** Edit a past user message and send it again as a new turn. */
  onResendMessage?: (text: string) => void | Promise<void>
  pendingApproval?: PendingHitlApproval | null
  approvalSubmitting?: boolean
  onSubmitApprovals?: (decisions: HitlDecision[]) => void | Promise<void>
  showScrollToBottom: boolean
  onScrollToBottom: () => void
  skills?: AgentSkill[]
  mcpServers?: McpServer[]
  workspaceFiles?: WorkspaceFile[]
  mentionChats?: AgentSession[]
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
  builtPlanPaths = EMPTY_PLAN_PATHS,
  liveDelta,
  liveStatus = null,
  onResendMessage,
  pendingApproval = null,
  approvalSubmitting = false,
  onSubmitApprovals,
  showScrollToBottom,
  onScrollToBottom,
  skills = EMPTY_SKILLS,
  mcpServers = EMPTY_MCP_SERVERS,
  workspaceFiles = EMPTY_WORKSPACE_FILES,
  mentionChats = EMPTY_MENTION_CHATS
}: ChatTranscriptProps) {
  perfCount('render.ChatTranscript')
  // Keep item object identity across rebuilds so memoized rows skip work;
  // pin the row callbacks for the same reason (parents recreate them).
  const previousItemsRef = useRef<ReturnType<typeof buildChatTimelineItems>>([])
  const timelineItems = useMemo(() => {
    const next = reuseTimelineItems(
      previousItemsRef.current,
      buildChatTimelineItems(conversationTimeline)
    )
    previousItemsRef.current = next
    return next
  }, [conversationTimeline])
  const stableToggleToolRunExpanded = useStableCallback(onToggleToolRunExpanded)
  const stableOpenFile = useStableCallback(onOpenFile)
  const stableBuildPlan = useStableCallback(onBuildPlan)
  const stableInterrupt = useStableCallback(onInterrupt)
  const lastMessageId = messages.at(-1)?.id
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

  // Track scroll position so we can hide the top / bottom edge fades when the
  // user is already at that extreme. Radix ScrollArea exposes an inner viewport
  // (`[data-radix-scroll-area-viewport]`) — that's what actually scrolls.
  const [atTop, setAtTop] = useState(true)
  const [atBottom, setAtBottom] = useState(true)
  useEffect(() => {
    const root = chatScrollRef.current
    if (!root) return
    const viewport = root.querySelector<HTMLElement>(
      '[data-radix-scroll-area-viewport]'
    )
    if (!viewport) return
    const update = () => {
      const slack = 1
      setAtTop(viewport.scrollTop <= slack)
      setAtBottom(
        viewport.scrollTop + viewport.clientHeight >=
          viewport.scrollHeight - slack
      )
    }
    update()
    viewport.addEventListener('scroll', update, { passive: true })
    const ro =
      typeof ResizeObserver !== 'undefined' ? new ResizeObserver(update) : null
    ro?.observe(viewport)
    return () => {
      viewport.removeEventListener('scroll', update)
      ro?.disconnect()
    }
  }, [chatScrollRef, sessionId, conversationTimeline])

  return (
    <div className="relative flex h-full min-h-0 min-w-0 flex-1 flex-col">
      {/* Top edge fade — hides when scrolled to the top. */}
      <div
        aria-hidden
        className={cn(
          'sandwalk-chat-edge-fade pointer-events-none absolute inset-x-0 top-0 z-10 h-5 bg-gradient-to-b from-background to-transparent transition-opacity duration-150',
          atTop ? 'opacity-0' : 'opacity-100'
        )}
      />
      {/* Bottom edge fade — hides when scrolled to the bottom. */}
      <div
        aria-hidden
        className={cn(
          'sandwalk-chat-edge-fade pointer-events-none absolute inset-x-0 bottom-0 z-10 h-5 bg-gradient-to-t from-background to-transparent transition-opacity duration-150',
          atBottom ? 'opacity-0' : 'opacity-100'
        )}
      />
      <ScrollArea
        ref={chatScrollRef}
        className="chat-scrollbar min-h-0 flex-1"
        data-transcript=""
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
                onToggleToolRunExpanded={stableToggleToolRunExpanded}
                runActive={runActive}
                tools={tools}
                runIdByMessageId={runIdByMessageId}
                usageByRunId={usageByRunId}
                lastMessageId={lastMessageId}
                copiedMessageId={copiedMessageId}
                setCopiedMessageId={setCopiedMessageId}
                session={session}
                onOpenFile={stableOpenFile}
                onBuildPlan={stableBuildPlan}
                onInterrupt={stableInterrupt}
                hiddenPlanPaths={hiddenPlanPaths}
                skills={skills}
                mcpServers={mcpServers}
                workspaceFiles={workspaceFiles}
                mentionChats={mentionChats}
                onResendMessage={onResendMessage}
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
                  mentionChats={mentionChats}
                  className="max-w-full space-y-3 [&_*]:max-w-full"
                />
              </div>
            ) : null}
            {runActive ? (
              <div className="mx-auto flex w-full max-w-[44rem] items-center px-2 py-2 text-sm">
                {pendingApproval ? (
                  <span className="animate-text-shimmer font-light">
                    Pending approval
                  </span>
                ) : liveStatus && !liveDelta ? (
                  <span
                    className="text-muted-foreground font-light"
                    data-testid="run-live-status"
                  >
                    {liveStatus}
                  </span>
                ) : (
                  <AgentStatusText
                    tools={statusTools}
                    liveDelta={liveDelta}
                  />
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
