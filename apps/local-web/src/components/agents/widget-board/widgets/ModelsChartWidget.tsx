import type { UsageOverview, WidgetSize } from '@sandwalk/agent-ui-core'

import { UsageModelStackedChart } from '@/components/agents/UsageModelStackedChart'

import { UsageModelsSkeleton } from '../../usage-overview-skeletons'
import { widgetShellClass } from '../grid'

export function ModelsChartWidget({
  overview,
  error,
  size
}: {
  overview: UsageOverview | null
  error: string | null
  size: WidgetSize
}) {
  return (
    <div className={widgetShellClass(size)}>
      <p className="text-muted-foreground shrink-0 text-xs font-light tracking-wide">
        Models · last 30 days
      </p>
      {overview ? (
        <div className="mt-2 flex min-h-0 flex-1 flex-col">
          <UsageModelStackedChart
            modelDays={overview.modelDays ?? []}
            chartModels={overview.chartModels ?? []}
            fill
          />
        </div>
      ) : error ? (
        <p className="text-muted-foreground mt-3 text-sm">{error}</p>
      ) : (
        <div className="mt-3 flex-1">
          <UsageModelsSkeleton />
        </div>
      )}
    </div>
  )
}
