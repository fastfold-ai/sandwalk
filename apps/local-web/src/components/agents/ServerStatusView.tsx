import type { ServerCacheInfo, ServerStatusReport } from '@sandwalk/agent-ui-core'
import {
  Check,
  CircleHelp,
  Copy,
  Loader2,
  Terminal
} from 'lucide-react'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { toast } from 'sonner'

import { SettingsBlockSkeleton } from '@/components/agents/PageSkeletons'
import { SandwalkMark } from '@/components/SandwalkMark'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
    description: 'Runs the local API (default http://127.0.0.1:8787).'
  },
  {
    id: 'status',
    title: 'Check auth / settings',
    command: 'sandwalk auth status',
    description: 'Shows whether API-key auth is enabled on this machine.'
  }
] as const

function formatBytes(bytes: number): string {
  const value = Math.max(0, bytes)
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB'] as const
  let n = value / 1024
  for (let i = 0; i < units.length; i += 1) {
    if (n < 1024 || i === units.length - 1) {
      return `${n.toFixed(1)} ${units[i]}`
    }
    n /= 1024
  }
  return `${value} B`
}

function formatUptime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (days > 0) return `${days}d ${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m ${secs}s`
  return `${secs}s`
}

function formatGpuLabel(chipName?: string | null, gpuCores?: number | null): string | null {
  const chip = chipName?.trim()
  const cores = gpuCores != null && gpuCores > 0 ? gpuCores : null
  if (chip && cores != null) return `${chip} · ${cores} cores`
  if (chip) return chip
  if (cores != null) return `${cores} cores`
  return null
}

function MemoryBar({ used, total }: { used: number; total: number }) {
  const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0
  return (
    <div className="flex min-w-[8rem] flex-1 items-center gap-3 sm:min-w-[12rem]">
      <div className="bg-muted h-1.5 flex-1 overflow-hidden rounded-full">
        <div
          className="bg-foreground/70 h-full rounded-full transition-[width] duration-300"
          style={{ width: `${Math.max(pct, pct > 0 ? 0.8 : 0)}%` }}
        />
      </div>
      <span className="text-muted-foreground shrink-0 text-sm tabular-nums">
        {formatBytes(used)} / {formatBytes(total)}
      </span>
    </div>
  )
}

function SectionLabel({
  children,
  subtitle
}: {
  children: ReactNode
  subtitle?: string
}) {
  return (
    <div className="mb-2 space-y-1">
      <div className="text-muted-foreground text-[11px] font-medium tracking-wider uppercase">
        {children}
      </div>
      {subtitle ? (
        <p className="text-muted-foreground text-sm">{subtitle}</p>
      ) : null}
    </div>
  )
}

function MetaRow({
  label,
  children,
  hint,
  stretch
}: {
  label: string
  children: ReactNode
  hint?: string
  stretch?: boolean
}) {
  return (
    <div
      className={cn(
        'flex gap-4 border-b border-border/60 py-3.5 last:border-b-0',
        stretch ? 'items-center' : 'items-start justify-between'
      )}
    >
      <div className="min-w-[7.5rem] shrink-0">
        <div className="text-sm font-medium">{label}</div>
        {hint ? (
          <div className="text-muted-foreground mt-0.5 text-xs">{hint}</div>
        ) : null}
      </div>
      <div
        className={cn(
          'text-muted-foreground text-sm',
          stretch ? 'min-w-0 flex-1' : 'max-w-[min(100%,20rem)] text-right'
        )}
      >
        {children}
      </div>
    </div>
  )
}

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
    <div className="border-border/80 bg-muted/35 flex items-center gap-2 rounded-lg border p-2.5">
      <Terminal className="text-muted-foreground size-4 shrink-0" />
      <code className="min-w-0 flex-1 truncate font-mono text-[13px]">
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

export function ServerStatusView({
  onLoad,
  onClearCache
}: {
  onLoad: (signal?: AbortSignal) => Promise<ServerStatusReport>
  onClearCache: (signal?: AbortSignal) => Promise<ServerCacheInfo>
}) {
  const [report, setReport] = useState<ServerStatusReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [clearing, setClearing] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true)
      setError(null)
      try {
        const next = await onLoad(signal)
        if (signal?.aborted) return
        setReport(next)
      } catch (err) {
        if (signal?.aborted) return
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [onLoad]
  )

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const copyCommand = (id: string, command: string) => {
    void navigator.clipboard.writeText(command)
    setCopiedId(id)
    window.setTimeout(() => {
      setCopiedId(current => (current === id ? null : current))
    }, 2000)
  }

  const clearCache = async () => {
    setConfirmClear(false)
    setClearing(true)
    setError(null)
    try {
      const cache = await onClearCache()
      setReport(current => (current ? { ...current, cache } : current))
      toast.success('Runtime cache cleared')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setClearing(false)
    }
  }

  const running = report?.status === 'running'
  const gpuLabel = formatGpuLabel(report?.system.chipName, report?.system.gpuCores)

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-3xl space-y-10 px-8 py-10">
        <h2 className="text-2xl font-semibold">Status</h2>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        {loading && !report ? (
          <>
            <div className="bg-muted/40 rounded-xl border px-4 py-4">
              <SettingsBlockSkeleton />
            </div>
            <section>
              <SectionLabel>System</SectionLabel>
              <div className="bg-background rounded-2xl border px-4 py-2">
                <SettingsBlockSkeleton />
              </div>
            </section>
          </>
        ) : report ? (
          <>
            <section className="bg-muted/50 flex flex-wrap items-center gap-4 rounded-2xl border px-4 py-4">
              <div className="bg-background text-foreground grid size-11 shrink-0 place-items-center rounded-xl border shadow-sm">
                <SandwalkMark className="h-6 w-6" />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold tracking-tight">
                    Sandwalk {report.version}
                  </h3>
                  <span
                    className={cn(
                      'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
                      running
                        ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
                        : 'bg-destructive/15 text-destructive'
                    )}
                  >
                    <span
                      className={cn(
                        'size-1.5 rounded-full',
                        running ? 'bg-emerald-500' : 'bg-destructive'
                      )}
                    />
                    {running ? 'Running' : 'Stopped'}
                  </span>
                </div>
                <p className="text-muted-foreground text-sm">
                  {report.message ||
                    (running
                      ? `Listening on ${report.host}:${report.port}`
                      : 'Server is not running')}
                </p>
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
                <DialogContent className="max-h-[min(90vh,40rem)] max-w-2xl overflow-hidden rounded-2xl p-0 sm:rounded-2xl">
                  <DialogHeader className="space-y-2 px-6 pt-6 pb-2 text-left">
                    <DialogTitle>Manage Sandwalk on this machine</DialogTitle>
                    <DialogDescription>
                      Start, stop, and restart from the Mac menubar app or the
                      CLI — not from this dashboard.
                    </DialogDescription>
                  </DialogHeader>

                  <ScrollArea className="h-[min(50vh,24rem)] px-6">
                    <div className="space-y-4 py-2 pr-3">
                      <div className="bg-muted/40 rounded-xl border px-3.5 py-3">
                        <p className="text-sm font-semibold">Mac app</p>
                        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
                          Use the Sandwalk menubar icon →{' '}
                          <span className="text-foreground font-medium">
                            Start
                          </span>
                          ,{' '}
                          <span className="text-foreground font-medium">
                            Stop
                          </span>
                          , or{' '}
                          <span className="text-foreground font-medium">
                            Restart
                          </span>
                          . That supervises both the API and this web UI
                          together.
                        </p>
                      </div>

                      <div>
                        <p className="mb-3 text-sm font-semibold">CLI</p>
                        <div className="space-y-3.5">
                          {MANAGE_COMMANDS.map(item => (
                            <div key={item.id}>
                              <p className="text-muted-foreground mb-1.5 text-xs font-medium">
                                {item.title}
                              </p>
                              <CommandRow
                                command={item.command}
                                copied={copiedId === item.id}
                                onCopy={() =>
                                  copyCommand(item.id, item.command)
                                }
                              />
                              <p className="text-muted-foreground mt-1.5 text-xs">
                                {item.description}
                              </p>
                            </div>
                          ))}
                        </div>
                        <p className="text-muted-foreground mt-3 text-xs leading-relaxed">
                          To stop a CLI-started server, interrupt the terminal
                          with Ctrl+C, or quit / stop from the menubar if it is
                          supervising the process.
                        </p>
                      </div>
                    </div>
                  </ScrollArea>

                  <DialogFooter className="px-6 pt-2 pb-5 sm:justify-end">
                    <Button type="button" onClick={() => setHelpOpen(false)}>
                      Got it
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </section>

            <section>
              <SectionLabel subtitle={report.system.label}>System</SectionLabel>
              <div className="bg-background rounded-2xl border px-4">
                {gpuLabel ? (
                  <MetaRow label="GPU">
                    <span>{gpuLabel}</span>
                  </MetaRow>
                ) : null}
                <MetaRow label="System RAM" stretch>
                  <MemoryBar
                    used={report.system.ramUsedBytes}
                    total={report.system.ramTotalBytes}
                  />
                </MetaRow>
                <MetaRow
                  label="Load average"
                  hint="1 · 5 · 15 minute averages"
                >
                  <span className="tabular-nums">
                    {report.system.loadAverage?.length
                      ? report.system.loadAverage.join(' · ')
                      : '—'}
                  </span>
                </MetaRow>
                <MetaRow label="Thermal state">
                  {report.system.thermalState ? (
                    <span className="inline-flex items-center justify-end gap-2">
                      <span
                        className={cn(
                          'size-2 rounded-full',
                          report.system.thermalState === 'Nominal'
                            ? 'bg-emerald-500'
                            : 'bg-amber-500'
                        )}
                      />
                      <span className="text-foreground">
                        {report.system.thermalState}
                      </span>
                    </span>
                  ) : (
                    '—'
                  )}
                </MetaRow>
                <MetaRow label="Server uptime">
                  <span className="tabular-nums">
                    {formatUptime(report.uptimeSeconds)}
                  </span>
                </MetaRow>
                <MetaRow label="Process">
                  <span className="tabular-nums">
                    pid {report.pid}
                    {report.host && report.port != null
                      ? ` · ${report.host}:${report.port}`
                      : ''}
                  </span>
                </MetaRow>
                <MetaRow label="Agent version">
                  <span className="tabular-nums">
                    {report.version} · Python {report.system.pythonVersion}
                  </span>
                </MetaRow>
              </div>
            </section>

            <section>
              <SectionLabel>Runtime cache</SectionLabel>
              <div className="bg-background rounded-2xl border px-4">
                <MetaRow label="Cache files">
                  <span className="tabular-nums">
                    {report.cache.fileCount}{' '}
                    {report.cache.fileCount === 1 ? 'file' : 'files'}
                  </span>
                </MetaRow>
                <MetaRow label="Total size">
                  <span className="tabular-nums">
                    {formatBytes(report.cache.totalBytes)}
                  </span>
                </MetaRow>
                <MetaRow label="Location">
                  <code className="block truncate font-mono text-xs">
                    {report.cache.path}
                  </code>
                </MetaRow>
                <div className="flex justify-end py-3.5">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={clearing}
                    onClick={() => setConfirmClear(true)}
                    className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                  >
                    {clearing ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : null}
                    Clear cache
                  </Button>
                </div>
              </div>
            </section>
          </>
        ) : null}
      </div>

      <AlertDialog
        open={confirmClear}
        onOpenChange={open => {
          if (!open) setConfirmClear(false)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear runtime cache?</AlertDialogTitle>
            <AlertDialogDescription>
              Clears files under{' '}
              <code className="font-mono">~/.fastfold-cli/cache</code>. Datasets
              and sessions are not deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={clearing}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={clearing}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={event => {
                event.preventDefault()
                void clearCache()
              }}
            >
              Clear cache
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ScrollArea>
  )
}
