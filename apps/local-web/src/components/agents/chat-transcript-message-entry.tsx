import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentMessage, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Check,
  Copy,
  Download,
  MoreHorizontal
} from 'lucide-react'
import type { Dispatch, SetStateAction } from 'react'

import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { UserMessageContent } from '@/components/agents/UserMessageContent'
import { type TranscriptEntry } from '@/components/agents/transcript'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { downloadMarkdown, formatMessagePopoverDate } from '@/lib/sessions'
import { cn } from '@/lib/utils'

export function ChatTranscriptMessageEntry({
  entry,
  runActive,
  runIdByMessageId,
  usageByRunId,
  messages,
  copiedMessageId,
  setCopiedMessageId,
  session,
  onOpenFile,
  client,
  sessionId
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
  client?: LocalAgentClient | null
  sessionId?: string | null
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
            <UserMessageContent
              content={entry.content}
              onOpenFile={onOpenFile}
              client={client}
              sessionId={sessionId}
              workspacePath={session?.workspacePath}
            />
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
              onOpenFile={onOpenFile}
              workspacePath={session?.workspacePath}
              className="max-w-full [&_*]:max-w-full [&_pre]:w-full [&_pre]:max-w-full [&_pre_code]:whitespace-pre-wrap [&_table]:w-full [&_table]:table-auto"
            />
          ) : null}
          {isAssistant && entry.content && !hideActionsWhileStreaming ? (
            <div className="text-muted-foreground -mb-7.5 min-h-7.5 -ml-1 flex items-center gap-0.5 pt-1.5">
              <button
                type="button"
                className="hover:bg-muted hover:text-foreground inline-flex h-6 w-6 items-center justify-center rounded-md"
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
                    className="hover:bg-muted hover:text-foreground inline-flex h-6 w-6 items-center justify-center rounded-md"
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
