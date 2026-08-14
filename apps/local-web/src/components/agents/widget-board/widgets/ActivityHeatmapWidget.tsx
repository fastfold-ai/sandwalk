import type { UsageOverview, WidgetSize } from '@sandwalk/agent-ui-core'
import { useMemo, useState } from 'react'

import {
  SessionActivityHeatmapGrid,
  SessionActivityHeatmapLegend
} from '@/components/agents/session-activity-heatmap-grid'
import { cn } from '@/lib/utils'

import {
  buildUsageHeatmapModel,
  formatTokenCount,
  type UsageGrain
} from '../../usage-overview-utils'
import { widgetShellClass } from '../grid'

const GRAIN_OPTIONS: Array<{ id: UsageGrain; label: string }> = [
  { id: 'daily', label: 'Daily' },
  { id: 'weekly', label: 'Weekly' }
]

export function ActivityHeatmapWidget({
  overview,
  size,
  grain,
  onGrainChange
}: {
  overview: UsageOverview | null
  size: WidgetSize
  grain: UsageGrain
  onGrainChange: (grain: UsageGrain) => void
}) {
  const [hovered, setHovered] = useState<string | null>(null)
  const heatmap = useMemo(
    () => (overview ? buildUsageHeatmapModel(overview.days, grain) : null),
    [overview, grain]
  )

  return (
    <div className={widgetShellClass(size)}>
      <div className="mb-3 flex shrink-0 flex-wrap items-center justify-between gap-2">
        <p className="text-muted-foreground text-xs font-light tracking-wide">
          Activity
        </p>
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
              onClick={() => onGrainChange(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      {heatmap ? (
        <div className="flex min-h-0 flex-1 flex-col justify-between gap-3">
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
        </div>
      ) : (
        <p className="text-muted-foreground text-sm">No activity yet.</p>
      )}
    </div>
  )
}
