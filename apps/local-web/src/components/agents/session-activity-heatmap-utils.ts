import type { AgentSession } from '@sandwalk/agent-ui-core'

export const WEEKDAY_LABELS = ['', 'M', '', 'W', '', 'F', ''] as const
export const MS_PER_DAY = 86_400_000

export type DayCell = {
  date: Date
  key: string
  count: number
  level: 0 | 1 | 2 | 3 | 4
  inRange: boolean
}

export const LEVEL_CLASS: Record<0 | 1 | 2 | 3 | 4, string> = {
  0: 'bg-muted dark:bg-muted/40',
  1: 'bg-emerald-200 dark:bg-emerald-950',
  2: 'bg-emerald-300 dark:bg-emerald-800',
  3: 'bg-emerald-500 dark:bg-emerald-600',
  4: 'bg-emerald-600 dark:bg-emerald-400'
}

export function startOfLocalDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

export function toDayKey(date: Date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function parseSessionDay(session: AgentSession): string | null {
  const stamp = session.createdAt || session.lastMessageAt || session.updatedAt
  if (!stamp) return null
  const date = new Date(stamp)
  if (Number.isNaN(date.getTime())) return null
  return toDayKey(date)
}

export function mondayIndex(date: Date) {
  return (date.getDay() + 6) % 7
}

export function startOfWeekMonday(date: Date) {
  const day = startOfLocalDay(date)
  day.setDate(day.getDate() - mondayIndex(day))
  return day
}

export function addDays(date: Date, days: number) {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

export function levelForCount(count: number, max: number): 0 | 1 | 2 | 3 | 4 {
  if (count <= 0 || max <= 0) return 0
  const ratio = count / max
  if (ratio <= 0.25) return 1
  if (ratio <= 0.5) return 2
  if (ratio <= 0.75) return 3
  return 4
}

export function formatLongDate(date: Date) {
  return date.toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  })
}

export function formatShortDate(date: Date) {
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

export function formatMonthLabel(date: Date) {
  return date.toLocaleDateString(undefined, { month: 'short' }).charAt(0)
}

export function computeStreaks(dayCounts: Map<string, number>, today: Date) {
  const todayStart = startOfLocalDay(today)
  let current = 0
  let cursor = todayStart
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

export function buildHeatmapModel(sessions: AgentSession[]) {
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
}
