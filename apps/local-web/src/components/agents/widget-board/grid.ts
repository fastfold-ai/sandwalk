import type { WidgetSize } from '@sandwalk/agent-ui-core'

import { cn } from '@/lib/utils'

export function colSpanClass(size: WidgetSize): string {
  if (size === 'lg') return 'col-span-12'
  if (size === 'md') return 'col-span-12 sm:col-span-6'
  return 'col-span-6 sm:col-span-3'
}

export function cardPaddingClass(size: WidgetSize): string {
  if (size === 'lg') return 'p-5 sm:p-6'
  if (size === 'md') return 'p-4'
  return 'p-3'
}

export function valueTextClass(size: WidgetSize): string {
  if (size === 'lg') return 'text-3xl font-semibold tracking-tight tabular-nums'
  if (size === 'md') return 'text-xl font-semibold tracking-tight tabular-nums'
  return 'text-lg font-semibold tracking-tight tabular-nums'
}

/** Fixed footprint for SM so grid neighbors (heatmap/bench) can't stretch them. */
export function widgetShellClass(size: WidgetSize, className?: string): string {
  return cn(
    'bg-card relative flex flex-col rounded-xl border',
    cardPaddingClass(size),
    size === 'sm' &&
      'h-[5.75rem] shrink-0 justify-between overflow-hidden',
    // MD/LG fill the grid cell so side-by-side cards share one row height.
    size === 'md' && 'h-full min-h-[14rem]',
    size === 'lg' && 'h-full min-h-0',
    className
  )
}

/**
 * Shared shell for full-width hero cards (Usage + Project description) so LG
 * rows match in height whether the body is a big number or scrollable text.
 */
export function heroShellClass(size: WidgetSize, className?: string): string {
  return widgetShellClass(
    size,
    cn(
      size === 'lg' && 'h-[8.25rem] min-h-[8.25rem]',
      className
    )
  )
}
