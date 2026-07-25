import { Check, ChevronDown, Copy, RotateCcw } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { type AppErrorInfo, normalizeAppError } from '@/lib/app-error'
import { copyText } from '@/lib/clipboard'
import { cn } from '@/lib/utils'

function buildDump(error: AppErrorInfo): string {
  return [
    `title: ${error.title}`,
    `detail: ${error.detail}`,
    error.hint ? `hint: ${error.hint}` : null,
    error.status != null ? `status: ${error.status}` : null,
    error.name ? `name: ${error.name}` : null,
    '',
    '--- message ---',
    error.raw || '(empty)',
    error.stack ? `\n--- stack ---\n${error.stack}` : null
  ]
    .filter(line => line != null)
    .join('\n')
}

/**
 * Generic error UI for any page / fetch failure / render crash.
 * Pass any thrown value — it normalizes title, hint, raw message, and stack.
 */
export function ErrorPage({
  error,
  variant = 'page',
  className,
  onRetry,
  retryLabel = 'Try again',
  defaultDetailsOpen = false
}: {
  error: unknown | AppErrorInfo
  variant?: 'page' | 'panel' | 'inline'
  className?: string
  onRetry?: () => void
  retryLabel?: string
  /** Technical dump starts expanded. Default collapsed. */
  defaultDetailsOpen?: boolean
}) {
  const info =
    error &&
    typeof error === 'object' &&
    'title' in error &&
    'detail' in error &&
    'raw' in error
      ? (error as AppErrorInfo)
      : normalizeAppError(error)

  const [open, setOpen] = useState(defaultDetailsOpen)
  const [copied, setCopied] = useState(false)
  const dump = useMemo(() => buildDump(info), [info])
  const hasDetails = Boolean(info.raw || info.stack)

  async function copyDump() {
    try {
      await copyText(dump)
    } catch {
      // ignore
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  const body = (
    <div
      role="alert"
      className={cn(
        'border-border bg-muted/40 overflow-hidden rounded-lg border',
        variant === 'inline' && 'rounded-md',
        className
      )}
    >
      <div className={cn('px-3.5 py-3', variant === 'inline' && 'px-3 py-2.5')}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <p className="text-sm font-medium text-red-700 dark:text-red-400">
              {info.title}
              {info.status != null ? (
                <span className="text-muted-foreground ml-2 font-mono text-[11px] font-normal">
                  HTTP {info.status}
                </span>
              ) : null}
            </p>
            <p className="text-muted-foreground text-sm leading-relaxed">
              {info.detail}
            </p>
            {info.hint ? (
              <p className="text-muted-foreground/90 text-xs leading-relaxed">
                {info.hint}
              </p>
            ) : null}
          </div>
          {onRetry ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={onRetry}
            >
              <RotateCcw className="size-3.5" />
              {retryLabel}
            </Button>
          ) : null}
        </div>

        {hasDetails ? (
          <div className="mt-2.5">
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-[11px] font-medium"
                onClick={() => setOpen(value => !value)}
                aria-expanded={open}
              >
                <ChevronDown
                  className={cn(
                    'size-3.5 shrink-0 transition-transform',
                    open ? 'rotate-0' : '-rotate-90'
                  )}
                />
                Details
              </button>
              {open ? (
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-[11px]"
                  onClick={() => void copyDump()}
                >
                  {copied ? (
                    <Check className="size-3" />
                  ) : (
                    <Copy className="size-3" />
                  )}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              ) : null}
            </div>
            {open ? (
              <pre className="bg-background text-muted-foreground mt-2 max-h-40 overflow-auto rounded-md border px-3 py-2 font-mono text-[11px] leading-relaxed break-all whitespace-pre-wrap">
                {dump}
              </pre>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )

  if (variant === 'page') {
    return (
      <main className="bg-background grid min-h-full place-items-center p-6">
        <div className="w-full max-w-xl space-y-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Error</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              Something failed while loading this view.
            </p>
          </div>
          {body}
        </div>
      </main>
    )
  }

  return body
}
