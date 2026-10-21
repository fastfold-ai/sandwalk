import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { Check, ChevronDown, ChevronRight, Plus } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

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
  formatContextWindow,
  formatLlamaModelLabel,
  formatReasoningEffortLabel,
  isComposerModelSelected,
  isLlamaWeightId,
  rankComposerModelOptions,
  resolveComposerModelOption
} from '@/lib/composer-models'
import { cn } from '@/lib/utils'

export function ComposerModelPicker({
  modelOptions,
  runtimeSettings,
  onModelSelect,
  onReasoningSettingsChange,
  onAddModels,
  onLoadModelPreferences,
  onToggleModelFavorite: _onToggleModelFavorite,
  onFocusComposer,
  triggerLabel,
  client
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
  client?: LocalAgentClient
}) {
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const [modelPickerOpen, setModelPickerOpen] = useState(false)
  const [sideOffset, setSideOffset] = useState(8)
  const [modelSearch, setModelSearch] = useState('')
  const [flyout, setFlyout] = useState<'model' | 'effort' | 'context' | null>(null)
  const [llamaContext, setLlamaContext] = useState(4096)
  const [llamaMemory, setLlamaMemory] = useState<Record<number, string>>({})
  const [llamaState, setLlamaState] = useState('unloaded')
  const pinnedContext = useRef<number | null>(null)
  const [preferences, setPreferences] = useState<ComposerModelPreferences>({
    favorites: [],
    recent: []
  })

  const unresolvedLlama =
    runtimeSettings?.model && isLlamaWeightId(runtimeSettings.model)
      ? runtimeSettings.model
      : null
  const selectedModel: ComposerModelOption =
    resolveComposerModelOption(modelOptions, runtimeSettings) ||
    (runtimeSettings
      ? {
          provider: unresolvedLlama ? 'local' : runtimeSettings.provider,
          model: runtimeSettings.model,
          label: unresolvedLlama
            ? formatLlamaModelLabel(unresolvedLlama)
            : runtimeSettings.model,
          speed: unresolvedLlama ? 'Llama' : '',
          source: unresolvedLlama ? 'profile' : undefined,
          backend: unresolvedLlama ? 'llama' : null,
          profileId: unresolvedLlama
            ? runtimeSettings.openaiProfileId || 'llama_local'
            : runtimeSettings.openaiProfileId,
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
  const selectedEffort = String(
    runtimeSettings?.reasoningEffort ?? selectedModel.reasoningEffort ?? 'medium'
  )
    .trim()
    .toLowerCase()
  const selectedFast = Boolean(
    runtimeSettings?.reasoningFast ?? selectedModel.reasoningFast
  )
  const contextLabel = formatContextWindow(selectedModel.contextWindow)?.replace(/k$/, 'K')
  const effortOptions =
    selectedModel.reasoningEffortOptions &&
    selectedModel.reasoningEffortOptions.length > 0
      ? selectedModel.reasoningEffortOptions
      : ['low', 'medium', 'high']

  const sections = useMemo(
    () => rankComposerModelOptions(modelOptions, modelSearch, preferences),
    [modelOptions, modelSearch, preferences]
  )

  const nav = useComposerModelPickerNav({
    open: modelPickerOpen,
    search: modelSearch,
    sections,
    selected: selectedModel,
    effortMenuOpen: flyout === 'effort'
  })

  useEffect(() => {
    pinnedContext.current = null
  }, [selectedModel.model])

  useEffect(() => {
    if (llamaState !== 'loading' || !client) return
    const timer = window.setInterval(() => {
      void client.llamaRuntimeCatalog().then(catalog => {
        const row = catalog.installed.find(item => item.id === selectedModel.model)
        if (row?.state && row.state !== 'loading') setLlamaState(row.state)
      }).catch(() => {})
    }, 2000)
    return () => window.clearInterval(timer)
  }, [client, llamaState, selectedModel.model])

  useEffect(() => {
    if (!client || selectedModel.backend !== 'llama') return
    let cancelled = false
    void client.llamaRuntimeMemory(selectedModel.model).then(result => {
      if (cancelled) return
      const next: Record<number, string> = {}
      for (const tier of result.tiers) next[tier.context] = tier.memory
      setLlamaMemory(next)
    }).catch(() => {})
    void client.llamaRuntimeCatalog().then(catalog => {
      if (cancelled) return
      const row = catalog.installed.find(item => item.id === selectedModel.model)
      if (row?.state) setLlamaState(row.state)
      if (pinnedContext.current == null && row?.context) setLlamaContext(row.context)
    }).catch(() => {})
    return () => {
      cancelled = true
    }
  }, [client, selectedModel.backend, selectedModel.model])

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
    setFlyout(null)
  }

  const focusComposerSoon = () => {
    window.requestAnimationFrame(() => {
      onFocusComposer?.()
    })
  }

  const selectModelAndClose = (option: ComposerModelOption) => {
    if (
      client &&
      (option.backend === 'llama' ||
        option.profileId === 'llama_local' ||
        isLlamaWeightId(option.model))
    ) {
      void client.llamaRuntimeEnsure()
    }
    void onModelSelect(option.provider, option.model, option.profileId)
    closePicker()
    focusComposerSoon()
  }

  return (
    <Popover
      open={modelPickerOpen}
      onOpenChange={open => {
        if (open) {
          const button = triggerRef.current
          const form = button?.closest('form')
          if (button && form) {
            const buttonBox = button.getBoundingClientRect()
            const formBox = form.getBoundingClientRect()
            setSideOffset(Math.max(8, buttonBox.top - formBox.top + 8))
          }
        }
        setModelPickerOpen(open)
        if (!open) {
          setModelSearch('')
          setFlyout(null)
        }
      }}
    >
      <PopoverTrigger asChild>
        <button
          ref={triggerRef}
          type="button"
          title={
            selectedModel.speed
              ? `${selectedModel.label} · ${selectedModel.speed}`
              : selectedModel.label
          }
          className="text-muted-foreground hover:text-foreground inline-flex shrink-0 items-center gap-1 rounded-md py-1 text-[13px]"
        >
          <span className="whitespace-nowrap">
            {triggerLabel || selectedModel.label}
          </span>
          <ChevronDown className="size-3.5 shrink-0 opacity-60" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        side="top"
        sideOffset={sideOffset}
        collisionPadding={12}
        className="z-[90] w-auto overflow-visible border-0 bg-transparent p-0 shadow-none"
        onCloseAutoFocus={event => event.preventDefault()}
      >
        <div className="relative">
          <div className="sandwalk-glass-menu border-border/60 bg-popover/90 w-60 rounded-2xl border p-1.5 text-[13px] shadow-lg backdrop-blur-xl">
            {supportsReasoningEffort &&
            selectedModel.supportsReasoningFast !== false &&
            onReasoningSettingsChange ? (
              <div
                className="flex items-center justify-between rounded-lg px-2.5 py-1.5"
                onMouseEnter={() => setFlyout(null)}
              >
                <span>Fast</span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={selectedFast}
                  aria-label="Fast"
                  className={cn(
                    'relative h-4 w-7 shrink-0 rounded-full transition-colors',
                    selectedFast ? 'bg-foreground' : 'bg-muted'
                  )}
                  onClick={() => {
                    void onReasoningSettingsChange({
                      provider: selectedModel.provider,
                      model: selectedModel.model,
                      reasoningFast: !selectedFast
                    })
                  }}
                >
                  <span
                    className={cn(
                      'bg-background absolute top-0.5 size-3 rounded-full transition-[left]',
                      selectedFast ? 'left-3.5' : 'left-0.5'
                    )}
                  />
                </button>
              </div>
            ) : null}
            {selectedModel.backend === 'llama' && client ? (
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left"
                onMouseEnter={() => setFlyout(null)}
                onClick={() => {
                  if (llamaState === 'loaded' || llamaState === 'ready') {
                    setLlamaState('unloaded')
                    void client.llamaRuntimeUnload(selectedModel.model)
                    return
                  }
                  if (llamaState === 'loading') return
                  setLlamaState('loading')
                  void client.llamaRuntimeLoad(selectedModel.model)
                }}
              >
                <span>{llamaState === 'loaded' || llamaState === 'ready' ? 'Eject' : 'Load'}</span>
                <span className="text-muted-foreground">
                  {llamaState === 'loading'
                    ? 'Loading…'
                    : llamaState === 'loaded' || llamaState === 'ready'
                      ? 'In memory'
                      : 'Unloaded'}
                </span>
              </button>
            ) : null}
            {selectedModel.backend === 'llama' && client ? (
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left"
                onMouseEnter={() => setFlyout('context')}
                onClick={() => setFlyout('context')}
              >
                <span>Context</span>
                <span className="text-muted-foreground flex items-center gap-1">
                  {llamaContext / 1024}k
                  <ChevronRight className="size-3.5 opacity-70" />
                </span>
              </button>
            ) : contextLabel ? (
              <div
                className="flex items-center justify-between rounded-lg px-2.5 py-1.5"
                onMouseEnter={() => setFlyout(null)}
              >
                <span>Context</span>
                <span className="text-muted-foreground flex items-center gap-1">
                  {contextLabel}
                </span>
              </div>
            ) : null}
            {supportsReasoningEffort && onReasoningSettingsChange ? (
              <button
                type="button"
                className={cn(
                  'hover:bg-muted flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left',
                  flyout === 'effort' && 'bg-muted'
                )}
                onMouseEnter={() => setFlyout('effort')}
                onClick={() => setFlyout('effort')}
              >
                <span>Effort</span>
                <span className="text-muted-foreground flex items-center gap-1">
                  {formatReasoningEffortLabel(selectedEffort)}
                  <ChevronRight className="size-3.5 opacity-70" />
                </span>
              </button>
            ) : null}
            {selectedModel.speed ? (
              <div
                className="flex items-center justify-between gap-3 rounded-lg px-2.5 py-1.5"
                onMouseEnter={() => setFlyout(null)}
              >
                <span>Provider</span>
                <span className="text-muted-foreground truncate">
                  {selectedModel.speed}
                </span>
              </div>
            ) : null}
            <button
              type="button"
              className={cn(
                'hover:bg-muted flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-1.5 text-left',
                flyout === 'model' && 'bg-muted'
              )}
              onMouseEnter={() => setFlyout('model')}
              onClick={() => setFlyout('model')}
            >
              <span>Model</span>
              <span className="text-muted-foreground flex min-w-0 items-center gap-1">
                <span className="truncate">
                  {triggerLabel || selectedModel.label}
                </span>
                <ChevronRight className="size-3.5 shrink-0 opacity-70" />
              </span>
            </button>
          </div>
          {flyout === 'context' && selectedModel.backend === 'llama' && client ? (
            <div className="sandwalk-glass-menu border-border/60 bg-popover/90 absolute top-14 left-full z-10 ml-2 w-44 rounded-2xl border p-1.5 shadow-lg backdrop-blur-xl">
              {[4096, 8192, 16384, 32768, 65536, 131072].map(tier => (
                <button
                  key={tier}
                  type="button"
                  className="hover:bg-muted flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-[13px]"
                  onPointerDown={event => {
                    event.preventDefault()
                    event.stopPropagation()
                    pinnedContext.current = tier
                    setLlamaContext(tier)
                    void client.llamaRuntimeSetContext(selectedModel.model, tier).catch(() => {
                      pinnedContext.current = null
                    })
                  }}
                >
                  <span>{tier / 1024}k</span>
                  <span className="text-muted-foreground inline-flex items-center gap-1.5">
                    {llamaMemory[tier] || '…'}
                    {llamaContext === tier ? <Check className="size-3.5 text-foreground" /> : null}
                  </span>
                </button>
              ))}
            </div>
          ) : null}
          {flyout === 'effort' && supportsReasoningEffort ? (
            <div className="sandwalk-glass-menu border-border/60 bg-popover/90 absolute top-14 left-full z-10 ml-2 w-40 rounded-2xl border p-1.5 shadow-lg backdrop-blur-xl">
              {effortOptions.map(level => {
                const active = selectedEffort === level
                return (
                  <button
                    key={level}
                    type="button"
                    className="hover:bg-muted flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-[13px]"
                    onClick={() => {
                      void onReasoningSettingsChange?.({
                        provider: selectedModel.provider,
                        model: selectedModel.model,
                        reasoningEffort: level
                      })
                    }}
                  >
                    <span>{formatReasoningEffortLabel(level)}</span>
                    {active ? <Check className="size-3.5" /> : null}
                  </button>
                )
              })}
            </div>
          ) : null}
          {flyout === 'model' ? (
            <div className="sandwalk-glass-menu border-border/60 bg-popover/90 absolute top-0 left-full z-10 ml-2 flex w-72 flex-col overflow-hidden rounded-2xl border shadow-lg backdrop-blur-xl">
              <div className="border-b px-3 py-1.5">
                <Input
                  value={modelSearch}
                  onChange={event => setModelSearch(event.target.value)}
                  onKeyDown={event => {
                    nav.onSearchKeyDown(event, selectModelAndClose)
                  }}
                  placeholder="Search models"
                  className="h-7 border-0 bg-transparent px-0 text-[13px] shadow-none focus-visible:ring-0"
                  autoFocus
                />
              </div>
              <ScrollArea className="h-52">
                <div className="py-1">
                  {modelOptions.length === 0 ? (
                    <div className="text-muted-foreground px-3 py-3 text-[13px]">
                      No enabled models.
                    </div>
                  ) : sections.length === 0 ? (
                    <div className="text-muted-foreground px-3 py-3 text-[13px]">
                      No models match “{modelSearch.trim()}”.
                    </div>
                  ) : (
                    sections.map(section => (
                      <div key={section.title || 'all'}>
                        {section.title ? (
                          <div className="text-muted-foreground px-3 pt-2 pb-1 text-xs">
                            {section.title}
                          </div>
                        ) : null}
                        {section.options.map(option => {
                          const optionKey = composerModelOptionKey(option)
                          const selected = isComposerModelSelected(
                            option,
                            runtimeSettings,
                            modelOptions
                          )
                          return (
                            <button
                              key={optionKey}
                              type="button"
                              data-composer-model-option={optionKey}
                              className={cn(
                                'hover:bg-muted mx-1 flex w-[calc(100%-0.5rem)] items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-[13px]',
                                nav.activeKey === optionKey && 'bg-muted'
                              )}
                              onMouseEnter={() => nav.setActiveKey(optionKey)}
                              onClick={() => selectModelAndClose(option)}
                            >
                              <span className="min-w-0 truncate">
                                {option.label}
                              </span>
                              <span className="flex shrink-0 items-center gap-1.5">
                                {option.speed ? (
                                  <span className="text-muted-foreground text-xs">
                                    {option.speed}
                                  </span>
                                ) : null}
                                {selected ? (
                                  <Check className="size-3.5 shrink-0" />
                                ) : null}
                              </span>
                            </button>
                          )
                        })}
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
              {onAddModels ? (
                <button
                  type="button"
                  className="hover:bg-muted flex items-center gap-2 border-t px-3 py-2 text-left text-[13px]"
                  onClick={() => {
                    closePicker()
                    onAddModels()
                  }}
                >
                  <Plus className="size-3.5 shrink-0" />
                  Add models
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      </PopoverContent>
    </Popover>
  )
}
