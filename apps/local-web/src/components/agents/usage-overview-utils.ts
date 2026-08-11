import type {
  UsageChartModel,
  UsageDayPoint,
  UsageModelDayPoint,
  UsageOverview
} from '@sandwalk/agent-ui-core'

import {
  type DayCell,
  addDays,
  formatMonthLabel,
  formatShortDate,
  levelForCount,
  startOfLocalDay,
  startOfWeekMonday,
  toDayKey
} from './session-activity-heatmap-utils'

export type UsageGrain = 'daily' | 'weekly'

/** Distinct stacked-bar colors (OpenRouter-style). */
export const MODEL_CHART_COLORS = [
  '#eab308', // yellow
  '#22c55e', // green
  '#a855f7', // purple
  '#38bdf8', // sky
  '#3b82f6', // blue
  '#ec4899', // pink
  '#f97316', // orange
  '#94a3b8' // slate (Other)
] as const

export function modelSeriesKey(
  model: Pick<UsageChartModel, 'modelId' | 'provider'>
): string {
  return `${model.provider || 'unknown'}\t${model.modelId}`
}

const NAMED_CHART_COLORS = MODEL_CHART_COLORS.slice(0, -1)

export function colorForChartModel(
  model: Pick<UsageChartModel, 'modelId' | 'provider'>,
  chartModels: UsageChartModel[],
  fallbackIndex = 0
): string {
  if (model.modelId === 'Other') {
    return MODEL_CHART_COLORS[MODEL_CHART_COLORS.length - 1]
  }
  const key = modelSeriesKey(model)
  const index = chartModels.findIndex(item => modelSeriesKey(item) === key)
  if (index < 0) {
    return NAMED_CHART_COLORS[fallbackIndex % NAMED_CHART_COLORS.length]
  }
  return NAMED_CHART_COLORS[index % NAMED_CHART_COLORS.length]
}

export type ModelChartDay = {
  day: string
  date: Date
  total: number
  segments: Array<{
    modelId: string
    provider: string
    tokens: number
    color: string
  }>
}

export function buildModelChartDays(
  modelDays: UsageModelDayPoint[],
  chartModels: UsageChartModel[]
): ModelChartDay[] {
  const byDay = new Map<string, Map<string, number>>()
  for (const point of modelDays) {
    if (!point.day || point.tokens <= 0) continue
    const bucket = byDay.get(point.day) ?? new Map<string, number>()
    const key = modelSeriesKey(point)
    bucket.set(key, (bucket.get(key) || 0) + point.tokens)
    byDay.set(point.day, bucket)
  }

  const today = startOfLocalDay(new Date())
  const start = addDays(today, -29)
  const out: ModelChartDay[] = []
  for (let i = 0; i < 30; i += 1) {
    const date = addDays(start, i)
    const key = toDayKey(date)
    const bucket = byDay.get(key) ?? new Map<string, number>()
    const segments = chartModels
      .map(model => ({
        modelId: model.modelId,
        provider: model.provider || 'unknown',
        tokens: bucket.get(modelSeriesKey(model)) || 0,
        color: colorForChartModel(model, chartModels)
      }))
      .filter(segment => segment.tokens > 0)
    const total = segments.reduce((sum, segment) => sum + segment.tokens, 0)
    out.push({ day: key, date, total, segments })
  }
  return out
}

export function shortModelLabel(modelId: string): string {
  if (modelId === 'Other') return 'Other'
  const parts = modelId.split('/')
  return parts[parts.length - 1] || modelId
}

export function providerLabel(provider: string | undefined): string {
  const value = String(provider || '').trim()
  if (!value || value === 'unknown') return ''
  return value
}

export function formatTokenCount(value: number): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 10_000) return `${Math.round(value / 1000)}k`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
  return value.toLocaleString()
}

/** Compact duration for Longest Agent (Cursor-style: 14h, 2d). */
export function formatAgentDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds || 0))
  if (total < 60) return total > 0 ? '<1m' : '—'
  const days = Math.floor(total / 86_400)
  const hours = Math.floor((total % 86_400) / 3_600)
  const minutes = Math.floor((total % 3_600) / 60)
  if (days > 0) return hours > 0 ? `${days}d ${hours}h` : `${days}d`
  if (hours > 0) return minutes > 0 && hours < 10 ? `${hours}h ${minutes}m` : `${hours}h`
  return `${minutes}m`
}

export function formatStreakDays(days: number): string {
  if (days <= 0) return '0d'
  return `${days}d`
}

export function formatPercent(share: number): string {
  return `${Math.round(share * 100)}%`
}

export function cacheHitPercent(overview: UsageOverview): number {
  const denom = overview.inputTokens + overview.cacheReadTokens
  if (denom <= 0) return 0
  return Math.round((1000 * overview.cacheReadTokens) / denom) / 10
}

export function attributedShareLabel(overview: UsageOverview): string {
  const attributed = overview.cliTokens + overview.uiTokens
  if (attributed <= 0) {
    if (overview.unknownTokens > 0) return 'Unattributed'
    return '—'
  }
  return `CLI ${formatPercent(overview.cliShare)} · UI ${formatPercent(overview.uiShare)}`
}

function weekKeyForDay(day: string): string {
  const date = new Date(`${day}T12:00:00`)
  return toDayKey(startOfWeekMonday(date))
}

export function buildUsageHeatmapModel(
  days: UsageDayPoint[],
  grain: UsageGrain
) {
  const today = startOfLocalDay(new Date())
  const endWeek = startOfWeekMonday(today)
  const startWeek = addDays(endWeek, -52 * 7)
  const rangeStart = startWeek

  const byDay = new Map(days.map(point => [point.day, point]))
  const weekTotals = new Map<string, UsageDayPoint>()
  if (grain === 'weekly') {
    for (const point of days) {
      if (point.tokens <= 0) continue
      const key = weekKeyForDay(point.day)
      const prev = weekTotals.get(key)
      if (!prev) {
        weekTotals.set(key, { ...point, day: key })
        continue
      }
      weekTotals.set(key, {
        day: key,
        tokens: prev.tokens + point.tokens,
        inputTokens: prev.inputTokens + point.inputTokens,
        outputTokens: prev.outputTokens + point.outputTokens,
        cacheReadTokens: prev.cacheReadTokens + point.cacheReadTokens,
        cliTokens: prev.cliTokens + point.cliTokens,
        uiTokens: prev.uiTokens + point.uiTokens,
        slackTokens: prev.slackTokens + point.slackTokens,
        unknownTokens: prev.unknownTokens + point.unknownTokens,
        runs: prev.runs + point.runs
      })
    }
  }

  let maxCount = 0
  const valueFor = (key: string): UsageDayPoint | null => {
    if (grain === 'weekly') {
      return weekTotals.get(weekKeyForDay(key)) || null
    }
    return byDay.get(key) || null
  }

  const weeks: DayCell[][] = []
  const detailByKey = new Map<string, UsageDayPoint>()
  for (let w = 0; w < 53; w += 1) {
    const weekStart = addDays(startWeek, w * 7)
    const week: DayCell[] = []
    for (let d = 0; d < 7; d += 1) {
      const date = addDays(weekStart, d)
      const key = toDayKey(date)
      const inRange = date >= rangeStart && date <= today
      const point = inRange ? valueFor(key) : null
      const count = point?.tokens || 0
      if (point) detailByKey.set(key, point)
      maxCount = Math.max(maxCount, count)
      week.push({
        date,
        key,
        count,
        level: 0,
        inRange
      })
    }
    weeks.push(week)
  }

  for (const week of weeks) {
    for (const cell of week) {
      if (!cell.inRange) continue
      cell.level = levelForCount(cell.count, maxCount)
    }
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

  return { weeks, monthLabels, detailByKey, grain }
}

export function peakDayLabel(overview: UsageOverview): string {
  if (!overview.peakDay) return '—'
  const date = new Date(`${overview.peakDay}T12:00:00`)
  if (Number.isNaN(date.getTime())) return overview.peakDay
  return formatShortDate(date)
}
