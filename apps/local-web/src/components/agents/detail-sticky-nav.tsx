import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/**
 * Fixed top chrome for capability detail pages (Back + actions).
 * Keep this outside the scroll region so content never slides underneath.
 */
export function DetailStickyNav({
  children,
  className,
  contentClassName
}: {
  children: ReactNode
  className?: string
  /** Inner max-width / padding — defaults match Skills detail. */
  contentClassName?: string
}) {
  return (
    <div
      className={cn(
        'bg-background shrink-0',
        className
      )}
    >
      <div
        className={cn(
          'mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-4 pt-4 pb-3 md:px-6',
          contentClassName
        )}
      >
        {children}
      </div>
    </div>
  )
}
