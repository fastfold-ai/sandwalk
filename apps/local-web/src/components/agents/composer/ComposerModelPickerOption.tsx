import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { Check, Star } from 'lucide-react'

import { ComposerModelEffortMenu } from '@/components/agents/composer/ComposerModelEffortMenu'
import {
  type ComposerModelOption,
  formatContextWindow,
  formatModelEffortBadge,
  formatPickerContextBadge,
  isComposerModelSelected
} from '@/lib/composer-models'
import { cn } from '@/lib/utils'

export function ComposerModelPickerOption({
  option,
  modelOptions,
  runtimeSettings,
  favorite = false,
  active = false,
  optionKey,
  effortMenuOpen,
  onEffortMenuOpenChange,
  onModelSelect,
  onReasoningSettingsChange,
  onModelSearchClear,
  onToggleFavorite,
  onClosePicker
}: {
  option: ComposerModelOption
  modelOptions: ComposerModelOption[]
  runtimeSettings: RuntimeSettings | null
  favorite?: boolean
  /** Keyboard / hover highlight (not the committed selection). */
  active?: boolean
  optionKey: string
  effortMenuOpen: boolean
  onEffortMenuOpenChange: (open: boolean) => void
  onModelSelect: (
    provider: string,
    model: string,
    profileId?: string | null
  ) => Promise<void>
  onReasoningSettingsChange?: (changes: {
    provider: string
    model: string
    reasoningEffort?: string
    reasoningFast?: boolean
  }) => Promise<void>
  onModelSearchClear: () => void
  onToggleFavorite?: () => void | Promise<void>
  /** Close picker after a plain row select — not Edit / star. */
  onClosePicker?: () => void
}) {
  const isSelected = isComposerModelSelected(
    option,
    runtimeSettings,
    modelOptions
  )
  const optionSupportsEffort = Boolean(
    option.supportsReasoningEffort ||
      (option.reasoningEffortOptions &&
        option.reasoningEffortOptions.length > 0)
  )
  const optionEffortOptions =
    option.reasoningEffortOptions && option.reasoningEffortOptions.length > 0
      ? option.reasoningEffortOptions
      : ['low', 'medium', 'high']
  // Selected row follows runtime settings so Edit → Effort updates instantly.
  const optionEffort = String(
    (isSelected
      ? runtimeSettings?.reasoningEffort
      : option.reasoningEffort) ||
      option.reasoningEffort ||
      'medium'
  )
    .trim()
    .toLowerCase()
  const optionFast = Boolean(
    isSelected
      ? (runtimeSettings?.reasoningFast ?? option.reasoningFast)
      : option.reasoningFast
  )
  const optionEffortLabel = formatModelEffortBadge({
    reasoningEffort: optionEffort,
    reasoningFast: optionFast
  })
  const contextBadge = formatPickerContextBadge(option.contextWindow)

  const selectModel = () => {
    void onModelSelect(option.provider, option.model, option.profileId)
    onModelSearchClear()
    onEffortMenuOpenChange(false)
    onClosePicker?.()
  }

  return (
    <div
      data-composer-model-selected={isSelected ? 'true' : undefined}
      data-composer-model-option={optionKey}
      data-active={active ? 'true' : undefined}
      className={cn(
        'hover:bg-muted group relative flex w-full items-center gap-2 px-3 py-1.5 text-sm',
        (isSelected || active) && 'bg-muted'
      )}
    >
      <button
        type="button"
        title={`${option.label}${
          option.speed ? ` · ${option.speed}` : ''
        }${
          contextBadge ? ` ${contextBadge}` : ''
        }${
          optionSupportsEffort
            ? ` · ${optionEffortLabel}`
            : ''
        }${
          formatContextWindow(option.contextWindow) &&
          !contextBadge
            ? ` · ${formatContextWindow(option.contextWindow)} context`
            : ''
        }`}
        className="absolute inset-0 z-0"
        aria-label={`Select ${option.label}`}
        onClick={selectModel}
      />
      <span className="pointer-events-none flex min-w-0 flex-1 flex-col gap-0.5 text-left">
        <span className="flex min-w-0 items-baseline gap-1.5 truncate">
          <span className="text-foreground truncate">{option.label}</span>
          {contextBadge ? (
            <span className="text-muted-foreground shrink-0 text-[11px]">
              {contextBadge}
            </span>
          ) : null}
        </span>
        {option.speed ? (
          <span className="text-muted-foreground truncate text-[11px] leading-none">
            {option.speed}
          </span>
        ) : null}
      </span>
      <div className="relative z-10 flex shrink-0 items-center gap-2">
        {onToggleFavorite ? (
          <button
            type="button"
            title={favorite ? 'Unpin favorite' : 'Pin favorite'}
            aria-label={favorite ? 'Unpin favorite' : 'Pin favorite'}
            className={cn(
              'rounded-sm p-0.5',
              favorite
                ? 'text-muted-foreground'
                : 'text-muted-foreground/40 hover:text-muted-foreground opacity-0 group-hover:opacity-100 group-data-[active=true]:opacity-100 focus-visible:opacity-100'
            )}
            onClick={event => {
              event.preventDefault()
              event.stopPropagation()
              void onToggleFavorite()
            }}
          >
            <Star
              className={cn('size-2.5', favorite && 'fill-current')}
            />
          </button>
        ) : null}
        {optionSupportsEffort ? (
          isSelected && onReasoningSettingsChange ? (
            <ComposerModelEffortMenu
              option={option}
              optionEffort={optionEffort}
              optionFast={optionFast}
              optionEffortOptions={optionEffortOptions}
              effortMenuOpen={effortMenuOpen}
              onEffortMenuOpenChange={onEffortMenuOpenChange}
              onReasoningSettingsChange={onReasoningSettingsChange}
            />
          ) : (
            <>
              <span className="text-muted-foreground pointer-events-none text-xs whitespace-nowrap group-hover:hidden group-data-[active=true]:hidden">
                {optionEffortLabel}
              </span>
              {onReasoningSettingsChange ? (
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground hidden text-xs font-medium group-hover:inline group-data-[active=true]:inline"
                  onClick={event => {
                    event.preventDefault()
                    event.stopPropagation()
                    void (async () => {
                      await onModelSelect(
                        option.provider,
                        option.model,
                        option.profileId
                      )
                      onModelSearchClear()
                      onEffortMenuOpenChange(true)
                    })()
                  }}
                >
                  Edit
                </button>
              ) : null}
            </>
          )
        ) : null}
        {isSelected ? (
          <Check className="text-foreground pointer-events-none size-4 shrink-0" />
        ) : null}
      </div>
    </div>
  )
}
