import { type ReactNode } from 'react'

import { SandwalkMark } from '@/components/SandwalkMark'
import { cn } from '@/lib/utils'

import { SandwalkServerHelpDialog } from './sandwalk-server-help-dialog'

export function SandwalkServerCard({
  version,
  running,
  subtitle,
  compact = false,
  flat = false,
  title,
  trailing,
  actions
}: {
  version?: string | null
  running: boolean
  subtitle: string
  compact?: boolean
  flat?: boolean
  title?: string | null
  trailing?: ReactNode
  /** Extra controls rendered beside Help (non-compact card). */
  actions?: ReactNode
}) {
  const statusBadge = (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full font-medium',
        compact
          ? 'gap-1 px-1.5 py-0 text-[10px] leading-4'
          : 'gap-1.5 px-2 py-0.5 text-xs',
        running
          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
          : 'bg-destructive/15 text-destructive'
      )}
    >
      <span
        className={cn(
          'rounded-full',
          compact ? 'size-1' : 'size-1.5',
          running && 'sandwalk-presence-dot',
          running ? 'bg-emerald-500' : 'bg-destructive'
        )}
      />
      {running ? 'Running' : 'Stopped'}
    </span>
  )

  if (compact) {
    const titleText = title?.trim() || null
    return (
      <div
        className={cn(
          'flex w-full min-w-0 items-center gap-2',
          flat
            ? 'px-1.5 py-1'
            : 'bg-muted/50 hover:bg-muted/70 rounded-lg border px-2.5 py-2 transition-colors'
        )}
      >
        {flat ? null : (
          <div className="bg-background text-foreground grid size-7 shrink-0 place-items-center rounded-md border shadow-sm">
            <SandwalkMark className="h-3.5 w-3.5" />
          </div>
        )}
        <div className="min-w-0 flex-1 space-y-0.5">
          {titleText ? (
            <div className="flex min-w-0 items-center gap-1.5">
              <span className="break-all text-sm font-semibold leading-tight">
                {titleText}
              </span>
            </div>
          ) : null}
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <span
              className={cn(
                'truncate tracking-tight',
                titleText
                  ? 'text-muted-foreground text-xs font-medium'
                  : 'text-xs font-semibold'
              )}
            >
              sandwalk{version ? ` ${version}` : ''}
            </span>
            {statusBadge}
          </div>
          <p className="text-muted-foreground truncate text-[11px] leading-tight">
            {subtitle}
          </p>
        </div>
        {trailing ? (
          <div className="text-muted-foreground shrink-0 self-start pt-0.5">
            {trailing}
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <section className="bg-muted/50 flex flex-wrap items-center gap-4 rounded-2xl border px-4 py-4">
      <div className="bg-background text-foreground grid size-11 shrink-0 place-items-center rounded-xl border shadow-sm">
        <SandwalkMark className="h-6 w-6" />
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold tracking-tight">
            sandwalk{version ? ` ${version}` : ''}
          </h3>
          {statusBadge}
        </div>
        <p className="text-muted-foreground text-sm">{subtitle}</p>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-1">
        {actions}
        <SandwalkServerHelpDialog />
      </div>
    </section>
  )
}

export function listenSubtitle(options: {
  running: boolean
  host?: string | null
  port?: number | string | null
  message?: string | null
  backendUrl?: string | null
}): string {
  if (options.message?.trim()) return options.message.trim()
  if (!options.running) return 'Server is not running'
  if (options.host && options.port != null && options.port !== '') {
    return `Listening on ${options.host}:${options.port}`
  }
  const raw = options.backendUrl?.trim()
  if (raw) {
    try {
      const url = new URL(raw)
      const host = url.hostname || '127.0.0.1'
      const port =
        url.port ||
        (url.protocol === 'https:' ? '443' : url.protocol === 'http:' ? '80' : '')
      return port ? `Listening on ${host}:${port}` : `Listening on ${host}`
    } catch {
      return `Listening on ${raw}`
    }
  }
  return 'Listening'
}
