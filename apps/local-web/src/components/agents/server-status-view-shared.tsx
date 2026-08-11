import { type ReactNode } from 'react'

import { cn } from '@/lib/utils'

export function formatBytes(bytes: number): string {
  const value = Math.max(0, bytes)
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB'] as const
  let n = value / 1024
  for (let i = 0; i < units.length; i += 1) {
    if (n < 1024 || i === units.length - 1) {
      return `${n.toFixed(1)} ${units[i]}`
    }
    n /= 1024
  }
  return `${value} B`
}

export function formatUptime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (days > 0) return `${days}d ${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m ${secs}s`
  return `${secs}s`
}

export function formatGpuLabel(
  chipName?: string | null,
  gpuCores?: number | null
): string | null {
  const chip = chipName?.trim()
  const cores = gpuCores != null && gpuCores > 0 ? gpuCores : null
  if (chip && cores != null) return `${chip} · ${cores} cores`
  if (chip) return chip
  if (cores != null) return `${cores} cores`
  return null
}

export function MemoryBar({ used, total }: { used: number; total: number }) {
  const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0
  return (
    <div className="flex min-w-[8rem] flex-1 items-center gap-3 sm:min-w-[12rem]">
      <div className="bg-muted h-1.5 flex-1 overflow-hidden rounded-full">
        <div
          className="bg-foreground/70 h-full rounded-full transition-[width] duration-300"
          style={{ width: `${Math.max(pct, pct > 0 ? 0.8 : 0)}%` }}
        />
      </div>
      <span className="text-muted-foreground shrink-0 text-sm tabular-nums">
        {formatBytes(used)} / {formatBytes(total)}
      </span>
    </div>
  )
}

export function SectionLabel({
  children,
  subtitle
}: {
  children: ReactNode
  subtitle?: string
}) {
  return (
    <div className="mb-2 space-y-1">
      <div className="text-muted-foreground text-[11px] font-medium tracking-wider uppercase">
        {children}
      </div>
      {subtitle ? (
        <p className="text-muted-foreground text-sm">{subtitle}</p>
      ) : null}
    </div>
  )
}

export function MetaRow({
  label,
  children,
  hint,
  stretch
}: {
  label: string
  children: ReactNode
  hint?: string
  stretch?: boolean
}) {
  return (
    <div
      className={cn(
        'flex gap-4 border-b border-border/60 py-3.5 last:border-b-0',
        stretch ? 'items-center' : 'items-start justify-between'
      )}
    >
      <div className="min-w-[7.5rem] shrink-0">
        <div className="text-sm font-medium">{label}</div>
        {hint ? (
          <div className="text-muted-foreground mt-0.5 text-xs">{hint}</div>
        ) : null}
      </div>
      <div
        className={cn(
          'text-muted-foreground text-sm',
          stretch ? 'min-w-0 flex-1' : 'max-w-[min(100%,20rem)] text-right'
        )}
      >
        {children}
      </div>
    </div>
  )
}
