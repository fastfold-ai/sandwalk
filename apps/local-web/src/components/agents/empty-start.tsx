import { useEffect, useState } from 'react'

import { cn } from '@/lib/utils'

export const PLUS_MENU_OPEN_EVENT = 'sandwalk:open-plus-menu'
export const PLAN_MODE_EVENT = 'sandwalk:plan-mode'
const PLAN_MODE_STORAGE_KEY = 'sandwalk.plan-mode'
const PLUS_MENU_STORAGE_KEY = 'sandwalk.plus-menu'

export type PlusMenuFlyout = 'skills' | 'mcp' | 'specialist' | 'sandbox'

/** Open the composer + menu on the matching row. Survives a hop to New Agent. */
export function openPlusMenu(flyout: PlusMenuFlyout) {
  try {
    sessionStorage.setItem(PLUS_MENU_STORAGE_KEY, flyout)
  } catch {
    // Private mode: the event below still opens it if the menu is mounted.
  }
  window.dispatchEvent(
    new CustomEvent(PLUS_MENU_OPEN_EVENT, { detail: { flyout } })
  )
}

/** Turn plan mode on or off. Survives a hop onto New Agent. */
export function requestPlanMode(enabled: boolean) {
  try {
    sessionStorage.setItem(PLAN_MODE_STORAGE_KEY, enabled ? '1' : '0')
  } catch {
    // The event still reaches a composer that is already mounted.
  }
  window.dispatchEvent(
    new CustomEvent(PLAN_MODE_EVENT, { detail: { enabled } })
  )
}

export function takeQueuedPlanMode(): boolean | null {
  try {
    const value = sessionStorage.getItem(PLAN_MODE_STORAGE_KEY)
    if (value !== '1' && value !== '0') return null
    sessionStorage.removeItem(PLAN_MODE_STORAGE_KEY)
    return value === '1'
  } catch {
    return null
  }
}

export function takeQueuedPlusMenu(): PlusMenuFlyout | null {
  try {
    const value = sessionStorage.getItem(PLUS_MENU_STORAGE_KEY)
    if (!value) return null
    sessionStorage.removeItem(PLUS_MENU_STORAGE_KEY)
    if (
      value === 'skills' ||
      value === 'mcp' ||
      value === 'specialist' ||
      value === 'sandbox'
    ) {
      return value
    }
  } catch {
    return null
  }
  return null
}

export const EMPTY_START_TIPS = [
  'Type / to attach a skill or an MCP server.',
  'Sandbox a run on Modal when you want a clean machine.',
  'Local models stay on this machine. Cloud models use your provider key.',
  'The ring next to Send is input usage. Compact it when the window fills up.',
  '@ mentions a file from the workspace.',
  '⌘D splits the current pane to the right.',
  'Pin a chat to keep it at the front of the list.'
]

export function useEmptyStartTip() {
  const [index, setIndex] = useState(
    () => Math.floor(Math.random() * EMPTY_START_TIPS.length)
  )
  useEffect(() => {
    const timer = window.setInterval(() => {
      setIndex(current => (current + 1) % EMPTY_START_TIPS.length)
    }, 9000)
    return () => window.clearInterval(timer)
  }, [])
  return EMPTY_START_TIPS[index]
}

export function EmptyStartTip({ className }: { className?: string }) {
  const tip = useEmptyStartTip()
  return (
    <p
      className={cn(
        'text-muted-foreground/45 text-center text-[12px] leading-relaxed',
        className
      )}
    >
      {tip}
    </p>
  )
}

export function EmptyStartActions({
  className,
  onNewAgent,
  onTerminal,
  onSkills,
  onSandbox,
  onPlan
}: {
  className?: string
  onNewAgent?: () => void
  onTerminal?: () => void
  onSkills?: () => void
  onSandbox?: () => void
  onPlan?: () => void
}) {
  const actions = [
    onPlan
      ? {
          label: 'Plan',
          hint: '⇧Tab',
          onClick: onPlan
        }
      : null,
    onNewAgent ? { label: 'New Agent', onClick: onNewAgent } : null,
    onTerminal ? { label: 'Terminal', onClick: onTerminal } : null,
    onSkills ? { label: 'Skills', onClick: onSkills } : null,
    onSandbox ? { label: 'Run in sandbox', onClick: onSandbox } : null
  ].filter(
    (item): item is { label: string; hint?: string; onClick: () => void } =>
      Boolean(item)
  )

  if (actions.length === 0) return null
  return (
    <div className={cn('flex w-full flex-wrap items-center justify-start gap-2', className)}>
      {actions.map(action => (
        <button
          key={action.label}
          type="button"
          onClick={action.onClick}
          className="text-muted-foreground/70 hover:text-foreground hover:bg-foreground/5 rounded-full border border-foreground/10 px-3 py-1 text-[12px]"
        >
          {action.label}
          {action.hint ? (
            <span className="text-muted-foreground/50 ml-1.5 text-[11px]">
              {action.hint}
            </span>
          ) : null}
        </button>
      ))}
    </div>
  )
}
