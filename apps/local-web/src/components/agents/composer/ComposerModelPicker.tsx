import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { ChevronDown, Plus } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { ComposerModelPickerOption } from '@/components/agents/composer/ComposerModelPickerOption'
import {
  composerModelOptionKey,
  useComposerModelPickerNav
} from '@/components/agents/composer/useComposerModelPickerNav'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  type ComposerModelOption,
  type ComposerModelPreferences,
  composerModelPrefKey,
  formatModelEffortBadge,
  formatPickerContextBadge,
  rankComposerModelOptions,
  resolveComposerModelOption
} from '@/lib/composer-models'

export function ComposerModelPicker({
  modelOptions,
  runtimeSettings,
  onModelSelect,
  onReasoningSettingsChange,
  onAddModels,
  onLoadModelPreferences,
  onToggleModelFavorite,
  onFocusComposer,
  triggerLabel
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
  onLoadModelPreferences?: () => Promise<ComposerModelPreferences>
  onToggleModelFavorite?: (option: ComposerModelOption) => Promise<{
    favorite: boolean
    favorites: string[]
  }>
  /** Return focus to the chat draft after a model is chosen. */
  onFocusComposer?: () => void
  /** Override the trigger label (e.g. Bench “Compare”). */
  triggerLabel?: string
}) {
  const [modelPickerOpen, setModelPickerOpen] = useState(false)
  const [modelSearch, setModelSearch] = useState('')
  const [effortMenuOpen, setEffortMenuOpen] = useState(false)
  const [preferences, setPreferences] = useState<ComposerModelPreferences>({
    favorites: [],
    recent: []
  })

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

  const sections = useMemo(
    () => rankComposerModelOptions(modelOptions, modelSearch, preferences),
    [modelOptions, modelSearch, preferences]
  )

  const favoriteSet = useMemo(
    () => new Set(preferences.favorites),
    [preferences.favorites]
  )

  const nav = useComposerModelPickerNav({
    open: modelPickerOpen,
    search: modelSearch,
    sections,
    selected: selectedModel,
    effortMenuOpen
  })

  useEffect(() => {
    if (!modelPickerOpen || !onLoadModelPreferences) return
    let cancelled = false
    void onLoadModelPreferences()
      .then(next => {
        if (!cancelled) setPreferences(next)
      })
      .catch(() => {
        // Keep last known favorites/recent if the request fails.
      })
    return () => {
      cancelled = true
    }
  }, [modelPickerOpen, onLoadModelPreferences])

  const closePicker = () => {
    setModelPickerOpen(false)
    setModelSearch('')
    setEffortMenuOpen(false)
  }

  const focusComposerSoon = () => {
    window.requestAnimationFrame(() => {
      onFocusComposer?.()
    })
  }

  const selectModelAndClose = (option: ComposerModelOption) => {
    void onModelSelect(option.provider, option.model, option.profileId)
    closePicker()
    focusComposerSoon()
  }

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
          title={`${selectedModel.label}${selectedModel.speed ? ` · ${selectedModel.speed}` : ''}${contextBadge ? ` ${contextBadge}` : ''}${reasoningBadge ? ` · ${reasoningBadge}` : ''}`}
          className="text-muted-foreground hover:text-foreground inline-flex min-w-0 max-w-[min(100%,20rem)] items-center gap-1 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
        >
          <span className="min-w-0 truncate font-medium">
            {triggerLabel || selectedModel.label}
          </span>
          {!triggerLabel && contextBadge ? (
            <span className="text-muted-foreground shrink-0 text-[11px]">
              {contextBadge}
            </span>
          ) : null}
          {!triggerLabel && reasoningBadge ? (
            <span className="text-muted-foreground shrink-0 text-[11px]">
              {reasoningBadge}
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
              onKeyDown={event => {
                nav.onSearchKeyDown(event, selectModelAndClose)
              }}
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
              ) : sections.length === 0 ? (
                <div className="text-muted-foreground px-3 py-3 text-sm">
                  No models match “{modelSearch.trim()}”.
                </div>
              ) : (
                sections.map(section => (
                  <div key={section.title || 'all'}>
                    {section.title ? (
                      <div className="text-muted-foreground px-3 pt-2 pb-1 text-[11px] font-medium tracking-wide uppercase">
                        {section.title}
                      </div>
                    ) : null}
                    {section.options.map(option => {
                      const optionKey = composerModelOptionKey(option)
                      return (
                        <div
                          key={optionKey}
                          onMouseEnter={() => nav.setActiveKey(optionKey)}
                        >
                          <ComposerModelPickerOption
                            option={option}
                            optionKey={optionKey}
                            modelOptions={modelOptions}
                            runtimeSettings={runtimeSettings}
                            favorite={favoriteSet.has(
                              composerModelPrefKey(option)
                            )}
                            active={nav.activeKey === optionKey}
                            effortMenuOpen={effortMenuOpen}
                            onEffortMenuOpenChange={setEffortMenuOpen}
                            onModelSelect={onModelSelect}
                            onReasoningSettingsChange={onReasoningSettingsChange}
                            onModelSearchClear={() => setModelSearch('')}
                            onClosePicker={() => {
                              closePicker()
                              focusComposerSoon()
                            }}
                            onToggleFavorite={
                              onToggleModelFavorite
                                ? async () => {
                                    const result =
                                      await onToggleModelFavorite(option)
                                    setPreferences(prev => ({
                                      ...prev,
                                      favorites: result.favorites
                                    }))
                                  }
                                : undefined
                            }
                          />
                        </div>
                      )
                    })}
                  </div>
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
                  closePicker()
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
