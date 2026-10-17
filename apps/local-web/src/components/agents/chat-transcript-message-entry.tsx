import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  AgentSkill,
  McpServer,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import {
  Check,
  Copy,
  Download,
  MoreHorizontal,
  Pencil
} from 'lucide-react'
import { type Dispatch, type SetStateAction, useEffect, useRef, useState } from 'react'

import { ConnectorMessageCard } from '@/components/agents/ConnectorMessageCard'
import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { UserMessageContent } from '@/components/agents/UserMessageContent'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { copyText } from '@/lib/clipboard'
import { perfCount } from '@/lib/perf-probe'
import {
  downloadMarkdown,
  formatMessagePopoverDate,
  type RunTokenUsage
} from '@/lib/sessions'
import { cn } from '@/lib/utils'

function formatSeconds(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return null
  if (value < 1) return `${Math.round(value * 1000)}ms`
  return `${value.toFixed(2)}s`
}

function formatTokPerSec(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value) || value <= 0) return null
  return `${value.toFixed(1)} tok/s`
}

export function ChatTranscriptMessageEntry({
  entry,
  runActive,
  runIdByMessageId,
  usageByRunId,
  lastMessageId,
  copiedMessageId,
  setCopiedMessageId,
  session,
  onOpenFile,
  client,
  sessionId,
  skills = [],
  mcpServers = [],
  workspaceFiles = [],
  mentionChats = [],
  onResendMessage
}: {
  entry: Extract<TranscriptEntry, { kind: 'message' }>
  runActive: boolean
  runIdByMessageId: Record<string, string>
  usageByRunId: Record<string, RunTokenUsage>
  lastMessageId: string | undefined
  copiedMessageId: string | null
  setCopiedMessageId: Dispatch<SetStateAction<string | null>>
  session: AgentSession | null | undefined
  onOpenFile: (path: string) => void
  client?: LocalAgentClient | null
  sessionId?: string | null
  skills?: AgentSkill[]
  mcpServers?: McpServer[]
  workspaceFiles?: WorkspaceFile[]
  mentionChats?: AgentSession[]
  /**
   * Send an edited copy of a user message as a new turn. The original stays
   * in the transcript; if a run is active it is stopped first.
   */
  onResendMessage?: (text: string) => void | Promise<void>
}) {
  perfCount('render.MessageEntry')
  const message = entry.message
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'
  const messagePopoverDate = formatMessagePopoverDate(message.createdAt)
  const messageRunId = runIdByMessageId[message.id] || null
  const messageUsage = (messageRunId && usageByRunId[messageRunId]) || null
  const hideActionsWhileStreaming =
    runActive && isAssistant && message.id === lastMessageId

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(message.content)
  const editorRef = useRef<HTMLTextAreaElement | null>(null)
  useEffect(() => {
    if (!editing) return
    const node = editorRef.current
    if (!node) return
    node.focus()
    node.setSelectionRange(node.value.length, node.value.length)
    node.style.height = 'auto'
    node.style.height = `${Math.min(node.scrollHeight, 320)}px`
  }, [editing])
  const canResend = Boolean(onResendMessage) && isUser && !message.source
  const submitEdit = () => {
    const text = draft.trim()
    if (!text || !onResendMessage) return
    setEditing(false)
    void onResendMessage(text)
  }

  return (
    <div
      className={cn(
        'fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] duration-150',
        isUser ? 'flex justify-end px-2' : ''
      )}
    >
      {isUser && message.source ? (
        <div className="relative min-w-0 max-w-[85%]">
          <ConnectorMessageCard
            source={message.source}
            createdAt={message.createdAt}
          />
        </div>
      ) : isUser && editing ? (
        <div
          className="bg-muted text-foreground w-full max-w-[85%] rounded-xl px-4 pb-2 pt-3"
          data-testid="user-message-editor"
        >
          <textarea
            ref={editorRef}
            value={draft}
            onChange={event => {
              setDraft(event.target.value)
              const node = event.target
              node.style.height = 'auto'
              node.style.height = `${Math.min(node.scrollHeight, 320)}px`
            }}
            onKeyDown={event => {
              if (event.key === 'Escape') {
                event.preventDefault()
                setEditing(false)
                setDraft(message.content)
              } else if (
                event.key === 'Enter' &&
                (event.metaKey || event.ctrlKey)
              ) {
                event.preventDefault()
                submitEdit()
              }
            }}
            className="placeholder:text-muted-foreground w-full resize-none bg-transparent text-sm leading-relaxed outline-none"
            aria-label="Edit message"
            rows={1}
          />
          <div className="mt-2 flex items-center justify-end gap-2">
            <button
              type="button"
              className="hover:bg-background/60 rounded-md px-3 py-1 text-xs"
              onClick={() => {
                setEditing(false)
                setDraft(message.content)
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="bg-foreground text-background rounded-md px-3 py-1 text-xs font-medium disabled:opacity-50"
              disabled={!draft.trim()}
              onClick={submitEdit}
              title="Send as a new message (⌘↩)"
            >
              {runActive ? 'Stop & send' : 'Send'}
            </button>
          </div>
        </div>
      ) : isUser ? (
        <div className="group/user relative min-w-0 max-w-[85%]">
          <div className="bg-muted text-foreground peer inline-block w-auto max-w-full break-words rounded-xl px-4 py-2">
            <UserMessageContent
              content={entry.content}
              onOpenFile={onOpenFile}
              client={client}
              sessionId={sessionId}
              workspacePath={session?.workspacePath}
              workspaceFiles={workspaceFiles}
              skills={skills}
              mcpServers={mcpServers}
              mentionChats={mentionChats}
            />
          </div>
          <div className="text-muted-foreground -mb-7 mt-1 flex min-h-6 items-center justify-end gap-0.5 opacity-0 transition-opacity group-hover/user:opacity-100 focus-within:opacity-100">
            <button
              type="button"
              className="hover:bg-muted hover:text-foreground inline-flex h-6 w-6 items-center justify-center rounded-md"
              onClick={async () => {
                await copyText(message.content)
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
            {canResend ? (
              <button
                type="button"
                className="hover:bg-muted hover:text-foreground inline-flex h-6 w-6 items-center justify-center rounded-md"
                onClick={() => {
                  setDraft(message.content)
                  setEditing(true)
                }}
                aria-label="Edit and resend"
                title="Edit and send as a new message"
              >
                <Pencil className="size-3.5" />
              </button>
            ) : null}
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
              skills={skills}
              mentionChats={mentionChats}
              className="max-w-full [&_*]:max-w-full [&_pre]:w-full [&_pre]:max-w-full [&_pre_code]:whitespace-pre-wrap [&_table]:w-full [&_table]:table-auto"
            />
          ) : null}
          {isAssistant && entry.content && !hideActionsWhileStreaming ? (
            <div className="text-muted-foreground -mb-7.5 min-h-7.5 -ml-1 flex items-center gap-0.5 pt-1.5">
              <button
                type="button"
                className="hover:bg-muted hover:text-foreground inline-flex h-6 w-6 items-center justify-center rounded-md"
                onClick={async () => {
                  await copyText(message.content)
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
              {formatTokPerSec(messageUsage?.tokensPerSecond) ? (
                <span className="text-muted-foreground px-1.5 font-mono text-[11px] tabular-nums">
                  {formatTokPerSec(messageUsage?.tokensPerSecond)}
                </span>
              ) : null}
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
                    {messageUsage?.estimated ? (
                      <div className="text-muted-foreground/80 mt-0.5 text-[10px]">
                        Estimated (provider omitted usage)
                      </div>
                    ) : null}
                    {formatTokPerSec(messageUsage?.tokensPerSecond) ? (
                      <div className="mt-0.5 flex items-center justify-between gap-3">
                        <span>Speed</span>
                        <span className="text-foreground">
                          {formatTokPerSec(messageUsage?.tokensPerSecond)}
                        </span>
                      </div>
                    ) : null}
                    {formatSeconds(messageUsage?.promptEvalSeconds) ? (
                      <div className="mt-0.5 flex items-center justify-between gap-3">
                        <span>Prompt eval</span>
                        <span className="text-foreground">
                          {formatSeconds(messageUsage?.promptEvalSeconds)}
                        </span>
                      </div>
                    ) : null}
                    {formatSeconds(messageUsage?.generationSeconds) ? (
                      <div className="mt-0.5 flex items-center justify-between gap-3">
                        <span>Generation</span>
                        <span className="text-foreground">
                          {formatSeconds(messageUsage?.generationSeconds)}
                        </span>
                      </div>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                    onClick={() => {
                      void downloadMarkdown(
                        `${session?.title || 'assistant-reply'}-${message.id.slice(0, 8)}.md`,
                        message.content
                      )
                    }}
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
