import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { ChevronDown, Plus } from 'lucide-react'
import { useMemo, useState } from 'react'

import { ComposerModelPickerOption } from '@/components/agents/composer/ComposerModelPickerOption'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  type ComposerModelOption,
  formatModelEffortBadge,
  formatPickerContextBadge,
  resolveComposerModelOption
} from '@/lib/composer-models'

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

  const selectedModel: ComposerModelOption =
    resolveComposerModelOption(modelOptions, runtimeSettings) ||
    (runtimeSettings
      ? {
          provider: runtimeSettings.provider,
          model: runtimeSettings.model,
          label: runtimeSettings.model,
          speed: '',
          contextWindow: null
        }
      : modelOptions[0] || {
          provider: 'anthropic',
          model: '',
          label: 'Select model',
          speed: '',
          contextWindow: null
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
  const contextBadge = formatPickerContextBadge(selectedModel.contextWindow)

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
          title={`${selectedModel.label}${contextBadge ? ` ${contextBadge}` : ''}${selectedModel.speed ? ` · ${selectedModel.speed}` : ''}${reasoningBadge ? ` · ${reasoningBadge}` : ''}`}
          className="text-muted-foreground hover:text-foreground inline-flex min-w-0 max-w-[min(100%,20rem)] items-center gap-1 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
        >
          <span className="min-w-0 truncate font-medium">
            {selectedModel.label}
          </span>
          {contextBadge ? (
            <span className="text-muted-foreground shrink-0 text-[11px]">
              {contextBadge}
            </span>
          ) : null}
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
        className="w-[min(18rem,calc(100vw-2rem))] overflow-visible p-0"
        onCloseAutoFocus={event => event.preventDefault()}
        onInteractOutside={event => {
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
                filteredModelOptions.map(option => (
                  <ComposerModelPickerOption
                    key={`${option.source || option.provider}:${option.profileId || 'cloud'}:${option.model}`}
                    option={option}
                    modelOptions={modelOptions}
                    runtimeSettings={runtimeSettings}
                    effortMenuOpen={effortMenuOpen}
                    onEffortMenuOpenChange={setEffortMenuOpen}
                    onModelSelect={onModelSelect}
                    onReasoningSettingsChange={onReasoningSettingsChange}
                    onModelSearchClear={() => setModelSearch('')}
                  />
                ))
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
