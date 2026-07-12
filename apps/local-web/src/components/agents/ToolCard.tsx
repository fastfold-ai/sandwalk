import { Loader2, Square, Terminal } from 'lucide-react'

import { cn } from '@/lib/utils'

export type TranscriptTool = {
  id: string
  runId: string | null
  messageId: string | null
  name: string
  status: 'pending' | 'completed' | 'error'
  args?: unknown
  result?: unknown
  startedAt: string
  endedAt?: string
  durationSeconds?: number
}

function formatToolPayload(value: unknown) {
  if (value == null) return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export function formatToolExecutionTime(
  startedAt?: string,
  endedAt?: string,
  durationSeconds?: number
) {
  if (typeof durationSeconds === 'number' && Number.isFinite(durationSeconds)) {
    if (durationSeconds < 1) return '<1s'
    if (durationSeconds < 10) return `${durationSeconds.toFixed(1)}s`
    if (durationSeconds < 60) return `${Math.round(durationSeconds)}s`
    const minutes = Math.floor(durationSeconds / 60)
    const seconds = Math.round(durationSeconds % 60)
    return `${minutes}m ${seconds}s`
  }
  if (!startedAt || !endedAt) return null
  const elapsedMs = Date.parse(endedAt) - Date.parse(startedAt)
  if (!Number.isFinite(elapsedMs) || elapsedMs < 0) return null
  if (elapsedMs < 1000) return '<1s'
  const totalSeconds = elapsedMs / 1000
  if (totalSeconds < 10) return `${totalSeconds.toFixed(1)}s`
  if (totalSeconds < 60) return `${Math.round(totalSeconds)}s`
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = Math.round(totalSeconds % 60)
  return `${minutes}m ${seconds}s`
}

export function ToolCard({
  tool,
  isRunning = false,
  onStop
}: {
  tool: TranscriptTool
  isRunning?: boolean
  onStop?: () => void
}) {
  const executionTime = formatToolExecutionTime(
    tool.startedAt,
    tool.endedAt,
    tool.durationSeconds
  )
  const argsText = formatToolPayload(tool.args)
  const resultText = formatToolPayload(tool.result)
  const hasArgs = Boolean(argsText.trim())
  const hasResult = Boolean(resultText.trim())
  const previewSource = (hasResult ? resultText : argsText)
    .replace(/\s+/g, ' ')
    .trim()
  const previewText =
    previewSource.length > 96
      ? `${previewSource.slice(0, 96).trimEnd()}…`
      : previewSource

  return (
    <details
      open={tool.status === 'pending'}
      className="border-border/70 bg-muted/25 rounded-md border px-2 py-1"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 py-1 text-sm">
        <span className="flex min-w-0 items-center gap-2">
          <Terminal className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0">
            <span
              className={cn(
                'block truncate font-medium leading-none',
                tool.status === 'pending'
                  ? 'text-foreground animate-pulse'
                  : 'text-muted-foreground'
              )}
            >
              {tool.name}
            </span>
            {previewText ? (
              <span className="text-muted-foreground/70 block max-w-[36rem] truncate pt-0.5 text-xs">
                {previewText}
              </span>
            ) : null}
          </span>
        </span>
        <span className="text-muted-foreground flex shrink-0 items-center justify-end gap-2 text-xs">
          <span className="w-[48px] whitespace-nowrap text-right tabular-nums">
            {executionTime || ''}
          </span>
          <span className="flex h-3 w-3 items-center justify-center">
            {tool.status === 'pending' ? (
              <Loader2 className="text-muted-foreground h-2.5 w-2.5 animate-spin [animation-duration:1.8s]" />
            ) : tool.status === 'error' ? (
              <span className="h-1.5 w-1.5 rounded-full bg-red-500/70" />
            ) : null}
          </span>
          {tool.status === 'pending' && isRunning && onStop ? (
            <button
              type="button"
              className="border-border/70 bg-background/80 text-muted-foreground hover:bg-destructive/10 hover:text-destructive inline-flex h-5 items-center gap-1 rounded-sm border px-1.5 text-[10px] font-medium"
              onClick={event => {
                event.preventDefault()
                onStop()
              }}
            >
              <Square className="h-2.5 w-2.5 fill-current" />
              <span>Stop</span>
            </button>
          ) : null}
        </span>
      </summary>
      {hasArgs || hasResult ? (
        <div className="space-y-1 pb-1 pt-0.5">
          {hasArgs ? (
            <pre className="border-border/40 bg-background/60 text-muted-foreground max-h-32 overflow-auto whitespace-pre-wrap rounded-sm border px-2 py-1.5 font-mono text-xs">
              {argsText}
            </pre>
          ) : null}
          {hasResult ? (
            <pre className="border-border/40 bg-background/60 text-muted-foreground max-h-48 overflow-auto whitespace-pre-wrap rounded-sm border px-2 py-1.5 font-mono text-xs">
              {resultText}
            </pre>
          ) : null}
        </div>
      ) : null}
    </details>
  )
}
