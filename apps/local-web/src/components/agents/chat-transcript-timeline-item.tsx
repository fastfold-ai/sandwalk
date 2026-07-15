import type { AgentMessage, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  MoreHorizontal
} from 'lucide-react'
import type { Dispatch, SetStateAction } from 'react'

import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { ReasoningGhost } from '@/components/agents/ReasoningGhost'
import { TodoListInline } from '@/components/agents/TodoListInline'
import { ToolCard, type TranscriptTool } from '@/components/agents/ToolCard'
import {
  thoughtDurationForTools,
  TOOL_RUN_VISIBLE_COUNT,
  type TranscriptEntry
} from '@/components/agents/transcript'
import { UserMessageContent } from '@/components/agents/UserMessageContent'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { downloadMarkdown, formatMessagePopoverDate } from '@/lib/sessions'
import { cn } from '@/lib/utils'

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

function ChatTranscriptMessageEntry({
  entry,
  runActive,
  runIdByMessageId,
  usageByRunId,
  messages,
  copiedMessageId,
  setCopiedMessageId,
  session,
  onOpenFile
}: {
  entry: Extract<TranscriptEntry, { kind: 'message' }>
  runActive: boolean
  runIdByMessageId: Record<string, string>
  usageByRunId: Record<string, { inputTokens: number; outputTokens: number }>
  messages: AgentMessage[]
  copiedMessageId: string | null
  setCopiedMessageId: Dispatch<SetStateAction<string | null>>
  session: AgentSession | null | undefined
  onOpenFile: (path: string) => void
}) {
  const message = entry.message
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'
  const messagePopoverDate = formatMessagePopoverDate(message.createdAt)
  const messageRunId = runIdByMessageId[message.id] || null
  const messageUsage = (messageRunId && usageByRunId[messageRunId]) || null
  const hideActionsWhileStreaming =
    runActive && isAssistant && message.id === messages.at(-1)?.id

  return (
    <div
      className={cn(
        'fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] duration-150',
        isUser ? 'flex justify-end px-2' : ''
      )}
    >
      {isUser ? (
        <div className="relative min-w-0 max-w-[85%]">
          <div className="bg-muted text-foreground peer inline-block w-auto max-w-full break-words rounded-xl px-4 py-2">
            <UserMessageContent content={entry.content} onOpenFile={onOpenFile} />
          </div>
        </div>
      ) : (
        <div
          className={cn(
            'text-foreground min-w-0 break-words px-2 leading-relaxed',
            message.role === 'system' &&
              'border-border/70 text-muted-foreground rounded-xl border'
          )}
        >
          {entry.content.trim() ? (
            <MarkdownContent
              content={entry.content}
              streaming={hideActionsWhileStreaming}
              className="max-w-full [&_*]:max-w-full [&_pre]:w-full [&_pre]:max-w-full [&_pre_code]:whitespace-pre-wrap [&_table]:w-full [&_table]:table-auto"
            />
          ) : null}
          {isAssistant && entry.content && !hideActionsWhileStreaming ? (
            <div className="text-zinc-300 dark:text-zinc-600 -mb-7.5 min-h-7.5 -ml-1 flex items-center gap-0.5 pt-1.5">
              <button
                type="button"
                className="hover:bg-muted hover:text-zinc-400 dark:hover:text-zinc-500 inline-flex h-6 w-6 items-center justify-center rounded-md"
                onClick={async () => {
                  await navigator.clipboard.writeText(message.content)
                  setCopiedMessageId(message.id)
                  window.setTimeout(() => {
                    setCopiedMessageId(current =>
                      current === message.id ? null : current
                    )
                  }, 1200)
                }}
                aria-label="Copy message"
              >
                {copiedMessageId === message.id ? (
                  <Check className="size-3.5" />
                ) : (
                  <Copy className="size-3.5" />
                )}
              </button>
              <Popover>
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    className="hover:bg-muted hover:text-zinc-400 dark:hover:text-zinc-500 inline-flex h-6 w-6 items-center justify-center rounded-md"
                    aria-label="More actions"
                  >
                    <MoreHorizontal className="size-3.5" />
                  </button>
                </PopoverTrigger>
                <PopoverContent align="start" className="w-48 p-1.5">
                  {messagePopoverDate ? (
                    <div className="text-muted-foreground border-border/50 mb-1 border-b px-2 pb-1.5 pt-1 text-xs">
                      {messagePopoverDate}
                    </div>
                  ) : null}
                  <div className="text-muted-foreground border-border/50 mb-1 border-b px-2 pb-1.5 pt-1 text-xs tabular-nums">
                    <div className="flex items-center justify-between gap-3">
                      <span>↑ Input</span>
                      <span className="text-foreground">
                        {(messageUsage?.inputTokens ?? 0).toLocaleString()}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center justify-between gap-3">
                      <span>↓ Output</span>
                      <span className="text-foreground">
                        {(messageUsage?.outputTokens ?? 0).toLocaleString()}
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                    onClick={() =>
                      downloadMarkdown(
                        `${session?.title || 'assistant-reply'}-${message.id.slice(0, 8)}.md`,
                        message.content
                      )
                    }
                  >
                    <Download className="size-4" />
                    Export Markdown
                  </button>
                </PopoverContent>
              </Popover>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
