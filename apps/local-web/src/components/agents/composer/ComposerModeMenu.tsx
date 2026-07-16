import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronDown,
  Infinity as InfinityIcon,
  ListChecks
} from 'lucide-react'
import { useState } from 'react'

import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'

type ModeId = 'agent' | 'plan'

/** Mustard / gold accents for Plan mode (chip + send button). */
export const planModeAccent = {
  chip: 'bg-[#f0e6c8] text-[#9a7429] hover:bg-[#e8d9b0] dark:bg-[#9a7429]/25 dark:text-[#e8c97a] dark:hover:bg-[#9a7429]/35',
  send: 'bg-[#9a7429] text-white hover:bg-[#825f22] [&_svg]:text-white'
} as const

export function ComposerModeMenu({
  runtimeSettings,
  onPlanModeChange
}: {
  runtimeSettings: RuntimeSettings | null
  onPlanModeChange: (planMode: boolean) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const planMode = Boolean(runtimeSettings?.planMode)
  const active: ModeId = planMode ? 'plan' : 'agent'

  const select = async (mode: ModeId) => {
    const nextPlan = mode === 'plan'
    setOpen(false)
    if (nextPlan === planMode) return
    try {
      await onPlanModeChange(nextPlan)
    } catch (error) {
      console.error('Failed to update plan mode', error)
    }
  }

  return (
    <Popover modal={false} open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            'inline-flex h-7 shrink-0 items-center gap-1 rounded-full px-2.5 text-xs font-medium',
            planMode
              ? planModeAccent.chip
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          )}
          aria-label="Agent mode"
        >
          {planMode ? (
            <ListChecks className="size-3.5" />
          ) : (
            <InfinityIcon className="size-3.5" />
          )}
          <span>{planMode ? 'Plan' : 'Agent'}</span>
          <ChevronDown className="size-3 opacity-70" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-44 p-1">
        {(
          [
            { id: 'agent' as const, label: 'Agent', icon: InfinityIcon },
            { id: 'plan' as const, label: 'Plan', icon: ListChecks }
          ] as const
        ).map(option => {
          const Icon = option.icon
          const selected = active === option.id
          return (
            <button
              key={option.id}
              type="button"
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                selected ? 'bg-muted' : 'hover:bg-muted/70'
              )}
              onClick={() => void select(option.id)}
            >
              <Icon className="text-muted-foreground size-3.5 shrink-0" />
              <span className="flex-1">{option.label}</span>
              {selected ? <Check className="size-3.5 opacity-70" /> : null}
            </button>
          )
        })}
      </PopoverContent>
    </Popover>
  )
}
