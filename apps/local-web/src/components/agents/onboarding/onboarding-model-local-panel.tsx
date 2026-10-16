import { Check, Eye, EyeOff, Loader, RefreshCw } from 'lucide-react'

import {
  LlamaLibrary,
  type LlamaLibraryActions} from '@/components/agents/LlamaLibrary'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import {
  OnboardingBackendIcon,
  type OnboardingBackendValue,
  OnboardingChip,
  PROFILE_BACKENDS} from './onboarding-model-shared'

export function OnboardingModelLocalPanel({
  localBackend,
  localUrl,
  localKey,
  showLocalKey,
  localLabel,
  discoverBusy,
  discoveredModels,
  discoverSource,
  discoverError,
  selectedModel,
  localBusy,
  localSaved,
  selectedBackend,
  onPickBackend,
  onLocalLabelChange,
  onLocalUrlChange,
  onLocalKeyChange,
  onToggleShowKey,
  onDiscover,
  onSave,
  onSelectModel,
  onUseLlama,
  llamaRuntime
}: {
  localBackend: OnboardingBackendValue
  localUrl: string
  localKey: string
  showLocalKey: boolean
  localLabel: string
  discoverBusy: boolean
  discoveredModels: string[]
  discoverSource: string | null
  discoverError: string | null
  selectedModel: string | null
  localBusy: boolean
  localSaved: boolean
  selectedBackend: (typeof PROFILE_BACKENDS)[number]
  onPickBackend: (value: OnboardingBackendValue) => void
  onLocalLabelChange: (value: string) => void
  onLocalUrlChange: (value: string) => void
  onLocalKeyChange: (value: string) => void
  onToggleShowKey: () => void
  onDiscover: () => void
  onSave: () => void
  onSelectModel: (modelId: string) => void
  onUseLlama?: (modelId: string) => void
  llamaRuntime?: LlamaLibraryActions
}) {
  if (localBackend === 'llama' && llamaRuntime) {
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {PROFILE_BACKENDS.map(item => (
            <OnboardingChip
              key={item.value}
              selected={localBackend === item.value}
              onClick={() => onPickBackend(item.value)}
            >
              <OnboardingBackendIcon icon={item.icon} />
              {item.label}
            </OnboardingChip>
          ))}
        </div>
        <LlamaLibrary
          actions={llamaRuntime}
          selectedId={localSaved ? selectedModel : null}
          onUse={modelId => onUseLlama?.(modelId)}
        />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {PROFILE_BACKENDS.map(item => (
          <OnboardingChip
            key={item.value}
            selected={localBackend === item.value}
            onClick={() => onPickBackend(item.value)}
          >
            <OnboardingBackendIcon icon={item.icon} />
            {item.label}
          </OnboardingChip>
        ))}
      </div>

      <div className="space-y-2">
        <Input
          value={localLabel}
          onChange={event => onLocalLabelChange(event.target.value)}
          placeholder="Profile name"
        />
        <Input
          value={localUrl}
          onChange={event => onLocalUrlChange(event.target.value)}
          placeholder={selectedBackend.baseUrl}
          className="font-mono text-sm"
        />
        <div className="relative">
          <Input
            type={showLocalKey ? 'text' : 'password'}
            autoComplete="off"
            value={localKey}
            onChange={event => onLocalKeyChange(event.target.value)}
            placeholder={
              localBackend === 'ollama'
                ? 'API key (optional)'
                : 'API key (if required)'
            }
            className="pr-10"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="absolute top-1/2 right-1 size-7 -translate-y-1/2"
            onClick={onToggleShowKey}
            aria-label={showLocalKey ? 'Hide API key' : 'Show API key'}
          >
            {showLocalKey ? (
              <EyeOff className="size-4" />
            ) : (
              <Eye className="size-4" />
            )}
          </Button>
        </div>
        <p className="text-muted-foreground text-[11px]">
          Suggested for {selectedBackend.label}: {selectedBackend.baseUrl} ·
          discovers via {selectedBackend.hint}
        </p>
      </div>

      <div className="flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="ghost"
          disabled={discoverBusy}
          onClick={() => onDiscover()}
        >
          {discoverBusy ? (
            <Loader className="size-4 animate-spin" />
          ) : (
            <RefreshCw className="size-4" />
          )}
          Discover models
        </Button>
        <Button
          type="button"
          disabled={localBusy || !selectedModel}
          onClick={() => onSave()}
        >
          {localBusy ? (
            <Loader className="size-4 animate-spin" />
          ) : localSaved ? (
            <Check className="size-4" />
          ) : null}
          {localSaved ? 'Saved' : 'Save & use'}
        </Button>
      </div>

      {discoverError ? (
        <p className="text-destructive text-sm">{discoverError}</p>
      ) : null}

      {discoveredModels.length ? (
        <div className="space-y-2">
          <p className="text-muted-foreground text-xs">
            Pick one for your first chat
            {discoverSource ? ` (${discoverSource})` : ''}:
          </p>
          <div className="max-h-40 space-y-1 overflow-y-auto pr-1">
            {discoveredModels.map(modelId => {
              const selected = selectedModel === modelId
              return (
                <button
                  key={modelId}
                  type="button"
                  onClick={() => onSelectModel(modelId)}
                  className={cn(
                    'hover:bg-muted/50 flex w-full items-center rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                    selected
                      ? 'border-foreground bg-muted/40'
                      : 'border-border/60'
                  )}
                >
                  <span className="min-w-0 flex-1 truncate font-mono text-xs">
                    {modelId}
                  </span>
                  {selected ? <Check className="size-3.5 shrink-0" /> : null}
                </button>
              )
            })}
          </div>
        </div>
      ) : null}
    </div>
  )
}
