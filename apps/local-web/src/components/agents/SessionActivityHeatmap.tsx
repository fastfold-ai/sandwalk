import type { AgentSession } from '@sandwalk/agent-ui-core'
import { useMemo, useState } from 'react'

import { cn } from '@/lib/utils'

import {
  HeatmapStat,
  SessionActivityHeatmapGrid,
  SessionActivityHeatmapLegend
} from './session-activity-heatmap-grid'
import { buildHeatmapModel } from './session-activity-heatmap-utils'

export function SessionActivityHeatmap({
  sessions,
  className
}: {
  sessions: AgentSession[]
  className?: string
}) {
  const [hovered, setHovered] = useState<string | null>(null)
  const model = useMemo(() => buildHeatmapModel(sessions), [sessions])

  return (
    <div className={cn('bg-card rounded-xl border p-5 sm:p-6', className)}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-muted-foreground text-xs font-light tracking-wide">
            Agent Sessions
          </p>
          <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">
            {model.total.toLocaleString()}
          </p>
        </div>
      </div>

      <SessionActivityHeatmapGrid
        weeks={model.weeks}
        monthLabels={model.monthLabels}
        hovered={hovered}
        onHover={setHovered}
      />

      <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <HeatmapStat label="Most active month" value={model.mostActiveMonth} />
        <HeatmapStat label="Most active day" value={model.mostActiveDayLabel} />
        <HeatmapStat label="Longest streak" value={`${model.longestStreak}d`} />
        <HeatmapStat label="Current streak" value={`${model.currentStreak}d`} />
      </div>

      <SessionActivityHeatmapLegend />
    </div>
  )
}
