import type { ReactNode } from 'react'

import { DesktopTitleBar } from '@/components/DesktopTitleBar'
import { cn } from '@/lib/utils'

/** Full-screen gate chrome (login / connect / waiting) with macOS overlay drag bar. */
export function DesktopGateFrame({
  children,
  className
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'bg-background flex h-full min-h-full w-full flex-col overflow-hidden',
        className
      )}
    >
      <DesktopTitleBar />
      <div className="relative min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  )
}
