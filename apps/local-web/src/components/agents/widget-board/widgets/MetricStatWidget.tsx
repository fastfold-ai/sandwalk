import type { UsageOverview, WidgetSize } from '@sandwalk/agent-ui-core'

import { cn } from '@/lib/utils'

import { valueTextClass,widgetShellClass } from '../grid'

export function MetricStatWidget({
  label,
  value,
  detail,
  size,
  loading
}: {
  label: string
  value: string
  /** Secondary line/suffix (e.g. peak-day date) — smaller muted text. */
  detail?: string | null
  size: WidgetSize
  loading?: boolean
}) {
  const title = loading
    ? undefined
    : detail
      ? `${value} · ${detail}`
      : value
  return (
    <div className={widgetShellClass(size)}>
      <p className="text-muted-foreground truncate text-xs font-light tracking-wide">
        {label}
      </p>
      <p
        className={cn(
          'flex min-w-0 items-baseline gap-1.5',
          size === 'sm' ? 'truncate' : 'flex-wrap'
        )}
        title={title}
      >
        <span
          className={cn(
            'min-w-0 truncate',
            valueTextClass(size),
            loading && 'text-muted-foreground'
          )}
        >
          {loading ? '—' : value}
        </span>
        {!loading && detail ? (
          <span className="text-muted-foreground truncate text-[11px] font-normal tracking-normal">
            {detail}
          </span>
        ) : null}
      </p>
    </div>
  )
}

export function metricValueForType(
  type: string,
  overview: UsageOverview | null,
  formatters: {
    formatTokenCount: (n: number) => string
    formatAgentDuration: (n: number) => string
    formatStreakDays: (n: number) => string
    peakDayLabel: (o: UsageOverview) => string
    cacheHitPercent: (o: UsageOverview) => number
  }
): { label: string; value: string; detail?: string } | null {
  if (!overview) return null
  switch (type) {
    case 'stat-longest-agent':
      return {
        label: 'Longest agent',
        value: formatters.formatAgentDuration(overview.longestAgentSeconds)
      }
    case 'stat-chats':
      return {
        label: 'Chats',
        value: overview.sessions.toLocaleString()
      }
    case 'stat-longest-streak':
      return {
        label: 'Longest streak',
        value: formatters.formatStreakDays(overview.longestStreakDays)
      }
    case 'stat-current-streak':
      return {
        label: 'Current streak',
        value: formatters.formatStreakDays(overview.currentStreakDays)
      }
    case 'stat-peak-day':
      return {
        label: 'Peak day',
        value:
          overview.peakDayTokens > 0
            ? formatters.formatTokenCount(overview.peakDayTokens)
            : '—',
        detail:
          overview.peakDayTokens > 0
            ? formatters.peakDayLabel(overview)
            : undefined
      }
    case 'stat-models-used':
      return {
        label: 'Models used',
        value: overview.modelsUsed.toLocaleString()
      }
    case 'stat-messages':
      return {
        label: 'Messages',
        value: overview.messages.toLocaleString()
      }
    case 'stat-tokens-in':
      return {
        label: 'Tokens in',
        value: formatters.formatTokenCount(overview.inputTokens)
      }
    case 'stat-tokens-out':
      return {
        label: 'Tokens out',
        value: formatters.formatTokenCount(overview.outputTokens)
      }
    case 'stat-cache-hit':
      return {
        label: 'Cache hit',
        value: `${formatters.cacheHitPercent(overview)}%`
      }
    case 'stat-avg-tokens-chat':
      return {
        label: 'Avg tokens / chat',
        value: formatters.formatTokenCount(overview.avgTokensPerSession)
      }
    case 'stat-runs':
      return {
        label: 'Runs',
        value: overview.runs.toLocaleString()
      }
    default:
      return null
  }
}
