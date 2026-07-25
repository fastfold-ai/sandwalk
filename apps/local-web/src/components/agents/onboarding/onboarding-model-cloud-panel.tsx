import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { Check, Eye, EyeOff, Loader2 } from 'lucide-react'

import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import {
  LLM_API_KEY_COPY,
  LLM_API_KEY_ORDER
} from '@/components/agents/models-view/models-view-utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { openInSystemBrowser } from '@/lib/desktop'
import { cn } from '@/lib/utils'

import { primaryMaskedPreview } from './onboarding-model-shared'

function hostLabelFor(integration: IntegrationSummary) {
  const copy =
    LLM_API_KEY_COPY[integration.key as (typeof LLM_API_KEY_ORDER)[number]]
  if (copy?.hostLabel) return copy.hostLabel
  if (!integration.setupUrl) return 'provider site'
  try {
    return new URL(integration.setupUrl).hostname
  } catch {
    return 'provider site'
  }
}

export function OnboardingModelCloudPanel({
  loadingIntegrations,
  cloudProviders,
  selectedCloud,
  selectedIntegration,
  cloudKey,
  showCloudKey,
  cloudBusy,
  cloudSaved,
  onSelectProvider,
  onCloudKeyChange,
  onToggleShowKey,
  onSave
}: {
  loadingIntegrations: boolean
  cloudProviders: IntegrationSummary[]
  selectedCloud: string | null
  selectedIntegration: IntegrationSummary | undefined
  cloudKey: string
  showCloudKey: boolean
  cloudBusy: boolean
  cloudSaved: boolean
  onSelectProvider: (key: string) => void
  onCloudKeyChange: (value: string) => void
  onToggleShowKey: () => void
  onSave: () => void
}) {
  return (
    <div className="space-y-3">
      {loadingIntegrations ? (
        <p className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading providers…
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {cloudProviders.map(item => {
            const selected = selectedCloud === item.key
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => onSelectProvider(item.key)}
                className={cn(
                  'hover:bg-muted/50 flex items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-colors',
                  selected
                    ? 'border-foreground bg-muted/40'
                    : 'border-border/70'
                )}
              >
                <IntegrationIcon integration={item} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">
                    {item.name}
                  </span>
                  <span className="text-muted-foreground block text-[11px]">
                    {item.configured ? 'Connected' : 'Add key'}
                  </span>
                </span>
                {item.configured ? (
                  <Check className="text-foreground size-3.5 shrink-0" />
                ) : null}
              </button>
            )
          })}
        </div>
      )}

      {selectedIntegration ? (
        <div className="space-y-2 pt-1">
          <div className="relative">
            <Input
              type={showCloudKey ? 'text' : 'password'}
              autoComplete="off"
              placeholder={
                selectedIntegration.configured
                  ? primaryMaskedPreview(selectedIntegration) ||
                    'Secret saved. Enter a new key to replace it.'
                  : `Paste ${selectedIntegration.name} API key`
              }
              value={cloudKey}
              onChange={event => onCloudKeyChange(event.target.value)}
              className="pr-10 font-mono text-sm"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute top-1/2 right-1 size-7 -translate-y-1/2"
              onClick={onToggleShowKey}
              aria-label={showCloudKey ? 'Hide API key' : 'Show API key'}
            >
              {showCloudKey ? (
                <EyeOff className="size-4" />
              ) : (
                <Eye className="size-4" />
              )}
            </Button>
          </div>
          {selectedIntegration.configured &&
          primaryMaskedPreview(selectedIntegration) &&
          !cloudKey.trim() ? (
            <p className="text-muted-foreground font-mono text-[11px]">
              Saved key {primaryMaskedPreview(selectedIntegration)}
            </p>
          ) : null}
          <div className="flex items-center justify-between gap-3">
            {selectedIntegration.setupUrl ? (
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground text-xs underline underline-offset-2"
                onClick={() =>
                  void openInSystemBrowser(selectedIntegration.setupUrl!)
                }
              >
                No key yet? Create one at {hostLabelFor(selectedIntegration)} ↗
              </button>
            ) : (
              <span />
            )}
            <Button
              type="button"
              disabled={cloudBusy || !cloudKey.trim()}
              onClick={() => onSave()}
            >
              {cloudBusy ? (
                <Loader2 className="size-4 animate-spin" />
              ) : cloudSaved ? (
                <Check className="size-4" />
              ) : null}
              {cloudSaved ? 'Saved' : 'Save & use'}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
