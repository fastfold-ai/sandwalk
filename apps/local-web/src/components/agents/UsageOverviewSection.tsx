import type { UsageChartModel, UsageOverview } from '@sandwalk/agent-ui-core'
import { useEffect, useMemo, useState } from 'react'

import {
  HeatmapStat,
  SessionActivityHeatmapGrid,
  SessionActivityHeatmapLegend
} from '@/components/agents/session-activity-heatmap-grid'
import { UsageModelStackedChart } from '@/components/agents/UsageModelStackedChart'
import { Skeleton } from '@/components/ui/skeleton'
import {
  readUsageOverviewCache,
  writeUsageOverviewCache
} from '@/lib/usage-overview-cache'
import { cn } from '@/lib/utils'

import {
  UsageHeroSkeleton,
  UsageModelsSkeleton
} from './usage-overview-skeletons'
import {
  buildUsageHeatmapModel,
  cacheHitPercent,
  colorForChartModel,
  formatAgentDuration,
  formatStreakDays,
  formatTokenCount,
  modelSeriesKey,
  peakDayLabel,
  providerLabel,
  type UsageGrain
} from './usage-overview-utils'

const GRAIN_OPTIONS: Array<{ id: UsageGrain; label: string }> = [
  { id: 'daily', label: 'Daily' },
  { id: 'weekly', label: 'Weekly' }
]

function MostUsedModelsList({
  overview,
  colorModels
}: {
  overview: UsageOverview
  colorModels: UsageChartModel[]
}) {
  if (overview.topModels.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">No model usage yet.</p>
    )
  }
  return (
    <div className="space-y-3">
      {overview.topModels.map((row, index) => {
        const max = overview.topModels[0]?.tokens || 1
        const width = Math.max(4, Math.round((100 * row.tokens) / max))
        const barColor = colorForChartModel(row, colorModels, index)
        const provider = providerLabel(row.provider)
        return (
          <div key={modelSeriesKey(row)}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="flex min-w-0 items-center gap-2 font-medium">
                <span
                  className="size-2.5 shrink-0 rounded-[2px]"
                  style={{ backgroundColor: barColor }}
                />
                <span className="truncate">
                  {row.modelId}
                  {provider ? (
                    <span className="text-muted-foreground font-normal">
                      {' '}
                      · {provider}
                    </span>
                  ) : null}
                </span>
              </span>
              <span className="text-muted-foreground shrink-0 tabular-nums">
                {formatTokenCount(row.tokens)}
              </span>
            </div>
            <div className="bg-muted mt-1.5 h-1.5 overflow-hidden rounded-full">
              <div
                className="h-full rounded-full"
                style={{ width: `${width}%`, backgroundColor: barColor }}
              />
            </div>
            <p className="text-muted-foreground mt-1 text-[11px] tabular-nums">
              {row.runs.toLocaleString()} {row.runs === 1 ? 'run' : 'runs'}
              {' · '}
              in {formatTokenCount(row.inputTokens)} / out{' '}
              {formatTokenCount(row.outputTokens)}
            </p>
          </div>
        )
      })}
    </div>
  )
}

export function UsageOverviewSection({
  client,
  className
}: {
  client: {
    baseUrl?: string
    getUsageOverview?: (signal?: AbortSignal) => Promise<UsageOverview>
  }
  className?: string
}) {
  const cacheKey = client.baseUrl || 'default'
  const [overview, setOverview] = useState<UsageOverview | null>(() =>
    readUsageOverviewCache(cacheKey)
  )
  const [error, setError] = useState<string | null>(null)
  const [grain, setGrain] = useState<UsageGrain>('daily')
  const [hovered, setHovered] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)
  const [retriedEmptyChart, setRetriedEmptyChart] = useState(false)

  useEffect(() => {
    if (!client.getUsageOverview) return
    const warm = readUsageOverviewCache(cacheKey)
    if (warm && reloadToken === 0) setOverview(warm)
    const controller = new AbortController()
    void client
      .getUsageOverview(controller.signal)
      .then(next => {
        writeUsageOverviewCache(cacheKey, next)
        setOverview(next)
        setError(null)
      })
      .catch(err => {
        if (controller.signal.aborted) return
        if (!warm && !readUsageOverviewCache(cacheKey)) {
          setError(err instanceof Error ? err.message : 'Failed to load usage')
        }
      })
    return () => controller.abort()
  }, [cacheKey, client, reloadToken])

  // One retry if chart data arrived before the server exposed modelDays.
  useEffect(() => {
    if (!overview || retriedEmptyChart) return
    if ((overview.modelDays?.length || 0) > 0) return
    setRetriedEmptyChart(true)
    setReloadToken(token => token + 1)
  }, [overview, retriedEmptyChart])

  const heatmap = useMemo(
    () => (overview ? buildUsageHeatmapModel(overview.days, grain) : null),
    [overview, grain]
  )

  const chartModels = overview?.chartModels ?? []
  const topModelSeries =
    overview?.topModels.map(row => ({
      modelId: row.modelId,
      provider: row.provider || 'unknown'
    })) ?? []
  const colorModels = chartModels.length > 0 ? chartModels : topModelSeries

  if (!client.getUsageOverview) return null

  return (
    <div className={cn('space-y-10', className)}>
      <div className="bg-card rounded-xl border p-5 sm:p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-muted-foreground text-xs font-light tracking-wide">
              Usage
            </p>
            {overview ? (
              <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">
                {formatTokenCount(overview.lifetimeTokens)}
              </p>
            ) : error ? (
              <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">
                —
              </p>
            ) : (
              <Skeleton className="mt-2 h-9 w-28" />
            )}
            <p className="text-muted-foreground mt-1 text-[11px]">
              Lifetime tokens
            </p>
          </div>
          <div className="bg-muted/50 flex rounded-md p-0.5 text-[11px]">
            {GRAIN_OPTIONS.map(option => (
              <button
                key={option.id}
                type="button"
                className={cn(
                  'rounded px-2.5 py-1 transition-colors',
                  grain === option.id
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )}
                onClick={() => setGrain(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {error ? (
          <p className="text-muted-foreground mt-6 text-sm">{error}</p>
        ) : null}

        {overview ? (
          <>
            <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <HeatmapStat
                label="Longest agent"
                value={formatAgentDuration(overview.longestAgentSeconds)}
              />
              <HeatmapStat
                label="Chats"
                value={overview.sessions.toLocaleString()}
              />
              <HeatmapStat
                label="Longest streak"
                value={formatStreakDays(overview.longestStreakDays)}
              />
              <HeatmapStat
                label="Current streak"
                value={formatStreakDays(overview.currentStreakDays)}
              />
            </div>

            {heatmap ? (
              <>
                <SessionActivityHeatmapGrid
                  weeks={heatmap.weeks}
                  monthLabels={heatmap.monthLabels}
                  hovered={hovered}
                  onHover={setHovered}
                  ariaLabelForCell={cell =>
                    `${formatTokenCount(cell.count)} tokens on ${cell.date.toLocaleDateString()}`
                  }
                  renderTooltip={cell => (
                    <>
                      <p className="font-medium">
                        {grain === 'weekly'
                          ? `Week of ${cell.date.toLocaleDateString(undefined, {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric'
                            })}`
                          : cell.date.toLocaleDateString(undefined, {
                              weekday: 'long',
                              month: 'long',
                              day: 'numeric',
                              year: 'numeric'
                            })}
                      </p>
                      <p className="mt-0.5 text-emerald-400 dark:text-emerald-700">
                        {formatTokenCount(cell.count)} tokens
                      </p>
                    </>
                  )}
                />
                <SessionActivityHeatmapLegend />
              </>
            ) : null}

            <div className="mt-8">
              <p className="text-muted-foreground text-xs font-light tracking-wide">
                Insights
              </p>
              <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
                <HeatmapStat
                  label="Peak day"
                  value={
                    overview.peakDayTokens > 0
                      ? `${formatTokenCount(overview.peakDayTokens)} · ${peakDayLabel(overview)}`
                      : '—'
                  }
                />
                <HeatmapStat
                  label="Models used"
                  value={overview.modelsUsed.toLocaleString()}
                />
                <HeatmapStat
                  label="Messages"
                  value={overview.messages.toLocaleString()}
                />
                <HeatmapStat
                  label="Tokens out"
                  value={formatTokenCount(overview.outputTokens)}
                />
                <HeatmapStat
                  label="Cache hit"
                  value={`${cacheHitPercent(overview)}%`}
                />
                <HeatmapStat
                  label="Avg tokens / chat"
                  value={formatTokenCount(overview.avgTokensPerSession)}
                />
              </div>
            </div>
          </>
        ) : error ? null : (
          <UsageHeroSkeleton />
        )}
      </div>

      <div className="bg-card rounded-xl border p-5 sm:p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-muted-foreground text-xs font-light tracking-wide">
              Models
            </p>
            <p className="mt-1 text-lg font-semibold tracking-tight">
              Last 30 days
            </p>
          </div>
        </div>

        {overview ? (
          <>
            <UsageModelStackedChart
              modelDays={overview.modelDays ?? []}
              chartModels={overview.chartModels ?? []}
            />
            <div className="mt-8">
              <p className="text-muted-foreground text-xs font-light tracking-wide">
                Most used models
              </p>
              <div className="mt-4">
                <MostUsedModelsList
                  overview={overview}
                  colorModels={colorModels}
                />
              </div>
            </div>
          </>
        ) : error ? (
          <p className="text-muted-foreground mt-6 text-sm">{error}</p>
        ) : (
          <UsageModelsSkeleton />
        )}
      </div>
    </div>
  )
}
