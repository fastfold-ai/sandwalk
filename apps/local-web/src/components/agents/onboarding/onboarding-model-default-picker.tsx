import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { Check, Loader } from 'lucide-react'
import { ComposerModelPicker } from '@/components/agents/composer/ComposerModelPicker'
import type { ComposerModelOption } from '@/lib/composer-models'

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
        <p className="text-sm font-medium">Choose a default model</p>
        <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">
          Only {providerName} models with a working API key are listed. This
          becomes the default for new chats — you can change it anytime.
        </p>
      </div>
      {loading ? (
        <p className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader className="size-4 animate-spin" />
          Loading models…
        </p>
      ) : modelOptions.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No enabled {providerName} models yet. You can pick one later in Models.
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-muted-foreground text-xs">Default</span>
          <ComposerModelPicker
            modelOptions={modelOptions}
            runtimeSettings={runtimeSettings}
            onModelSelect={onModelSelect}
          />
          {saving ? (
            <Loader className="text-muted-foreground size-3.5 animate-spin" />
          ) : saved ? (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
              <Check className="size-3.5" />
              Saved
            </span>
          ) : null}
        </div>
      )}
    </div>
  )
}
