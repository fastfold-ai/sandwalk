import type { ServicesReport } from '@sandwalk/agent-local-client'
import { Loader, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

function formatBytes(bytes: number | null) {
  if (bytes == null) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB'] as const
  let value = bytes / 1024
  for (let index = 0; index < units.length; index += 1) {
    if (value < 1024 || index === units.length - 1) {
      return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`
    }
    value /= 1024
  }
  return `${bytes} B`
}

export function LogsView({
  onLoad
}: {
  onLoad: (signal?: AbortSignal) => Promise<ServicesReport>
}) {
  const [report, setReport] = useState<ServicesReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold">Logs</h2>
            <p className="text-muted-foreground mt-2 text-sm">
              Sandwalk services on this machine: process id, port, memory, and the
              latest server log.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading}
            onClick={() => void load()}
          >
            {loading ? (
              <Loader className="size-3.5 animate-spin" />
            ) : (
              <RefreshCw className="size-3.5" />
            )}
            Refresh
          </Button>
        </div>

        {error ? (
          <p className="text-destructive text-sm">{error}</p>
        ) : null}

        <section className="overflow-hidden rounded-xl border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/40 text-muted-foreground text-xs">
              <tr>
                <th className="px-3 py-2 font-medium">Service</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">PID</th>
                <th className="px-3 py-2 font-medium">Port</th>
                <th className="px-3 py-2 font-medium">Memory</th>
                <th className="px-3 py-2 font-medium">CPU</th>
              </tr>
            </thead>
            <tbody>
              {(report?.processes || []).map(process => (
                <tr key={process.id} className="border-t align-top">
                  <td className="px-3 py-3">
                    <div className="font-medium">{process.name}</div>
                    <div className="text-muted-foreground mt-1 font-mono text-xs">
                      {process.detail || process.command || '—'}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <span
                      className={cn(
                        'inline-flex rounded-full px-2 py-0.5 text-xs',
                        process.status === 'running'
                          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                          : 'bg-muted text-muted-foreground'
                      )}
                    >
                      {process.status === 'running' ? 'Running' : 'Stopped'}
                    </span>
                  </td>
                  <td className="px-3 py-3 font-mono text-xs">
                    {process.pid ?? '—'}
                  </td>
                  <td className="px-3 py-3 font-mono text-xs">
                    {process.port ?? '—'}
                  </td>
                  <td className="px-3 py-3 font-mono text-xs">
                    {formatBytes(process.rssBytes)}
                  </td>
                  <td className="px-3 py-3 font-mono text-xs">
                    {process.cpuPercent == null
                      ? '—'
                      : `${process.cpuPercent.toFixed(1)}%`}
                  </td>
                </tr>
              ))}
              {!report && loading ? (
                <tr>
                  <td className="text-muted-foreground px-3 py-4" colSpan={6}>
                    Reading processes…
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </section>

        {(report?.logs || []).map(log => (
          <section key={log.name} className="space-y-2">
            <h3 className="text-sm font-medium">{log.name}</h3>
            <pre className="bg-muted/40 max-h-96 min-h-32 overflow-auto rounded-xl p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
              {log.tail || 'No log lines yet.'}
            </pre>
          </section>
        ))}
        {report && report.logs.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            No log files yet. They appear under ~/.sandwalk/logs after the
            server writes agent-server.log.
          </p>
        ) : null}
      </div>
    </ScrollArea>
  )
}
