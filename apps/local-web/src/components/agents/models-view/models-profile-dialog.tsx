import type { ModelProfile } from '@sandwalk/agent-ui-core'
import { Check, ChevronDown, Eye, EyeOff, Loader2, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'

import { ProfileBackendIcon } from './models-view-shared'
import {
  formatDiscoveredModelLabel,
  PROFILE_BACKENDS,
  type ProfileBackendValue,
  type ProfileFormState
} from './models-view-utils'

export function ModelsProfileDialog({
  open,
  editing,
  form,
  selectedBackend,
  savingProfile,
  discovering,
  discoveredModels,
  discoverSource,
  discoverError,
  showProfileApiKey,
  onOpenChange,
  onFormChange,
  onBackendChange,
  onDiscoverModels,
  onSaveProfile,
  onShowProfileApiKeyChange,
  onResetDiscoverState
}: {
  open: boolean
  editing: ModelProfile | null
  form: ProfileFormState
  selectedBackend: (typeof PROFILE_BACKENDS)[number]
  savingProfile: boolean
  discovering: boolean
  discoveredModels: string[]
  discoverSource: string | null
  discoverError: string | null
  showProfileApiKey: boolean
  onOpenChange: (open: boolean) => void
  onFormChange: (
    value: ProfileFormState | ((prev: ProfileFormState) => ProfileFormState)
  ) => void
  onBackendChange: (backend: ProfileBackendValue) => void
  onDiscoverModels: () => void
  onSaveProfile: () => void
  onShowProfileApiKeyChange: (value: boolean | ((open: boolean) => boolean)) => void
  onResetDiscoverState: () => void
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={nextOpen => {
        onOpenChange(nextOpen)
        if (!nextOpen) onResetDiscoverState()
      }}
    >
      <DialogContent className="flex max-h-[min(90dvh,42rem)] flex-col gap-4 overflow-hidden sm:max-w-lg">
        <DialogHeader className="shrink-0">
          <DialogTitle>
            {editing ? 'Edit Local LLM' : 'Add Local LLM'}
          </DialogTitle>
        </DialogHeader>
        <div className="grid shrink-0 gap-3">
          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground text-xs">Label</span>
            <Input
              value={form.label}
              onChange={event =>
                onFormChange(prev => ({ ...prev, label: event.target.value }))
              }
              placeholder={selectedBackend.defaultLabel}
            />
          </label>

          <div className="space-y-1.5 text-sm">
            <span className="text-muted-foreground text-xs">Backend</span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 w-full justify-between px-3 font-normal"
                >
                  <span className="flex min-w-0 items-center gap-2 truncate">
                    <ProfileBackendIcon icon={selectedBackend.icon} />
                    <span className="flex min-w-0 items-baseline gap-1.5 truncate">
                      <span className="truncate">{selectedBackend.label}</span>
                      <span className="text-muted-foreground shrink-0 text-[11px]">
                        · {selectedBackend.hint}
                      </span>
                    </span>
                  </span>
                  <ChevronDown className="text-muted-foreground size-4 shrink-0" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-72"
              >
                <DropdownMenuLabel className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                  Endpoint type
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {PROFILE_BACKENDS.map(option => {
                  const selected = option.value === form.backend
                  return (
                    <DropdownMenuItem
                      key={option.value}
                      className="gap-2"
                      onSelect={() => onBackendChange(option.value)}
                    >
                      <ProfileBackendIcon icon={option.icon} />
                      <span className="flex min-w-0 flex-1 items-baseline gap-1.5 truncate">
                        <span className="truncate text-sm">{option.label}</span>
                        <span className="text-muted-foreground truncate text-[11px]">
                          · {option.hint}
                        </span>
                      </span>
                      {selected ? (
                        <Check className="ml-auto size-4 shrink-0" />
                      ) : null}
                    </DropdownMenuItem>
                  )
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground text-xs">Base URL</span>
            <Input
              value={form.baseUrl}
              onChange={event => {
                onFormChange(prev => ({ ...prev, baseUrl: event.target.value }))
                onResetDiscoverState()
              }}
              placeholder={selectedBackend.baseUrl}
              className="font-mono text-sm"
            />
            <span className="text-muted-foreground block text-[11px]">
              Suggested for {selectedBackend.label}: {selectedBackend.baseUrl}
            </span>
          </label>

          <div className="space-y-1.5 text-sm">
            <span className="text-muted-foreground text-xs">
              API key {editing?.hasApiKey ? '(leave blank to keep)' : ''}
            </span>
            <div className="relative">
              <Input
                type={showProfileApiKey ? 'text' : 'password'}
                value={form.apiKey}
                onChange={event =>
                  onFormChange(prev => ({ ...prev, apiKey: event.target.value }))
                }
                placeholder={
                  editing?.hasApiKey
                    ? editing.apiKeyPreview ||
                      'Secret saved. Enter a new key to replace it.'
                    : selectedBackend.value === 'ollama'
                      ? 'Optional (Ollama usually needs none)'
                      : 'Optional'
                }
                className="pr-10 font-mono text-sm"
                autoComplete="off"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute top-1/2 right-1 size-7 -translate-y-1/2"
                onClick={() => onShowProfileApiKeyChange(open => !open)}
                aria-label={showProfileApiKey ? 'Hide API key' : 'Show API key'}
              >
                {showProfileApiKey ? (
                  <EyeOff className="size-4" />
                ) : (
                  <Eye className="size-4" />
                )}
              </Button>
            </div>
          </div>
        </div>

        <div className="flex min-h-0 min-w-0 flex-col gap-1.5">
          <div className="flex shrink-0 items-center justify-between gap-2">
            <span className="text-muted-foreground text-xs">Models</span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              disabled={discovering || !form.baseUrl.trim()}
              onClick={onDiscoverModels}
            >
              {discovering ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <RefreshCw className="size-3.5" />
              )}
              Discover models
            </Button>
          </div>

          {discoveredModels.length > 0 ? (
            <ScrollArea className="h-52 w-full min-w-0 rounded-xl border">
              <div className="divide-y pr-2">
                {discoveredModels.map(modelId => (
                  <div
                    key={modelId}
                    className="flex min-w-0 items-center justify-between gap-3 px-4 py-3"
                    title={modelId}
                  >
                    <div className="min-w-0 flex-1 overflow-hidden">
                      <div className="truncate text-sm font-medium">
                        {formatDiscoveredModelLabel(modelId)}
                      </div>
                      <div className="text-muted-foreground truncate text-xs">
                        local · {selectedBackend.label.toLowerCase()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          ) : (
            <p className="text-muted-foreground text-[11px]">
              Discover to preview models from this endpoint. After Save, they
              appear as selectable entries in the model list.
            </p>
          )}
          {discoverSource && discoveredModels.length > 0 ? (
            <span className="text-muted-foreground block shrink-0 text-[11px]">
              Found {discoveredModels.length} via {discoverSource}. After Save,
              all of them appear in the model list.
            </span>
          ) : null}
          {discoverError ? (
            <span className="text-destructive block shrink-0 text-[11px]">
              {discoverError}
            </span>
          ) : null}
        </div>

        <DialogFooter className="shrink-0">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={savingProfile} onClick={onSaveProfile}>
            {savingProfile ? <Loader2 className="animate-spin" /> : null}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
