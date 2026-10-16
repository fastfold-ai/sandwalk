import type { RuntimeSettings } from '@sandwalk/agent-ui-core'

import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export type RuntimeDraft = {
  toolMode: 'ptc' | 'native'
  groupToolTraces: boolean
  toolTraceDetailLimit: string
  backgroundWatchTimeoutS: string
  interruptDrainTimeoutS: string
  parallelMaxThreads: string
  toolHealthEnabled: boolean
  toolHealthFailThreshold: string
  toolHealthSuppressSeconds: string
  maxConcurrentRuns: string
  minFreeMemoryGb: string
}

export function settingsToDraft(settings: RuntimeSettings | null): RuntimeDraft {
  return {
    toolMode: settings?.toolMode === 'native' ? 'native' : 'ptc',
    groupToolTraces: settings?.groupToolTraces ?? true,
    toolTraceDetailLimit: String(settings?.toolTraceDetailLimit ?? 1),
    backgroundWatchTimeoutS: String(settings?.backgroundWatchTimeoutS ?? 7200),
    interruptDrainTimeoutS: String(settings?.interruptDrainTimeoutS ?? 10),
    parallelMaxThreads: String(settings?.parallelMaxThreads ?? 5),
    toolHealthEnabled: settings?.toolHealthEnabled ?? true,
    toolHealthFailThreshold: String(settings?.toolHealthFailThreshold ?? 2),
    toolHealthSuppressSeconds: String(
      settings?.toolHealthSuppressSeconds ?? 900
    ),
    maxConcurrentRuns: String(settings?.maxConcurrentRuns ?? 0),
    minFreeMemoryGb: String(
      Math.round(((settings?.minFreeMemoryMb ?? 2048) / 1024) * 10) / 10
    )
  }
}

export function clampInt(
  value: string,
  minimum: number,
  maximum: number,
  fallback: number
) {
  const n = Math.round(Number(value))
  if (!Number.isFinite(n)) return fallback
  return Math.max(minimum, Math.min(maximum, n))
}

export function RuntimeToggle({
  enabled,
  disabled,
  label,
  onToggle
}: {
  enabled: boolean
  disabled?: boolean
  label: string
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      disabled={disabled}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700',
        disabled && 'cursor-not-allowed opacity-60'
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

export function RuntimeNumberField({
  label,
  hint,
  value,
  min,
  max,
  step,
  disabled,
  onChange
}: {
  label: string
  hint?: string
  value: string
  min: number
  max: number
  step?: number
  disabled?: boolean
  onChange: (value: string) => void
}) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <Input
        type="number"
        min={min}
        max={max}
        step={step ?? 1}
        className="w-40"
        value={value}
        disabled={disabled}
        onChange={event => onChange(event.target.value)}
      />
      {hint ? (
        <p className="text-muted-foreground text-xs leading-relaxed">{hint}</p>
      ) : null}
    </label>
  )
}
