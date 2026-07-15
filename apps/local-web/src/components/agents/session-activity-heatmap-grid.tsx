import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

import {
  formatLongDate,
  LEVEL_CLASS,
  type DayCell,
  WEEKDAY_LABELS
} from './session-activity-heatmap-utils'

export function HeatmapStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-muted-foreground text-[11px]">{label}</p>
      <p className="mt-1 text-sm font-medium tracking-tight">{value}</p>
    </div>
  )
}

export function SessionActivityHeatmapGrid({
  weeks,
  monthLabels,
  hovered,
  onHover
}: {
  weeks: DayCell[][]
  monthLabels: Array<{ label: string; weekIndex: number }>
  hovered: string | null
  onHover: (key: string | null) => void
}) {
  return (
    <TooltipProvider delayDuration={120}>
      <div className="mt-6 overflow-x-auto">
        <div className="inline-block min-w-full">
          <div
            className="mb-1 grid gap-[3px]"
            style={{
              gridTemplateColumns: `1.25rem repeat(${weeks.length}, minmax(0, 1fr))`
            }}
          >
            <span />
            {weeks.map((_, weekIndex) => {
              const label = monthLabels.find(
                item => item.weekIndex === weekIndex
              )
              return (
                <span
                  key={`month-${weekIndex}`}
                  className="text-muted-foreground text-center text-[10px] leading-none"
                >
                  {label?.label || ''}
                </span>
              )
            })}
          </div>

          <div className="flex gap-[3px]">
            <div className="flex w-5 shrink-0 flex-col gap-[3px] pt-px">
              {WEEKDAY_LABELS.map((label, index) => (
                <span
                  key={`wd-${index}`}
                  className="text-muted-foreground flex h-[11px] items-center text-[10px] leading-none"
                >
                  {label}
                </span>
              ))}
            </div>

            <div className="flex min-w-0 flex-1 gap-[3px]">
              {weeks.map((week, weekIndex) => (
                <div
                  key={`week-${weekIndex}`}
                  className="flex min-w-0 flex-1 flex-col gap-[3px]"
                >
                  {week.map(cell => {
                    if (!cell.inRange) {
                      return (
                        <div
                          key={cell.key}
                          className="aspect-square w-full min-h-[11px] rounded-[2px] bg-transparent"
                        />
                      )
                    }
                    const active = hovered === cell.key
                    return (
                      <Tooltip key={cell.key}>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            aria-label={`${cell.count} sessions on ${formatLongDate(cell.date)}`}
                            className={cn(
                              'aspect-square w-full min-h-[11px] rounded-[2px] transition-opacity',
                              LEVEL_CLASS[cell.level],
                              active && 'ring-foreground/30 ring-1'
                            )}
                            onMouseEnter={() => onHover(cell.key)}
                            onMouseLeave={() => onHover(null)}
                            onFocus={() => onHover(cell.key)}
                            onBlur={() => onHover(null)}
                          />
                        </TooltipTrigger>
                        <TooltipContent
                          side="top"
                          className="bg-zinc-900 text-zinc-50 dark:bg-zinc-100 dark:text-zinc-900"
                        >
                          <p className="font-medium">
                            {formatLongDate(cell.date)}
                          </p>
                          <p className="mt-0.5 text-emerald-400 dark:text-emerald-700">
                            {cell.count.toLocaleString()}{' '}
                            {cell.count === 1 ? 'session' : 'sessions'}
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    )
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </TooltipProvider>
  )
}

export function SessionActivityHeatmapLegend() {
  return (
    <div className="text-muted-foreground mt-6 flex items-center gap-2 text-[11px]">
      <span>Fewer</span>
      <div className="flex items-center gap-[3px]">
        {([0, 1, 2, 3, 4] as const).map(level => (
          <span
            key={level}
            className={cn('size-2.5 rounded-[2px]', LEVEL_CLASS[level])}
          />
        ))}
      </div>
      <span>More</span>
    </div>
  )
}
