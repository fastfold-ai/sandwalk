import type { AgentMessage, AgentSession } from '@sandwalk/agent-ui-core'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { Dispatch, SetStateAction } from 'react'

import { ReasoningGhost } from '@/components/agents/ReasoningGhost'
import { TodoListInline } from '@/components/agents/TodoListInline'
import { ToolCard, type TranscriptTool } from '@/components/agents/ToolCard'
import { ChatTranscriptMessageEntry } from '@/components/agents/chat-transcript-message-entry'
import {
  thoughtDurationForTools,
  TOOL_RUN_VISIBLE_COUNT
} from '@/components/agents/transcript'
import { type ChatTimelineItem } from '@/components/agents/chat-transcript-timeline'

type TimelineItemProps = {
  timelineItem: ChatTimelineItem
  sessionId: string | null
  expandedToolRunKeys: Record<string, boolean>
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
  onInterrupt: (() => void) | undefined
}

export function ChatTranscriptTimelineItem({
  timelineItem,
  sessionId,
  expandedToolRunKeys,
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
  onInterrupt
}: TimelineItemProps) {
  if (timelineItem.kind === 'tool_run') {
    const isExpanded = expandedToolRunKeys[timelineItem.key] === true
    const visibleTools = isExpanded
      ? timelineItem.tools
      : timelineItem.tools.slice(-TOOL_RUN_VISIBLE_COUNT)
    const hiddenCount = Math.max(
      0,
      timelineItem.tools.length - TOOL_RUN_VISIBLE_COUNT
    )
    return (
      <div key={timelineItem.key} className="space-y-1">
        {hiddenCount > 0 ? (
          <div className="mx-auto w-full max-w-[44rem] px-2">
            <button
              type="button"
              className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-xs"
              onClick={() => {
                if (!sessionId) return
                onToggleToolRunExpanded(timelineItem.key)
              }}
            >
              {isExpanded ? (
                <ChevronDown className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
              ) : (
                <ChevronRight className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
              )}
              <span>
                {isExpanded ? 'Show less' : `Show more (${hiddenCount})`}
              </span>
            </button>
          </div>
        ) : null}
        {visibleTools.map(tool => (
          <div
            key={tool.id}
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
    )
  }

  const entry = timelineItem.entry
  if (entry.kind === 'thought') {
    const turnTools = tools.filter(
      tool =>
        tool.messageId === entry.message.id ||
        (runIdByMessageId[entry.message.id] &&
          tool.runId === runIdByMessageId[entry.message.id])
    )
    const duration = thoughtDurationForTools(turnTools)
    return (
      <div
        key={timelineItem.key}
        className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
      >
        <ReasoningGhost
          id={entry.message.id}
          label={duration ? `Thought for ${duration}` : 'Thought'}
          thought={entry.thought}
        />
      </div>
    )
  }

  if (entry.kind === 'tool') {
    return (
      <div
        key={timelineItem.key}
        className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
      >
        <ToolCard tool={entry.tool} isRunning={runActive} onStop={onInterrupt} />
      </div>
    )
  }

  if (entry.kind === 'todos') {
    return (
      <div
        key={timelineItem.key}
        className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
      >
        <TodoListInline todos={entry.todos} className="mt-1" />
      </div>
    )
  }

  return (
    <ChatTranscriptMessageEntry
      key={timelineItem.key}
      entry={entry}
      runActive={runActive}
      runIdByMessageId={runIdByMessageId}
      usageByRunId={usageByRunId}
      messages={messages}
      copiedMessageId={copiedMessageId}
      setCopiedMessageId={setCopiedMessageId}
      session={session}
      onOpenFile={onOpenFile}
    />
  )
}
