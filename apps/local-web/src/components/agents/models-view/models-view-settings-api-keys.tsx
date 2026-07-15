import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { ChevronDown, Eye, EyeOff, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import { ModelToggle } from './models-view-shared'
import {
  LLM_API_KEY_COPY,
  LLM_API_KEY_ORDER,
  primaryMaskedPreview
} from './models-view-utils'

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
