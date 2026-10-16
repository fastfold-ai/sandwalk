import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { Check, Loader } from 'lucide-react'

import type { ComposerModelOption } from '@/lib/composer-models'
import { cn } from '@/lib/utils'

export function OnboardingModelDefaultPicker({
  providerName,
  modelOptions,
  runtimeSettings,
  loading,
  saving,
  saved,
  onModelSelect
}: {
  providerName: string
  modelOptions: ComposerModelOption[]
  runtimeSettings: RuntimeSettings | null
  loading: boolean
  saving: boolean
  saved: boolean
  onModelSelect: (
    provider: string,
    model: string,
    profileId?: string | null
  ) => Promise<void>
}) {
  return (
    <div className="border-border/70 space-y-3 rounded-xl border p-3">
      <div>
        <p className="text-sm font-medium">Choose a model for your first chat</p>
        <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">
          These are the {providerName} models that are configured and healthy.
          The one you pick starts your first chat.
        </p>
      </div>
      {loading ? (
        <p className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader className="size-4 animate-spin" />
          Loading models…
        </p>
      ) : modelOptions.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No healthy {providerName} models yet. Check the key, then try again.
        </p>
      ) : (
        <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
          {modelOptions.map(option => {
            const selected =
              saved &&
              runtimeSettings?.model === option.model &&
              runtimeSettings.provider === option.provider
            return (
              <button
                key={`${option.provider}:${option.model}`}
                type="button"
                disabled={saving}
                onClick={() =>
                  void onModelSelect(option.provider, option.model, option.profileId)
                }
                className={cn(
                  'hover:bg-muted/50 flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                  selected
                    ? 'border-foreground bg-muted/40'
                    : 'border-border/60'
                )}
              >
                <span className="min-w-0 flex-1 truncate">{option.label}</span>
                {selected ? (
                  <Check className="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                ) : null}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
