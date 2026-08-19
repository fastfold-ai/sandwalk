import { Check, Loader } from 'lucide-react'

import { cn } from '@/lib/utils'

export function BusyConfirmOverlay({
  open,
  phase,
  message,
  description
}: {
  open: boolean
  phase: 'working' | 'done'
  message: string
  description?: string
}) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background flex w-full max-w-sm flex-col items-center gap-3 rounded-xl border px-6 py-8 shadow-lg">
        <div
          className={cn(
            'flex size-12 items-center justify-center rounded-full',
            phase === 'done'
              ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
              : 'bg-muted text-foreground'
          )}
        >
          {phase === 'done' ? (
            <Check className="size-6" />
          ) : (
            <Loader className="size-6 animate-spin" />
          )}
        </div>
        <div className="space-y-1 text-center">
          <p className="text-base font-semibold">{message}</p>
          {description ? (
            <p className="text-muted-foreground text-sm">{description}</p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
