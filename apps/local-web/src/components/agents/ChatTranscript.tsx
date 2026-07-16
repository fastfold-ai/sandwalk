import type {
  AgentMessage,
  AgentPlanCard,
  AgentSession,
  AgentTodo
} from '@sandwalk/agent-ui-core'
import { ArrowDown } from 'lucide-react'
import type { Dispatch, RefObject, SetStateAction } from 'react'
import { useMemo } from 'react'

import { BuildPlanStatusCard } from '@/components/agents/BuildPlanStatusCard'
import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { TodoListInline } from '@/components/agents/TodoListInline'
import { ToolCard, type TranscriptTool } from '@/components/agents/ToolCard'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { buildChatTimelineItems } from '@/components/agents/chat-transcript-timeline'
import { ChatTranscriptTimelineItem } from '@/components/agents/chat-transcript-timeline-item'
import { ScrollArea } from '@/components/ui/scroll-area'

type ChatTranscriptProps = {
  chatScrollRef: RefObject<HTMLDivElement | null>
  chatEndRef: RefObject<HTMLDivElement | null>
  conversationTimeline: TranscriptEntry[]
  expandedToolRunKeys: Record<string, boolean>
  sessionId: string | null
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
  showScrollToBottom: boolean
  onScrollToBottom: () => void
}

export function ChatTranscript({
  chatScrollRef,
  chatEndRef,
  conversationTimeline,
  expandedToolRunKeys,
  sessionId,
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
  showScrollToBottom,
  onScrollToBottom
}: ChatTranscriptProps) {
  const timelineItems = useMemo(
    () => buildChatTimelineItems(conversationTimeline),
    [conversationTimeline]
  )
  const hiddenPlanPaths = useMemo(() => {
    const paths = new Set(builtPlanPaths)
    if (activeBuildPlan?.path) paths.add(activeBuildPlan.path)
    return paths
  }, [activeBuildPlan?.path, builtPlanPaths])

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
              />
            ))}
            {runActive && activeBuildPlan ? (
              <div className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150">
                <BuildPlanStatusCard
                  plan={activeBuildPlan}
                  todos={activeRunTodos}
                  runActive={runActive}
                />
              </div>
            ) : null}
            {activeRunTools.length > 0 ? (
              <div className="space-y-1">
                {activeRunTools.map(tool => (
                  <div
                    key={`active-${tool.id}`}
                    className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                  >
                    <ToolCard
                      tool={tool}
                      isRunning={runActive}
                      onStop={onInterrupt}
                    />
                  </div>
                ))}
              </div>
            ) : null}
            {activeRunTodos.length > 0 && !activeBuildPlan ? (
              <div className="mx-auto w-full max-w-[44rem] px-2">
                <TodoListInline todos={activeRunTodos} />
              </div>
            ) : null}
            {liveDelta ? (
              <div className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150">
                <MarkdownContent
                  content={liveDelta}
                  streaming
                  className="max-w-full [&_*]:max-w-full"
                />
              </div>
            ) : null}
            {runActive && !liveDelta ? (
              <div className="text-muted-foreground mx-auto flex w-full max-w-[44rem] items-center gap-1 px-2 py-2 text-sm">
                <div className="bg-foreground/80 animate-breathe h-2.5 w-2.5 rounded-full" />
                <span className="sr-only">Generating</span>
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
