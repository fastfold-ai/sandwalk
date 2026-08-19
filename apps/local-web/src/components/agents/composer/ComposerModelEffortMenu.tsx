import { Check } from 'lucide-react'

import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  type ComposerModelOption,
  formatReasoningEffortLabel
} from '@/lib/composer-models'
import { cn } from '@/lib/utils'

export function ComposerModelEffortMenu({
  option,
  optionEffort,
  optionFast,
  optionEffortOptions,
  effortMenuOpen,
  onEffortMenuOpenChange,
  onReasoningSettingsChange
}: {
  option: ComposerModelOption
  optionEffort: string
  optionFast: boolean
  optionEffortOptions: string[]
  effortMenuOpen: boolean
  onEffortMenuOpenChange: (open: boolean) => void
  onReasoningSettingsChange: (changes: {
    provider: string
    model: string
    reasoningEffort?: string
    reasoningFast?: boolean
  }) => Promise<void>
}) {
  return (
    <Popover
      modal={false}
      open={effortMenuOpen}
      onOpenChange={onEffortMenuOpenChange}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground text-xs font-medium opacity-100"
          onClick={event => {
            event.stopPropagation()
          }}
        >
          Edit
        </button>
      </PopoverTrigger>
      <PopoverContent
        side="right"
        align="start"
        sideOffset={10}
        className="z-[90] w-44 overflow-hidden p-0"
        onOpenAutoFocus={event => event.preventDefault()}
        onCloseAutoFocus={event => event.preventDefault()}
      >
        <div className="text-muted-foreground border-b px-3 py-2 text-[11px] font-medium tracking-wide uppercase">
          Effort
        </div>
        <div className="py-1">
          {optionEffortOptions.map(level => {
            const active = optionEffort === level
            return (
              <button
                key={level}
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm"
                onClick={event => {
                  event.preventDefault()
                  event.stopPropagation()
                  void onReasoningSettingsChange({
                    provider: option.provider,
                    model: option.model,
                    reasoningEffort: level
                  })
                }}
              >
                <span className="truncate">
                  {formatReasoningEffortLabel(level)}
                </span>
                {active ? (
                  <Check className="text-foreground ml-auto size-4 shrink-0" />
                ) : null}
              </button>
            )
          })}
        </div>
        {option.supportsReasoningFast !== false ? (
          <>
            <div className="text-muted-foreground border-t px-3 py-2 text-[11px] font-medium tracking-wide uppercase">
              Options
            </div>
            <div className="flex items-center justify-between gap-3 px-3 py-2.5">
              <span className="text-sm font-medium">Fast</span>
              <button
                type="button"
                role="switch"
                aria-checked={optionFast}
                aria-label="Fast mode"
                className={cn(
                  'relative h-5 w-9 shrink-0 rounded-full transition-colors',
                  optionFast ? 'bg-primary' : 'bg-muted-foreground/30'
                )}
                onClick={event => {
                  event.preventDefault()
                  event.stopPropagation()
                  void onReasoningSettingsChange({
                    provider: option.provider,
                    model: option.model,
                    reasoningFast: !optionFast
                  })
                }}
              >
                <span
                  className={cn(
                    'bg-background pointer-events-none absolute top-0.5 left-0.5 size-4 rounded-full border border-black/5 shadow-sm transition-transform',
                    optionFast && 'translate-x-4'
                  )}
                />
              </button>
            </div>
          </>
        ) : null}
      </PopoverContent>
    </Popover>
  )
}
