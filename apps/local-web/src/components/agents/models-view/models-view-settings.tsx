import type { AgentModel, IntegrationSummary, ModelProfile } from '@sandwalk/agent-ui-core'
import { ChevronDown, Eye, EyeOff, Loader2, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import { ModelToggle, ProfileBackendIcon } from './models-view-shared'
import {
  LLM_API_KEY_COPY,
  LLM_API_KEY_ORDER,
  primaryMaskedPreview,
  PROFILE_BACKENDS,
  profileBackend} from './models-view-utils'

export function ModelsApiKeysSection({
  open,
  providerIntegrations,
  keyDrafts,
  savingKeys,
  revealedKeys,
  onOpenChange,
  onKeyDraftChange,
  onRevealedKeyChange,
  onSaveProviderKey,
  onClearProviderKey
}: {
  open: boolean
  providerIntegrations: IntegrationSummary[]
  keyDrafts: Record<string, string>
  savingKeys: Record<string, boolean>
  revealedKeys: Record<string, boolean>
  onOpenChange: (open: boolean) => void
  onKeyDraftChange: (key: string, value: string) => void
  onRevealedKeyChange: (key: string, revealed: boolean) => void
  onSaveProviderKey: (integration: IntegrationSummary) => void
  onClearProviderKey: (integration: IntegrationSummary) => void
}) {
  return (
    <section className="space-y-4">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => onOpenChange(!open)}
      >
        <h3 className="text-base font-semibold">API Keys</h3>
        <ChevronDown
          className={cn(
            'text-muted-foreground size-4 transition-transform',
            open && 'rotate-180'
          )}
        />
      </button>

      {open ? (
        <div className="space-y-10">
          {providerIntegrations.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No LLM provider integrations available from the agent backend.
            </p>
          ) : null}
          {providerIntegrations.map(integration => {
            const copy =
              LLM_API_KEY_COPY[
                integration.key as (typeof LLM_API_KEY_ORDER)[number]
              ]
            const draft = keyDrafts[integration.key] || ''
            const saving = Boolean(savingKeys[integration.key])
            return (
              <div key={integration.key} className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <div className="text-sm font-medium text-zinc-700 dark:text-zinc-200">
                      {copy?.title || `${integration.name} API Key`}
                    </div>
                    <p className="text-muted-foreground text-sm leading-relaxed">
                      {copy ? (
                        <>
                          {copy.beforeLink}
                          {integration.setupUrl ? (
                            <a
                              href={integration.setupUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="text-foreground underline underline-offset-2"
                            >
                              {copy.linkLabel}
                            </a>
                          ) : (
                            copy.linkLabel
                          )}
                          {copy.afterLink}
                        </>
                      ) : (
                        <>
                          {integration.description}{' '}
                          {integration.setupUrl ? (
                            <a
                              href={integration.setupUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="text-foreground underline underline-offset-2"
                            >
                              Get API key
                            </a>
                          ) : null}
                        </>
                      )}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 pt-0.5">
                    <span className="text-muted-foreground text-xs">
                      {integration.configured ? 'Secret saved' : 'Not set'}
                    </span>
                    <ModelToggle
                      enabled={integration.configured}
                      pending={saving}
                      label={
                        integration.configured
                          ? `Clear ${integration.name} API key`
                          : `${integration.name} API key not set`
                      }
                      onToggle={() => {
                        if (integration.configured) {
                          onClearProviderKey(integration)
                        }
                      }}
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <div className="relative flex-1">
                    <Input
                      type={revealedKeys[integration.key] ? 'text' : 'password'}
                      value={draft}
                      autoComplete="off"
                      onChange={event =>
                        onKeyDraftChange(integration.key, event.target.value)
                      }
                      placeholder={
                        integration.configured
                          ? primaryMaskedPreview(integration) ||
                            'Secret saved. Enter a new key to replace it.'
                          : copy?.placeholderUnset ||
                            `Enter your ${integration.name} API Key`
                      }
                      className="bg-muted/40 pr-9 font-mono text-sm"
                      onKeyDown={event => {
                        if (event.key === 'Enter') {
                          event.preventDefault()
                          onSaveProviderKey(integration)
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground absolute right-2 top-1/2 -translate-y-1/2"
                      aria-label={
                        revealedKeys[integration.key]
                          ? 'Hide API key'
                          : 'Show API key'
                      }
                      onClick={() =>
                        onRevealedKeyChange(
                          integration.key,
                          !revealedKeys[integration.key]
                        )
                      }
                    >
                      {revealedKeys[integration.key] ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </button>
                  </div>
                  <Button
                    variant="outline"
                    className="sm:w-auto"
                    disabled={saving || !draft.trim()}
                    onClick={() => onSaveProviderKey(integration)}
                  >
                    {saving ? <Loader2 className="animate-spin" /> : null}
                    Save
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      ) : null}
    </section>
  )
}

export function ModelsCustomSection({
  open,
  customModels,
  onOpenChange,
  onOpenCustomCreate,
  onRemoveCustomModel
}: {
  open: boolean
  customModels: AgentModel[]
  onOpenChange: (open: boolean) => void
  onOpenCustomCreate: () => void
  onRemoveCustomModel: (model: AgentModel) => void
}) {
  return (
    <section className="space-y-3 border-t pt-6">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => onOpenChange(!open)}
      >
        <div className="min-w-0 pr-3">
          <h3 className="text-base font-semibold">Custom cloud models</h3>
          <p className="text-muted-foreground mt-1 text-sm">
            Add a provider model by name (for example an OpenAI deployment id)
            so it appears in the list above.
          </p>
        </div>
        <ChevronDown
          className={cn(
            'text-muted-foreground size-4 shrink-0 transition-transform',
            open && 'rotate-180'
          )}
        />
      </button>

      {open ? (
        <div className="space-y-3">
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground"
            onClick={onOpenCustomCreate}
          >
            <Plus />
            Add Custom Model
          </Button>

          <div className="divide-y rounded-xl border">
            {customModels.length === 0 ? (
              <div className="text-muted-foreground px-4 py-6 text-sm">
                No custom cloud models yet.
              </div>
            ) : (
              customModels.map(model => (
                <div
                  key={model.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">
                      {model.label}
                    </div>
                    <div className="text-muted-foreground truncate font-mono text-xs">
                      {model.provider} · {model.id}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8"
                    onClick={() => onRemoveCustomModel(model)}
                    aria-label={`Remove ${model.label}`}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </section>
  )
}

export function ModelsProfilesSection({
  open,
  localProfiles,
  onOpenChange,
  onOpenCreate,
  onProbeProfile,
  onOpenEdit,
  onRemoveProfile
}: {
  open: boolean
  localProfiles: ModelProfile[]
  onOpenChange: (open: boolean) => void
  onOpenCreate: () => void
  onProbeProfile: (profile: ModelProfile) => void
  onOpenEdit: (profile: ModelProfile) => void
  onRemoveProfile: (profile: ModelProfile) => void
}) {
  return (
    <section className="space-y-3 border-t pt-6">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => onOpenChange(!open)}
      >
        <div className="min-w-0 pr-3">
          <h3 className="text-base font-semibold">Local LLM</h3>
          <p className="text-muted-foreground mt-1 text-sm">
            Discovered models from these endpoints appear in the model list
            above.
          </p>
        </div>
        <ChevronDown
          className={cn(
            'text-muted-foreground size-4 shrink-0 transition-transform',
            open && 'rotate-180'
          )}
        />
      </button>

      {open ? (
        <div className="space-y-3">
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground"
            onClick={onOpenCreate}
          >
            <Plus />
            Add Local LLM
          </Button>

          <div className="divide-y rounded-xl border">
            {localProfiles.length === 0 ? (
              <div className="text-muted-foreground px-4 py-6 text-sm">
                No local OpenAI-compatible endpoints yet.
              </div>
            ) : (
              localProfiles.map(profile => {
                const backendMeta =
                  profileBackend(
                    profile.backend === 'openai' ? 'other' : profile.backend
                  ) || PROFILE_BACKENDS.find(item => item.value === 'other')!
                return (
                  <div
                    key={profile.id}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="flex min-w-0 items-start gap-3">
                      <ProfileBackendIcon
                        icon={backendMeta.icon}
                        className="mt-0.5 size-5 rounded-md"
                      />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">
                          {profile.label}
                          {profile.isActive ? (
                            <span className="text-muted-foreground ml-2 text-xs">
                              active
                            </span>
                          ) : null}
                        </div>
                        <div className="text-muted-foreground truncate font-mono text-xs">
                          {profile.backend}
                          {profile.baseUrl ? ` · ${profile.baseUrl}` : ''}
                        </div>
                        <div className="text-muted-foreground text-xs">
                          {profile.hasApiKey
                            ? `Key ${profile.apiKeyPreview || '••••'}`
                            : 'No API key'}
                          {profile.defaultModel
                            ? ` · default ${profile.defaultModel}`
                            : ''}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => onProbeProfile(profile)}
                        aria-label={`Probe ${profile.label}`}
                      >
                        <RefreshCw className="size-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => onOpenEdit(profile)}
                        aria-label={`Edit ${profile.label}`}
                      >
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => onRemoveProfile(profile)}
                        aria-label={`Delete ${profile.label}`}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      ) : null}
    </section>
  )
}
