import type { ModelProfile } from '@sandwalk/agent-ui-core'
import { Check, ChevronDown, Copy, Eye, EyeOff, Loader, RefreshCw, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import {
  LlamaLibrary,
  type LlamaLibraryActions} from '@/components/agents/LlamaLibrary'
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
import { copyText } from '@/lib/clipboard'
import { cn } from '@/lib/utils'

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
  testingProfile,
  testResult,
  discoveredModels,
  discoverSource,
  discoverError,
  showProfileApiKey,
  onOpenChange,
  onFormChange,
  onBackendChange,
  onDiscoverModels,
  onTestProfile,
  onSaveProfile,
  onRemoveProfile,
  onShowProfileApiKeyChange,
  onRevealStoredSecret,
  onResetDiscoverState,
  llamaRuntime,
  onUseLlamaModel
}: {
  open: boolean
  editing: ModelProfile | null
  form: ProfileFormState
  selectedBackend: (typeof PROFILE_BACKENDS)[number]
  savingProfile: boolean
  discovering: boolean
  testingProfile: boolean
  testResult: { ok: boolean; message: string } | null
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
  onTestProfile: () => void
  onSaveProfile: () => void
  onRemoveProfile?: (profile: ModelProfile) => void
  onShowProfileApiKeyChange: (value: boolean | ((open: boolean) => boolean)) => void
  /** Load the saved Local LLM API key into the draft for show/copy. */
  onRevealStoredSecret?: (profileId: string) => Promise<string>
  onResetDiscoverState: () => void
  llamaRuntime?: LlamaLibraryActions
  onUseLlamaModel?: (modelId: string) => void
}) {
  const [secretAction, setSecretAction] = useState<'reveal' | 'copy' | null>(
    null
  )
  const [copied, setCopied] = useState(false)
  const busy =
    savingProfile || discovering || testingProfile || secretAction !== null

  useEffect(() => {
    setSecretAction(null)
    setCopied(false)
  }, [editing?.id, open])

  const ensureStoredSecret = async (): Promise<string> => {
    const draft = form.apiKey.trim()
    if (draft) return draft
    if (!editing?.hasApiKey || !onRevealStoredSecret) return ''
    const value = (await onRevealStoredSecret(editing.id)).trim()
    if (value) {
      onFormChange(prev => ({ ...prev, apiKey: value }))
    }
    return value
  }

  const toggleReveal = async () => {
    if (showProfileApiKey) {
      onShowProfileApiKeyChange(false)
      return
    }
    if (editing?.hasApiKey && !form.apiKey.trim()) {
      if (!onRevealStoredSecret) {
        onShowProfileApiKeyChange(true)
        return
      }
      setSecretAction('reveal')
      try {
        await ensureStoredSecret()
        onShowProfileApiKeyChange(true)
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : 'Unable to reveal saved key'
        )
      } finally {
        setSecretAction(null)
      }
      return
    }
    onShowProfileApiKeyChange(true)
  }

  const copySecret = async () => {
    setSecretAction('copy')
    try {
      const value = await ensureStoredSecret()
      if (!value) {
        toast.error('No API key to copy')
        return
      }
      onShowProfileApiKeyChange(true)
      const ok = await copyText(value)
      if (ok) {
        setCopied(true)
        toast.success('API key copied')
        window.setTimeout(() => setCopied(false), 1500)
      } else {
        toast.error('Could not copy — select the key manually')
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Unable to copy saved key'
      )
    } finally {
      setSecretAction(null)
    }
  }

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

          {form.backend === 'llama' && llamaRuntime ? (
            <LlamaLibrary
              actions={llamaRuntime}
              selectedId={discoveredModels[0] || null}
              onUse={modelId => onUseLlamaModel?.(modelId)}
            />
          ) : null}

          {form.backend === 'llama' ? null : (
          <>
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
                className="pr-16 font-mono text-sm"
                autoComplete="off"
              />
              <div className="absolute top-1/2 right-1.5 flex -translate-y-1/2 items-center gap-0.5">
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground grid size-7 place-items-center rounded-md"
                  aria-label="Copy API key"
                  title="Copy API key"
                  disabled={busy}
                  onClick={() => void copySecret()}
                >
                  {secretAction === 'copy' ? (
                    <Loader className="size-4 animate-spin" />
                  ) : copied ? (
                    <Check className="size-4 text-emerald-600 dark:text-emerald-400" />
                  ) : (
                    <Copy className="size-4" />
                  )}
                </button>
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground grid size-7 place-items-center rounded-md"
                  aria-label={
                    showProfileApiKey ? 'Hide API key' : 'Show API key'
                  }
                  title={showProfileApiKey ? 'Hide API key' : 'Show API key'}
                  disabled={busy}
                  onClick={() => void toggleReveal()}
                >
                  {secretAction === 'reveal' ? (
                    <Loader className="size-4 animate-spin" />
                  ) : showProfileApiKey ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                </button>
              </div>
            </div>
          </div>
          </>
          )}
        </div>

        {form.backend === 'llama' ? null : (
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
                <Loader className="size-3.5 animate-spin" />
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
          {testResult ? (
            <p
              className={cn(
                'shrink-0 rounded-md px-3 py-2 text-sm',
                testResult.ok
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                  : 'bg-amber-500/15 text-amber-900 dark:text-amber-200'
              )}
            >
              {testResult.message}
            </p>
          ) : null}
        </div>
        )}

        <DialogFooter className="shrink-0 gap-2 sm:justify-between">
          <div className="flex flex-wrap gap-2">
            {editing && onRemoveProfile ? (
              <Button
                variant="ghost"
                className="text-destructive hover:text-destructive"
                disabled={busy}
                onClick={() => onRemoveProfile(editing)}
              >
                <Trash2 />
                Remove
              </Button>
            ) : null}
            <Button
              variant="ghost"
              disabled={busy || !form.baseUrl.trim()}
              onClick={onTestProfile}
            >
              {testingProfile ? <Loader className="animate-spin" /> : null}
              Test
            </Button>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button disabled={busy} onClick={onSaveProfile}>
              {savingProfile ? <Loader className="animate-spin" /> : null}
              Save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
