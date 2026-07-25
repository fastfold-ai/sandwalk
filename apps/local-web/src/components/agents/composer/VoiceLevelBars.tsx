import { cn } from '@/lib/utils'

/** Live mic-level strip — each bar is a recent RMS sample, newest on the right. */
export function VoiceLevelBars({
  levels,
  count = 12,
  className
}: {
  levels: number[]
  count?: number
  className?: string
}) {
  return (
    <span className={cn('voice-listen-bars', className)} aria-hidden="true">
      {Array.from({ length: count }, (_, index) => {
        const level = levels[levels.length - count + index] ?? 0
        const clamped = Math.min(1, Math.max(0, level))
        return (
          <i
            key={index}
            style={{ height: `${Math.max(2, Math.round(2 + clamped * 16))}px` }}
          />
        )
      })}
    </span>
  )
}
