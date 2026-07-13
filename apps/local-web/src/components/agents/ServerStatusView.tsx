import type { ServerCacheInfo, ServerStatusReport } from '@sandwalk/agent-ui-core'
import { Loader2 } from 'lucide-react'
import { type ReactNode,useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { SettingsBlockSkeleton } from '@/components/agents/PageSkeletons'
import {
  listenSubtitle,
  SandwalkServerCard
} from '@/components/agents/SandwalkServerCard'
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
            <SandwalkServerCard
              version={report.version}
              running={running}
              subtitle={listenSubtitle({
                running,
                host: report.host,
                port: report.port,
                message: report.message
              })}
            />

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
              <code className="font-mono">~/.sandwalk/cache</code>. Datasets
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
