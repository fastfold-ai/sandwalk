import type { UsageChartModel, UsageModelDayPoint } from '@sandwalk/agent-ui-core'
import { useMemo, useState } from 'react'

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

import {
  buildModelChartDays,
  formatTokenCount,
  modelSeriesKey,
  providerLabel,
  shortModelLabel
} from './usage-overview-utils'

function ModelSeriesLabel({
  modelId,
  provider
}: {
  modelId: string
  provider?: string
}) {
  const providerText = providerLabel(provider)
  if (!providerText || modelId === 'Other') {
    return <span className="truncate">{shortModelLabel(modelId)}</span>
  }
  return (
    <span className="min-w-0 truncate">
      <span>{shortModelLabel(modelId)}</span>
      <span className="text-muted-foreground"> · {providerText}</span>
    </span>
  )
}

export function UsageModelStackedChart({
  modelDays,
  chartModels,
  className,
  fill = false
}: {
  modelDays: UsageModelDayPoint[]
  chartModels: UsageChartModel[]
  className?: string
  /** Grow plot area to fill the parent card (matches side-by-side heatmap height). */
  fill?: boolean
}) {
  const days = useMemo(
    () => buildModelChartDays(modelDays ?? [], chartModels ?? []),
    [modelDays, chartModels]
  )
  const maxTotal = Math.max(1, ...days.map(day => day.total))
  const [hovered, setHovered] = useState<string | null>(null)
  const active = days.find(day => day.day === hovered) || null
  const hasData = days.some(day => day.total > 0)
  const plotHeight = fill ? 'h-full min-h-[7.5rem]' : 'h-32'

  if (!hasData) {
    return (
      <p className="text-muted-foreground mt-6 text-sm">
        No token activity in the last 30 days.
      </p>
    )
  }

  const ticks = [0, 0.25, 0.5, 0.75, 1].map(ratio => ({
    ratio,
    label: formatTokenCount(Math.round(maxTotal * ratio))
  }))

  return (
    <div
      className={cn(
        fill ? 'flex min-h-0 flex-1 flex-col' : 'mt-3',
        className
      )}
    >
      <div className={cn('flex items-end gap-2', fill && 'min-h-0 flex-1')}>
        <div
          className={cn(
            'text-muted-foreground flex w-9 shrink-0 flex-col justify-between text-right text-[10px] tabular-nums',
            plotHeight
          )}
        >
          {[...ticks].reverse().map(tick => (
            <span key={tick.ratio}>{tick.label}</span>
          ))}
        </div>

        <TooltipProvider delayDuration={80}>
          <div className={cn('relative min-w-0 flex-1', fill && 'h-full')}>
            <div className="pointer-events-none absolute inset-0 flex flex-col justify-between">
              {ticks.map(tick => (
                <div
                  key={tick.ratio}
                  className="border-border/40 border-t border-dashed"
                />
              ))}
            </div>
            <div
              className={cn(
                'relative flex items-end gap-[3px]',
                plotHeight
              )}
            >
              {days.map(day => {
                const heightPct = Math.max(
                  0,
                  Math.round((100 * day.total) / maxTotal)
                )
                const selected = hovered === day.day
                return (
                  <Tooltip key={day.day}>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          'relative flex h-full min-w-0 flex-1 flex-col justify-end rounded-sm transition-colors',
                          selected ? 'bg-muted/60' : 'hover:bg-muted/30'
                        )}
                        aria-label={`${formatTokenCount(day.total)} tokens on ${day.date.toLocaleDateString()}`}
                        onMouseEnter={() => setHovered(day.day)}
                        onMouseLeave={() => setHovered(null)}
                        onFocus={() => setHovered(day.day)}
                        onBlur={() => setHovered(null)}
                      >
                        <div
                          className="flex w-full flex-col-reverse overflow-hidden rounded-[2px]"
                          style={{ height: `${heightPct}%` }}
                        >
                          {day.segments.map(segment => (
                            <div
                              key={modelSeriesKey(segment)}
                              style={{
                                backgroundColor: segment.color,
                                height: `${Math.max(
                                  2,
                                  Math.round(
                                    (100 * segment.tokens) /
                                      Math.max(1, day.total)
                                  )
                                )}%`
                              }}
                              className="w-full"
                            />
                          ))}
                        </div>
                      </button>
                    </TooltipTrigger>
                    <TooltipContent
                      side="top"
                      className="bg-zinc-900 text-zinc-50 dark:bg-zinc-100 dark:text-zinc-900"
                    >
                      <p className="font-medium">
                        {day.date.toLocaleDateString(undefined, {
                          month: 'long',
                          day: 'numeric',
                          year: 'numeric'
                        })}
                      </p>
                      <div className="mt-1.5 space-y-1">
                        {day.segments.map(segment => (
                          <div
                            key={modelSeriesKey(segment)}
                            className="flex items-center gap-2 text-[11px]"
                          >
                            <span
                              className="size-2 shrink-0 rounded-full"
                              style={{ backgroundColor: segment.color }}
                            />
                            <span className="min-w-0 flex-1 truncate">
                              <ModelSeriesLabel
                                modelId={segment.modelId}
                                provider={segment.provider}
                              />
                            </span>
                            <span className="tabular-nums opacity-80">
                              {formatTokenCount(segment.tokens)}
                            </span>
                          </div>
                        ))}
                      </div>
                      <p className="mt-1.5 text-[11px] font-medium tabular-nums">
                        Total {formatTokenCount(day.total)}
                      </p>
                    </TooltipContent>
                  </Tooltip>
                )
              })}
            </div>
          </div>
        </TooltipProvider>
      </div>

      <div className="text-muted-foreground mt-1.5 flex justify-between pl-11 text-[10px]">
        <span>
          {days[0]?.date.toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric'
          })}
        </span>
        <span>
          {active
            ? `${formatTokenCount(active.total)} · ${active.date.toLocaleDateString(
                undefined,
                { month: 'short', day: 'numeric' }
              )}`
            : days[days.length - 1]?.date.toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric'
              })}
        </span>
      </div>
    </div>
  )
}
