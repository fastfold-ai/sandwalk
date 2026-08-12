import type {
  UsageChartModel,
  UsageOverview,
  WidgetSize
} from '@sandwalk/agent-ui-core'

import {
  colorForChartModel,
  formatTokenCount,
  modelSeriesKey,
  providerLabel
} from '../../usage-overview-utils'
import { UsageModelsSkeleton } from '../../usage-overview-skeletons'
import { widgetShellClass } from '../grid'

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

export function ModelsTopListWidget({
  overview,
  error,
  size
}: {
  overview: UsageOverview | null
  error: string | null
  size: WidgetSize
}) {
  const chartModels = overview?.chartModels ?? []
  const topModelSeries =
    overview?.topModels.map(row => ({
      modelId: row.modelId,
      provider: row.provider || 'unknown'
    })) ?? []
  const colorModels = chartModels.length > 0 ? chartModels : topModelSeries

  return (
    <div className={widgetShellClass(size)}>
      <p className="text-muted-foreground text-xs font-light tracking-wide">
        Most used models
      </p>
      <div className="mt-4">
        {overview ? (
          <MostUsedModelsList overview={overview} colorModels={colorModels} />
        ) : error ? (
          <p className="text-muted-foreground text-sm">{error}</p>
        ) : (
          <UsageModelsSkeleton />
        )}
      </div>
    </div>
  )
}
