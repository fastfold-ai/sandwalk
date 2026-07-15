import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { Check, ChevronDown, Plus } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  formatModelEffortBadge,
  formatReasoningEffortLabel,
  isComposerModelSelected,
  resolveComposerModelOption,
  type ComposerModelOption
} from '@/lib/composer-models'
import { cn } from '@/lib/utils'

export function ComposerModelPicker({
  modelOptions,
  runtimeSettings,
  onModelSelect,
  onReasoningSettingsChange,
  onAddModels
}: {
  modelOptions: ComposerModelOption[]
  runtimeSettings: RuntimeSettings | null
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
  onAddModels?: () => void
}) {
  const [modelPickerOpen, setModelPickerOpen] = useState(false)
  const [modelSearch, setModelSearch] = useState('')
  const [effortMenuOpen, setEffortMenuOpen] = useState(false)

  const selectedModel =
    resolveComposerModelOption(modelOptions, runtimeSettings) ||
    (runtimeSettings
      ? {
          provider: runtimeSettings.provider,
          model: runtimeSettings.model,
          label: runtimeSettings.model,
          speed: ''
        }
      : modelOptions[0] || {
          provider: 'anthropic',
          model: '',
          label: 'Select model',
          speed: ''
        })

  const supportsReasoningEffort = Boolean(
    selectedModel.supportsReasoningEffort ||
      (selectedModel.reasoningEffortOptions &&
        selectedModel.reasoningEffortOptions.length > 0)
  )
  const selectedEffort = String(selectedModel.reasoningEffort || 'medium')
    .trim()
    .toLowerCase()
  const selectedFast = Boolean(selectedModel.reasoningFast)
  const reasoningBadge = supportsReasoningEffort
    ? formatModelEffortBadge({
        reasoningEffort: selectedEffort,
        reasoningFast: selectedFast
      })
    : null

  const filteredModelOptions = useMemo(() => {
    const needle = modelSearch.trim().toLowerCase()
    if (!needle) return modelOptions
    return modelOptions.filter(option => {
      const haystack = [
        option.label,
        option.model,
        option.provider,
        option.speed || '',
        option.source || '',
        option.profileId || ''
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [modelOptions, modelSearch])

  return (
    <Popover
      open={modelPickerOpen}
      onOpenChange={open => {
        setModelPickerOpen(open)
        if (!open) {
          setModelSearch('')
          setEffortMenuOpen(false)
        }
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          title={`${selectedModel.label}${selectedModel.speed ? ` · ${selectedModel.speed}` : ''}${reasoningBadge ? ` · ${reasoningBadge}` : ''}`}
          className="text-muted-foreground hover:text-foreground inline-flex min-w-0 max-w-[min(100%,20rem)] items-center gap-1 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
        >
          <span className="min-w-0 truncate font-medium">
            {selectedModel.label}
          </span>
          {reasoningBadge ? (
            <span className="text-muted-foreground shrink-0 text-[11px]">
              {reasoningBadge}
            </span>
          ) : selectedModel.speed ? (
            <span className="text-muted-foreground shrink-0 text-[11px]">
              {selectedModel.speed}
            </span>
          ) : null}
          <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        side="top"
        className="w-[min(28rem,calc(100vw-2rem))] overflow-visible p-0"
        onCloseAutoFocus={event => event.preventDefault()}
        onInteractOutside={event => {
          // Nested Edit panel is portaled; don't dismiss the model list.
          if (effortMenuOpen) event.preventDefault()
        }}
        onFocusOutside={event => {
          if (effortMenuOpen) event.preventDefault()
        }}
        onPointerDownOutside={event => {
          if (effortMenuOpen) event.preventDefault()
        }}
      >
        <div className="bg-popover overflow-hidden rounded-md border-0">
          <div className="bg-popover border-b px-3 py-2">
            <Input
              value={modelSearch}
              onChange={event => setModelSearch(event.target.value)}
              placeholder="Search models"
              className="h-7 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
              autoFocus
            />
          </div>
          <ScrollArea className="h-72 w-full">
            <div className="w-full py-1">
              {modelOptions.length === 0 ? (
                <div className="text-muted-foreground px-3 py-3 text-sm">
                  No enabled models. Turn models on in Dashboard → Models.
                </div>
              ) : filteredModelOptions.length === 0 ? (
                <div className="text-muted-foreground px-3 py-3 text-sm">
                  No models match “{modelSearch.trim()}”.
                </div>
              ) : (
                filteredModelOptions.map(option => {
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
                    option.reasoningEffortOptions &&
                    option.reasoningEffortOptions.length > 0
                      ? option.reasoningEffortOptions
                      : ['low', 'medium', 'high']
                  const optionEffort = String(
                    option.reasoningEffort || 'medium'
                  )
                    .trim()
                    .toLowerCase()
                  const optionFast = Boolean(option.reasoningFast)
                  const optionEffortLabel = formatModelEffortBadge({
                    reasoningEffort: optionEffort,
                    reasoningFast: optionFast
                  })
                  const selectModel = () => {
                    void onModelSelect(
                      option.provider,
                      option.model,
                      option.profileId
                    )
                    setModelSearch('')
                    if (!optionSupportsEffort) {
                      setEffortMenuOpen(false)
                    }
                  }
                  return (
                    <div
                      key={`${option.source || option.provider}:${option.profileId || 'cloud'}:${option.model}`}
                      className={cn(
                        'hover:bg-muted group relative flex w-full items-center gap-2 px-3 py-1.5 text-sm',
                        isSelected && 'bg-muted'
                      )}
                    >
                      <button
                        type="button"
                        title={`${option.label}${
                          optionSupportsEffort
                            ? ` ${optionEffortLabel}`
                            : option.speed
                              ? ` · ${option.speed}`
                              : ''
                        }`}
                        className="absolute inset-0 z-0"
                        aria-label={`Select ${option.label}`}
                        onClick={selectModel}
                      />
                      <span className="pointer-events-none flex min-w-0 flex-1 items-baseline gap-1.5 truncate text-left">
                        <span className="text-foreground truncate">
                          {option.label}
                        </span>
                        {optionSupportsEffort ? (
                          <span className="text-muted-foreground shrink-0 text-[11px]">
                            {optionEffortLabel}
                          </span>
                        ) : null}
                      </span>
                      <div className="relative z-10 flex shrink-0 items-center gap-2">
                        {optionSupportsEffort && onReasoningSettingsChange ? (
                          isSelected ? (
                            <Popover
                              modal={false}
                              open={effortMenuOpen}
                              onOpenChange={setEffortMenuOpen}
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
                                className="w-44 overflow-hidden p-0"
                                onOpenAutoFocus={event =>
                                  event.preventDefault()
                                }
                                onCloseAutoFocus={event =>
                                  event.preventDefault()
                                }
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
                                <div className="text-muted-foreground border-t px-3 py-2 text-[11px] font-medium tracking-wide uppercase">
                                  Options
                                </div>
                                <div className="flex items-center justify-between gap-3 px-3 py-2.5">
                                  <span className="text-sm font-medium">
                                    Fast
                                  </span>
                                  <button
                                    type="button"
                                    role="switch"
                                    aria-checked={optionFast}
                                    aria-label="Fast mode"
                                    className={cn(
                                      'relative h-5 w-9 shrink-0 rounded-full transition-colors',
                                      optionFast
                                        ? 'bg-primary'
                                        : 'bg-muted-foreground/30'
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
                              </PopoverContent>
                            </Popover>
                          ) : (
                            <button
                              type="button"
                              className="text-muted-foreground hover:text-foreground text-xs font-medium opacity-0 transition-opacity group-hover:opacity-100"
                              onClick={event => {
                                event.preventDefault()
                                event.stopPropagation()
                                void (async () => {
                                  await onModelSelect(
                                    option.provider,
                                    option.model,
                                    option.profileId
                                  )
                                  setModelSearch('')
                                  setEffortMenuOpen(true)
                                })()
                              }}
                            >
                              Edit
                            </button>
                          )
                        ) : null}
                        {option.speed &&
                        !isSelected &&
                        !optionSupportsEffort ? (
                          <span className="text-muted-foreground pointer-events-none text-xs whitespace-nowrap">
                            {option.speed}
                          </span>
                        ) : null}
                        {isSelected ? (
                          <Check className="text-foreground pointer-events-none size-4 shrink-0" />
                        ) : null}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </ScrollArea>
          {onAddModels ? (
            <div className="border-t p-1">
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
                onClick={() => {
                  setModelPickerOpen(false)
                  setModelSearch('')
                  setEffortMenuOpen(false)
                  onAddModels()
                }}
              >
                <Plus className="size-3.5 shrink-0" />
                Add Models
              </button>
            </div>
          ) : null}
        </div>
      </PopoverContent>
    </Popover>
  )
}
