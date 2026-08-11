import { Cpu } from 'lucide-react'

import { cn } from '@/lib/utils'

export function ModelToggle({
  enabled,
  pending,
  label,
  onToggle
}: {
  enabled: boolean
  pending?: boolean
  label: string
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      disabled={pending}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700',
        pending && 'cursor-not-allowed opacity-60'
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onToggle()
      }}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          enabled ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}

export function ProfileBackendIcon({
  icon,
  className
}: {
  icon: string
  className?: string
}) {
  if (icon === 'cpu') {
    return <Cpu className={cn('text-muted-foreground size-4 shrink-0', className)} />
  }
  return (
    <img
      src={icon}
      alt=""
      className={cn('size-4 shrink-0 rounded-sm object-cover', className)}
    />
  )
}
