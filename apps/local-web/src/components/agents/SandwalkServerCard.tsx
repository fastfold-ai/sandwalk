import { Check, CircleHelp, Copy, Terminal } from 'lucide-react'
import { type ReactNode, useState } from 'react'

import { SandwalkMark } from '@/components/SandwalkMark'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

const MANAGE_COMMANDS = [
  {
    id: 'serve',
    title: 'Start the server',
    command: 'sandwalk serve',
    description: 'Runs the sandwalk API (default http://127.0.0.1:8787).'
  },
  {
    id: 'status',
    title: 'Check auth / settings',
    command: 'sandwalk auth status',
    description: 'Shows whether API-key auth is enabled on the server.'
  }
] as const

function CommandRow({
  command,
  copied,
  onCopy
}: {
  command: string
  copied: boolean
  onCopy: () => void
}) {
  return (
    <div className="bg-muted/60 border-border flex items-center gap-2 rounded-lg border p-2.5">
      <Terminal className="text-muted-foreground size-4 shrink-0" />
      <code className="text-foreground min-w-0 flex-1 truncate font-mono text-[13px]">
        {command}
      </code>
      <button
        type="button"
        className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-7 shrink-0 items-center justify-center rounded-md transition-colors"
        onClick={onCopy}
        aria-label={`Copy ${command}`}
        title="Copy command"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </button>
    </div>
  )
}

function MacAppIcon({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'flex size-11 shrink-0 items-center justify-center rounded-[11px] bg-white p-2 shadow-[0_1px_2px_rgba(0,0,0,0.12)] ring-1 ring-black/5',
        className
      )}
      aria-hidden
    >
      <img src="/sandwalk-mark.svg" alt="" className="size-full" />
    </div>
  )
}

export function SandwalkServerCard({
  version,
  running,
  subtitle,
  compact = false,
  flat = false,
  title,
  trailing
}: {
  version?: string | null
  running: boolean
  subtitle: string
  /** Dense card for menus / tight layouts (no Help). */
  compact?: boolean
  /** Compact without chrome (no mark, no card background). */
  flat?: boolean
  /** Optional primary line above the Sandwalk status (e.g. user name). */
  title?: string | null
  trailing?: ReactNode
}) {
  const [helpOpen, setHelpOpen] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const copyCommand = (id: string, command: string) => {
    void navigator.clipboard.writeText(command)
    setCopiedId(id)
    window.setTimeout(() => {
      setCopiedId(current => (current === id ? null : current))
    }, 2000)
  }

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

      <Dialog
        open={helpOpen}
        onOpenChange={open => {
          setHelpOpen(open)
          if (!open) setCopiedId(null)
        }}
      >
        <DialogTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-muted-foreground shrink-0"
          >
            <CircleHelp className="size-3.5" />
            Help
          </Button>
        </DialogTrigger>
        <DialogContent className="bg-card text-card-foreground border-border flex max-h-[min(90vh,44rem)] max-w-2xl flex-col gap-0 overflow-hidden rounded-2xl p-0 shadow-xl sm:rounded-2xl">
          <DialogHeader className="shrink-0 space-y-2 px-6 pt-6 pb-2 text-left">
            <DialogTitle className="text-lg font-semibold">
              How to manage sandwalk
            </DialogTitle>
          </DialogHeader>

          <ScrollArea className="h-[min(55vh,28rem)] px-6">
            <div className="space-y-4 py-2 pr-3">
              <div className="bg-muted/50 border-border rounded-xl border px-3.5 py-3">
                <div className="flex items-start gap-3">
                  <MacAppIcon />
                  <div className="min-w-0 flex-1">
                    <p className="text-foreground text-sm font-semibold">
                      Mac app
                    </p>
                    <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
                      Use the sandwalk menubar icon →{' '}
                      <span className="text-foreground font-medium">Start</span>
                      ,{' '}
                      <span className="text-foreground font-medium">Stop</span>,
                      or{' '}
                      <span className="text-foreground font-medium">
                        Restart
                      </span>
                      . That supervises the API and this web UI together when
                      you run sandwalk from the app.
                    </p>
                  </div>
                </div>
              </div>

              <div>
                <p className="text-foreground mb-3 text-sm font-semibold">
                  CLI commands
                </p>
                <div className="space-y-3.5">
                  {MANAGE_COMMANDS.map(item => (
                    <div key={item.id}>
                      <p className="text-muted-foreground mb-1.5 text-xs font-medium">
                        {item.title}
                      </p>
                      <CommandRow
                        command={item.command}
                        copied={copiedId === item.id}
                        onCopy={() => copyCommand(item.id, item.command)}
                      />
                      <p className="text-muted-foreground mt-1.5 text-xs">
                        {item.description}
                      </p>
                    </div>
                  ))}
                </div>
                <p className="text-muted-foreground mt-3 text-xs leading-relaxed">
                  To stop a CLI-started server, interrupt the terminal with
                  Ctrl+C, or quit / stop from the menubar if it is supervising
                  the process. The dashboard connects to whatever host you
                  configure — local or remote.
                </p>
              </div>
            </div>
          </ScrollArea>

          <DialogFooter className="shrink-0 px-6 pt-2 pb-5 sm:justify-end">
            <button
              type="button"
              className="bg-primary text-primary-foreground h-10 rounded-lg px-4 text-sm font-semibold transition-opacity hover:opacity-90"
              onClick={() => setHelpOpen(false)}
            >
              Got it
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
