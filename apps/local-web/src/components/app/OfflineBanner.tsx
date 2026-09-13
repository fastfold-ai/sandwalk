import { WifiOff } from 'lucide-react'

import { cn } from '@/lib/utils'

interface OfflineBannerProps {
  isOffline: boolean
  message?: string
  featuresAffected?: string[]
  className?: string
}

export function OfflineBanner({
  isOffline,
  message,
  featuresAffected,
  className,
}: OfflineBannerProps) {
  if (!isOffline) return null

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-4 py-2 text-sm border-b',
        'bg-amber-50/80 dark:bg-amber-950/30',
        'text-amber-800 dark:text-amber-300',
        'border-amber-200/60 dark:border-amber-800/40',
        className
      )}
    >
      <WifiOff className="w-4 h-4 shrink-0" />
      <span className="font-medium">Offline</span>
      <span className="opacity-80 truncate">
        {message || 'Some features may not work'}
      </span>
      <span className="ml-auto opacity-60 hidden md:inline">
        {featuresAffected ? `${featuresAffected.length} features affected` : ''}
      </span>
    </div>
  )
}
