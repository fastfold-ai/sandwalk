import type {
  ServerCacheInfo,
  ServerLifecycleResult,
  ServerStatusReport
} from '@sandwalk/agent-ui-core'
import { Activity, Loader2, Play, Square } from 'lucide-react'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { toast } from 'sonner'

import { SettingsBlockSkeleton } from '@/components/agents/PageSkeletons'
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
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

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

export function ServerStatusView({
  onLoad,
  onStop,
  onRestart,
  onClearCache,
  onAfterStop,
  onAfterRestart
}: {
  onLoad: (signal?: AbortSignal) => Promise<ServerStatusReport>
  onStop: (signal?: AbortSignal) => Promise<ServerLifecycleResult>
  onRestart: (signal?: AbortSignal) => Promise<ServerLifecycleResult>
  onClearCache: (signal?: AbortSignal) => Promise<ServerCacheInfo>
  onAfterStop?: () => void
  onAfterRestart?: () => Promise<void>
}) {
  const [report, setReport] = useState<ServerStatusReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const [restarting, setRestarting] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [lifecycleNote, setLifecycleNote] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<'stop' | 'start' | 'clear-cache' | null>(
    null
  )

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true)
      setError(null)
      try {
        const next = await onLoad(signal)
        if (signal?.aborted) return
        setReport(next)
        setLifecycleNote(null)
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

  const runConfirmed = async () => {
    if (!confirm) return
    const action = confirm
    setConfirm(null)
    setError(null)

    if (action === 'stop') {
      setStopping(true)
      try {
        const result = await onStop()
        setLifecycleNote(result.message || 'Server is shutting down.')
        toast.success(result.message || 'Server stopped')
        onAfterStop?.()
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setStopping(false)
      }
      return
    }

    if (action === 'start') {
      setRestarting(true)
      try {
        const result = await onRestart()
        setLifecycleNote(result.message || 'Server is starting…')
        toast.message(result.message || 'Starting server…')
        if (onAfterRestart) {
          await onAfterRestart()
          await load()
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setRestarting(false)
      }
      return
    }

    setClearing(true)
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
  const busy = stopping || restarting

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
                <Activity className="size-5" strokeWidth={1.75} />
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold tracking-tight">
                    Sandwalk {report.version}
                  </h3>
                  <span
                    className={cn(
                      'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
                      busy
                        ? 'bg-muted text-muted-foreground'
                        : running
                          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
                          : 'bg-destructive/15 text-destructive'
                    )}
                  >
                    {busy ? (
                      <Loader2 className="size-3 animate-spin" />
                    ) : (
                      <span
                        className={cn(
                          'size-1.5 rounded-full',
                          running ? 'bg-emerald-500' : 'bg-destructive'
                        )}
                      />
                    )}
                    {busy
                      ? stopping
                        ? 'Stopping…'
                        : 'Starting…'
                      : running
                        ? 'Running'
                        : 'Stopped'}
                  </span>
                </div>
                <p className="text-muted-foreground text-sm">
                  {lifecycleNote || report.message || 'Server is running'}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => setConfirm(running ? 'stop' : 'start')}
                className={cn(
                  'shrink-0',
                  running &&
                    'text-destructive hover:bg-destructive/10 hover:text-destructive'
                )}
              >
                {busy ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : running ? (
                  <Square className="size-3.5" />
                ) : (
                  <Play className="size-3.5" />
                )}
                {busy
                  ? stopping
                    ? 'Stopping…'
                    : 'Starting…'
                  : running
                    ? 'Stop'
                    : 'Start'}
              </Button>
            </section>

            <section>
              <SectionLabel subtitle={report.system.label}>System</SectionLabel>
              <div className="bg-background rounded-2xl border px-4">
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
                    disabled={clearing || busy}
                    onClick={() => setConfirm('clear-cache')}
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
        open={confirm !== null}
        onOpenChange={open => {
          if (!open) setConfirm(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirm === 'stop'
                ? 'Stop Sandwalk?'
                : confirm === 'start'
                  ? 'Start Sandwalk?'
                  : 'Clear runtime cache?'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirm === 'stop' ? (
                <>
                  The dashboard will disconnect until you start Sandwalk again
                  with <code className="font-mono">fastfold serve</code>.
                </>
              ) : confirm === 'start' ? (
                <>
                  Sandwalk will restart on this machine. Active agent runs may
                  be interrupted briefly.
                </>
              ) : (
                <>
                  Clears files under{' '}
                  <code className="font-mono">~/.fastfold-cli/cache</code>.
                  Datasets and sessions are not deleted.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy || clearing}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={busy || clearing}
              className={
                confirm === 'stop' || confirm === 'clear-cache'
                  ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
                  : undefined
              }
              onClick={event => {
                event.preventDefault()
                void runConfirmed()
              }}
            >
              {confirm === 'stop'
                ? 'Stop'
                : confirm === 'start'
                  ? 'Start'
                  : 'Clear cache'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ScrollArea>
  )
}
