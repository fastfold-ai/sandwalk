import { Wifi, WifiOff } from 'lucide-react'

import { cn } from '@/lib/utils'

interface OfflineBannerProps {
  isOffline: boolean
  justOnline?: boolean
  message?: string
  featuresAffected?: string[]
  className?: string
}

export function OfflineBanner({
  isOffline,
  justOnline = false,
  message,
  featuresAffected,
  className
}: OfflineBannerProps) {
  if (!isOffline && !justOnline) return null

  const online = justOnline && !isOffline

  return (
    <div
      role="status"
      className={cn(
        'flex shrink-0 items-center gap-2 border-t px-4 py-1.5 text-sm',
        online
          ? 'border-emerald-200/60 bg-emerald-50/80 text-emerald-800 dark:border-emerald-800/40 dark:bg-emerald-950/30 dark:text-emerald-300'
          : 'border-amber-200/60 bg-amber-50/80 text-amber-800 dark:border-amber-800/40 dark:bg-amber-950/30 dark:text-amber-300',
        className
      )}
    >
      {online ? (
        <Wifi className="size-4 shrink-0" />
      ) : (
        <WifiOff className="size-4 shrink-0" />
      )}
      <span className="font-medium">{online ? 'Back online' : 'Offline'}</span>
      <span className="truncate opacity-80">
        {online
          ? 'Connection restored'
          : message || 'Some features may not work'}
      </span>
      {!online && featuresAffected?.length ? (
        <span className="ml-auto hidden opacity-60 md:inline">
          {featuresAffected.length} features affected
        </span>
      ) : null}
    </div>
  )
}
