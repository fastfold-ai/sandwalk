import type { ToolSummary } from '@sandwalk/agent-ui-core'

import { cn } from '@/lib/utils'

export function ToolToggle({
  enabled,
  pending,
  label,
  onToggle,
  locked = false
}: {
  enabled: boolean
  pending?: boolean
  label: string
  onToggle: () => void
  /** Core tools: always on; toggle is non-interactive. */
  locked?: boolean
}) {
  const blocked = pending || locked
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      aria-disabled={locked || undefined}
      title={locked ? 'Core tool — always enabled' : undefined}
      disabled={blocked}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700',
        blocked && 'cursor-not-allowed opacity-60'
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        if (locked) return
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

export function toolIsToggleable(tool: ToolSummary): boolean {
  if (tool.toggleable === false) return false
  if (tool.tier === 'core') return false
  return true
}

export function statusClass(status: ToolSummary['status']) {
  if (status === 'experimental')
    return 'text-amber-700 bg-amber-500/10 dark:text-amber-300'
  if (status === 'guarded')
    return 'text-violet-700 bg-violet-500/10 dark:text-violet-300'
  return 'text-muted-foreground bg-muted'
}

export function tierClass(tier: ToolSummary['tier']) {
  if (tier === 'core')
    return 'text-sky-700 bg-sky-500/10 dark:text-sky-300'
  return 'text-muted-foreground bg-muted'
}

export function toolTier(tool: ToolSummary): 'core' | 'extra' {
  return tool.tier === 'core' ? 'core' : 'extra'
}

export function filterButtonClass(active: boolean) {
  return cn(
    'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
    active
      ? 'bg-muted text-foreground'
      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
  )
}
