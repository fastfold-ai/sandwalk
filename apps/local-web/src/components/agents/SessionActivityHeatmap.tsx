import type { AgentSession } from '@fastfold/agent-ui-core'
import { useMemo, useState } from 'react'

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

const WEEKDAY_LABELS = ['', 'M', '', 'W', '', 'F', ''] as const
const MS_PER_DAY = 86_400_000

type DayCell = {
  date: Date
  key: string
  count: number
  level: 0 | 1 | 2 | 3 | 4
  inRange: boolean
}

function startOfLocalDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function toDayKey(date: Date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function parseSessionDay(session: AgentSession): string | null {
  const stamp = session.createdAt || session.lastMessageAt || session.updatedAt
  if (!stamp) return null
  const date = new Date(stamp)
  if (Number.isNaN(date.getTime())) return null
  return toDayKey(date)
}

/** Monday-based weekday index: Mon=0 … Sun=6 */
function mondayIndex(date: Date) {
  return (date.getDay() + 6) % 7
}

function startOfWeekMonday(date: Date) {
  const day = startOfLocalDay(date)
  day.setDate(day.getDate() - mondayIndex(day))
  return day
}

function addDays(date: Date, days: number) {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

function levelForCount(count: number, max: number): 0 | 1 | 2 | 3 | 4 {
  if (count <= 0 || max <= 0) return 0
  const ratio = count / max
  if (ratio <= 0.25) return 1
  if (ratio <= 0.5) return 2
  if (ratio <= 0.75) return 3
  return 4
}

function formatLongDate(date: Date) {
  return date.toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  })
}

function formatShortDate(date: Date) {
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

function formatMonthLabel(date: Date) {
  return date.toLocaleDateString(undefined, { month: 'short' }).charAt(0)
}

function computeStreaks(dayCounts: Map<string, number>, today: Date) {
  const todayStart = startOfLocalDay(today)
  let current = 0
  let cursor = todayStart
  // Current streak can include today or end yesterday.
  if ((dayCounts.get(toDayKey(cursor)) || 0) === 0) {
    cursor = addDays(cursor, -1)
  }
  while ((dayCounts.get(toDayKey(cursor)) || 0) > 0) {
    current += 1
    cursor = addDays(cursor, -1)
  }

  let longest = 0
  let run = 0
  const keys = [...dayCounts.keys()].sort()
  let prev: string | null = null
  for (const key of keys) {
    const count = dayCounts.get(key) || 0
    if (count <= 0) {
      run = 0
      prev = key
      continue
    }
    if (prev) {
      const prevDate = new Date(`${prev}T12:00:00`)
      const thisDate = new Date(`${key}T12:00:00`)
      const gap = Math.round(
        (thisDate.getTime() - prevDate.getTime()) / MS_PER_DAY
      )
      run = gap === 1 ? run + 1 : 1
    } else {
      run = 1
    }
    longest = Math.max(longest, run)
    prev = key
  }

  return { current, longest: Math.max(longest, current) }
}

const LEVEL_CLASS: Record<0 | 1 | 2 | 3 | 4, string> = {
  0: 'bg-muted dark:bg-muted/40',
  1: 'bg-emerald-200 dark:bg-emerald-950',
  2: 'bg-emerald-300 dark:bg-emerald-800',
  3: 'bg-emerald-500 dark:bg-emerald-600',
  4: 'bg-emerald-600 dark:bg-emerald-400'
}

export function SessionActivityHeatmap({
  sessions,
  className
}: {
  sessions: AgentSession[]
  className?: string
}) {
  const [hovered, setHovered] = useState<string | null>(null)

  const model = useMemo(() => {
    const today = startOfLocalDay(new Date())
    const endWeek = startOfWeekMonday(today)
    const startWeek = addDays(endWeek, -52 * 7)
    const rangeStart = startWeek

    const dayCounts = new Map<string, number>()
    for (const session of sessions) {
      const key = parseSessionDay(session)
      if (!key) continue
      dayCounts.set(key, (dayCounts.get(key) || 0) + 1)
    }

    let maxCount = 0
    for (const count of dayCounts.values()) {
      maxCount = Math.max(maxCount, count)
    }

    const weeks: DayCell[][] = []
    for (let w = 0; w < 53; w += 1) {
      const weekStart = addDays(startWeek, w * 7)
      const week: DayCell[] = []
      for (let d = 0; d < 7; d += 1) {
        const date = addDays(weekStart, d)
        const key = toDayKey(date)
        const inRange = date >= rangeStart && date <= today
        const count = inRange ? dayCounts.get(key) || 0 : 0
        week.push({
          date,
          key,
          count,
          level: inRange ? levelForCount(count, maxCount) : 0,
          inRange
        })
      }
      weeks.push(week)
    }

    const monthLabels: Array<{ label: string; weekIndex: number }> = []
    let lastMonth = -1
    weeks.forEach((week, weekIndex) => {
      const mid = week[3]?.date
      if (!mid || !week.some(cell => cell.inRange)) return
      const month = mid.getMonth()
      if (month === lastMonth) return
      lastMonth = month
      monthLabels.push({ label: formatMonthLabel(mid), weekIndex })
    })

    let mostActiveDay: DayCell | null = null
    const monthTotals = new Map<string, { label: string; count: number }>()
    for (const week of weeks) {
      for (const cell of week) {
        if (!cell.inRange || cell.count <= 0) continue
        if (!mostActiveDay || cell.count > mostActiveDay.count) {
          mostActiveDay = cell
        }
        const monthKey = `${cell.date.getFullYear()}-${cell.date.getMonth()}`
        const label = cell.date.toLocaleDateString(undefined, { month: 'long' })
        const prev = monthTotals.get(monthKey)
        monthTotals.set(monthKey, {
          label,
          count: (prev?.count || 0) + cell.count
        })
      }
    }

    let mostActiveMonth = '—'
    let bestMonthCount = 0
    for (const entry of monthTotals.values()) {
      if (entry.count > bestMonthCount) {
        bestMonthCount = entry.count
        mostActiveMonth = entry.label
      }
    }

    const { current, longest } = computeStreaks(dayCounts, today)

    return {
      weeks,
      monthLabels,
      total: sessions.length,
      mostActiveMonth,
      mostActiveDayLabel: mostActiveDay
        ? formatShortDate(mostActiveDay.date)
        : '—',
      longestStreak: longest,
      currentStreak: current
    }
  }, [sessions])

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

      <TooltipProvider delayDuration={120}>
        <div className="mt-6 overflow-x-auto">
          <div className="inline-block min-w-full">
            <div
              className="mb-1 grid gap-[3px]"
              style={{
                gridTemplateColumns: `1.25rem repeat(${model.weeks.length}, minmax(0, 1fr))`
              }}
            >
              <span />
              {model.weeks.map((_, weekIndex) => {
                const label = model.monthLabels.find(
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
                {model.weeks.map((week, weekIndex) => (
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
                              onMouseEnter={() => setHovered(cell.key)}
                              onMouseLeave={() => setHovered(null)}
                              onFocus={() => setHovered(cell.key)}
                              onBlur={() => setHovered(null)}
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

      <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Most active month" value={model.mostActiveMonth} />
        <Stat label="Most active day" value={model.mostActiveDayLabel} />
        <Stat label="Longest streak" value={`${model.longestStreak}d`} />
        <Stat label="Current streak" value={`${model.currentStreak}d`} />
      </div>

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
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-muted-foreground text-[11px]">{label}</p>
      <p className="mt-1 text-sm font-medium tracking-tight">{value}</p>
    </div>
  )
}
