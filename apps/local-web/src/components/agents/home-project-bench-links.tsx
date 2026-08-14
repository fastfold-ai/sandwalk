import type {
  BenchActiveStatus,
  BenchResultSummary,
  LocalAgentClient
} from '@sandwalk/agent-local-client'
import { ExternalLink, Loader, Pause, Target } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { cn } from '@/lib/utils'

function isBenchRunInProgress(status?: string | null): boolean {
  const value = (status || '').toLowerCase()
  return value === 'running' || value === 'paused' || value === 'queued'
}

/** Compact run duration: `39s`, `11m 12s`, `2h 35m`, `1d 2h`. */
function formatRunDuration(seconds: number): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0))
  if (total < 60) return `${total}s`
  const days = Math.floor(total / 86_400)
  const hours = Math.floor((total % 86_400) / 3_600)
  const minutes = Math.floor((total % 3_600) / 60)
  const secs = total % 60
  if (days > 0) return hours > 0 ? `${days}d ${hours}h` : `${days}d`
  if (hours > 0) return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`
  return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`
}

function displayRunSeconds(row: BenchResultSummary, nowMs: number): number {
  const reported = Number(row.timeS) || 0
  if (!isBenchRunInProgress(row.status) || !row.createdAt) return reported
  const start = Date.parse(row.createdAt)
  if (Number.isNaN(start)) return reported
  const wall = Math.max(0, (nowMs - start) / 1000)
  // Prefer the larger so the clock stays monotonic across polls.
  return Math.max(reported, wall)
}

function overlayLiveStatus(
  rows: BenchResultSummary[],
  active: BenchActiveStatus | null
): BenchResultSummary[] {
  if (!active) return rows
  const live = new Map<string, string>()
  for (const job of active.inflight ?? []) live.set(job.runId, 'running')
  for (const job of active.queue ?? []) live.set(job.runId, 'queued')
  for (const job of active.paused ?? []) live.set(job.runId, 'paused')
  if (active.running && active.currentRunId) {
    live.set(active.currentRunId, 'running')
  }
  return rows.map(row => {
    const next = live.get(row.runId)
    if (next) return { ...row, status: next }
    const status = (row.status || '').toLowerCase()
    if (status === 'running' || status === 'queued') {
      return { ...row, status: 'interrupted' }
    }
    return row
  })
}

export function HomeProjectBenchLinks({
  client,
  projectId,
  embedded = false
}: {
  client: LocalAgentClient
  projectId: string
  /** When true, skip the section title (widget board supplies chrome). */
  embedded?: boolean
}) {
  const navigate = useNavigate()
  const [rows, setRows] = useState<BenchResultSummary[]>([])
  const [loaded, setLoaded] = useState(false)
  const [nowMs, setNowMs] = useState(() => Date.now())
  const hasActiveRun = rows.some(row => isBenchRunInProgress(row.status))

  useEffect(() => {
    let cancelled = false
    let sawSuccess = false
    const load = () => {
      void Promise.all([
        client.listBenchResults({ limit: 100 }),
        client.getBenchActive()
      ])
        .then(([page, active]) => {
          if (cancelled) return
          sawSuccess = true
          setRows(
            overlayLiveStatus(
              page.data.filter(item => item.projectId === projectId),
              active
            )
          )
        })
        .catch(() => {
          if (!cancelled && !sawSuccess) setRows([])
        })
        .finally(() => {
          if (!cancelled) setLoaded(true)
        })
    }
    setLoaded(false)
    load()
    const id = window.setInterval(load, 1500)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [client, projectId])

  useEffect(() => {
    if (!hasActiveRun) return
    setNowMs(Date.now())
    const id = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [hasActiveRun])

  if (!loaded || rows.length === 0) {
    if (!embedded) return null
    return (
      <div>
        <h3 className="text-muted-foreground mb-3 text-xs font-light tracking-wide">
          Bench results
        </h3>
        <p className="text-muted-foreground text-sm">No bench results yet.</p>
      </div>
    )
  }

  return (
    <section className={embedded ? undefined : 'mb-8'}>
      <h3
        className={cn(
          embedded
            ? 'text-muted-foreground mb-3 text-xs font-light tracking-wide'
            : 'mb-3 text-sm font-medium'
        )}
      >
        Bench results
      </h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {rows.map(row => {
          const statusKey = (row.status || '').toLowerCase()
          const paused = statusKey === 'paused' || statusKey === 'interrupted'
          const running = statusKey === 'running'
          const statusLabel =
            statusKey === 'paused'
              ? 'Paused'
              : statusKey === 'interrupted'
                ? 'Interrupted'
                : 'Running'
          const pct = Math.round((row.accuracy || 0) * 1000) / 10
          const duration = displayRunSeconds(row, nowMs)
          const durationLabel =
            duration > 0
              ? ` · ${formatRunDuration(duration)}${running ? ' graded' : ''}`
              : ''
          return (
            <button
              key={row.runId}
              type="button"
              className="bg-card sandwalk-surface-shadow hover:bg-muted/40 flex min-h-[6.5rem] flex-col rounded-xl p-4 text-left transition-colors"
              onClick={() =>
                navigate(`/dashboard/bench/${encodeURIComponent(row.runId)}`)
              }
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-2.5">
                  <span
                    className={cn(
                      'flex size-8 shrink-0 items-center justify-center rounded-md',
                      running
                        ? 'bg-sky-500/15 text-sky-600'
                        : paused
                          ? 'bg-muted text-muted-foreground'
                          : pct >= 70
                          ? 'bg-emerald-500/15 text-emerald-600'
                          : pct >= 40
                            ? 'bg-amber-500/15 text-amber-600'
                            : 'bg-red-500/15 text-red-600'
                    )}
                  >
                    {running ? (
                      <Loader className="size-3.5 animate-spin" />
                    ) : paused ? (
                      <Pause className="size-3.5" />
                    ) : (
                      <Target className="size-3.5" />
                    )}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {row.benchmark}
                    </p>
                    <p className="text-muted-foreground mt-0.5 truncate text-xs">
                      {row.modelId}
                    </p>
                  </div>
                </div>
                {paused ? (
                  <p className="text-muted-foreground text-sm font-semibold">
                    {statusLabel}
                  </p>
                ) : running ? (
                  <p className="text-sky-600 text-sm font-semibold">
                    {statusLabel}
                  </p>
                ) : (
                  <p
                    className={cn(
                      'text-lg font-semibold tabular-nums',
                      pct >= 70
                        ? 'text-emerald-600'
                        : pct >= 40
                          ? 'text-amber-600'
                          : 'text-red-600'
                    )}
                  >
                    {pct.toFixed(1)}%
                  </p>
                )}
              </div>
              <div className="text-muted-foreground mt-auto flex items-center justify-between gap-2 pt-3 text-xs">
                <span className="tabular-nums">
                  {row.correct}/{row.total}
                  {durationLabel}
                </span>
                <span className="inline-flex items-center gap-1">
                  {running ? 'View run' : 'Open result'}
                  <ExternalLink className="size-3" />
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}
