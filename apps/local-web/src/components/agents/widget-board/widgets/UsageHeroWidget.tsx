import type { UsageOverview, WidgetSize } from '@sandwalk/agent-ui-core'

import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import { formatTokenCount } from '../../usage-overview-utils'
import { valueTextClass, widgetShellClass } from '../grid'

export function UsageHeroWidget({
  overview,
  error,
  size,
  scopeLabel
}: {
  overview: UsageOverview | null
  error: string | null
  size: WidgetSize
  scopeLabel?: string
}) {
  return (
    <div className={widgetShellClass(size)}>
      <div>
        <p className="text-muted-foreground text-xs font-light tracking-wide">
          Usage{scopeLabel ? ` · ${scopeLabel}` : ''}
        </p>
        {overview ? (
          <p className={cn('mt-1', valueTextClass(size === 'sm' ? 'md' : size))}>
            {formatTokenCount(overview.lifetimeTokens)}
          </p>
        ) : error ? (
          <p className={cn('mt-1', valueTextClass('md'))}>—</p>
        ) : (
          <Skeleton className="mt-2 h-9 w-28" />
        )}
        <p className="text-muted-foreground mt-1 text-[11px]">
          Lifetime tokens
        </p>
      </div>
      {error ? (
        <p className="text-muted-foreground mt-4 text-sm">{error}</p>
      ) : null}
    </div>
  )
}
