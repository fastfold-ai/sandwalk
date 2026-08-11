import { useEffect, useState } from 'react'

import { cn } from '@/lib/utils'

import { SCAN_PHASES } from './doctor-view-utils'

export function DoctorScanProgress({ active }: { active: boolean }) {
  const [progress, setProgress] = useState(8)
  const [phaseIndex, setPhaseIndex] = useState(0)

  useEffect(() => {
    if (!active) {
      setProgress(100)
      return
    }
    setProgress(8)
    setPhaseIndex(0)
    const progressTimer = window.setInterval(() => {
      setProgress(prev => {
        if (prev >= 92) return prev
        const step = prev < 40 ? 6 : prev < 70 ? 3 : 1.5
        return Math.min(92, prev + step)
      })
    }, 400)
    const phaseTimer = window.setInterval(() => {
      setPhaseIndex(prev => (prev + 1) % SCAN_PHASES.length)
    }, 1800)
    return () => {
      window.clearInterval(progressTimer)
      window.clearInterval(phaseTimer)
    }
  }, [active])

  return (
    <div
      className="border-border/60 bg-muted/20 rounded-lg border px-4 py-5"
      aria-busy={active}
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            {active ? 'Doctor scan running' : 'Doctor scan complete'}
          </p>
          <p className="text-muted-foreground mt-1 text-sm">
            {active ? SCAN_PHASES[phaseIndex] : 'Results are ready below.'}
          </p>
        </div>
        <span className="text-muted-foreground shrink-0 text-xs tabular-nums">
          {Math.round(progress)}%
        </span>
      </div>
      <div className="bg-muted mt-4 h-2 overflow-hidden rounded-full">
        <div
          className={cn(
            'bg-foreground/80 h-full rounded-full transition-[width] duration-300 ease-out',
            active && 'animate-pulse'
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}
