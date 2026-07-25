import type { ModelProfile } from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronDown,
  ChevronRight,
  Loader2,
  Plus
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { ProfileBackendIcon } from './models-view-shared'
import {
  PROFILE_BACKENDS,
  profileBackend
} from './models-view-utils'
import type { ProfileProbeStatus } from './use-models-view-profiles'

export function ModelsProfilesSection({
  open,
  localProfiles,
  probeStatusById,
  onOpenChange,
  onOpenCreate,
  onOpenEdit
}: {
  open: boolean
  localProfiles: ModelProfile[]
  probeStatusById: Record<string, ProfileProbeStatus>
  onOpenChange: (open: boolean) => void
  onOpenCreate: () => void
  onOpenEdit: (profile: ModelProfile) => void
}) {
  return (
    <section className="space-y-4">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => onOpenChange(!open)}
      >
        <div className="min-w-0 pr-3">
          <h3 className="text-base font-semibold">Local</h3>
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

          {localProfiles.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No local OpenAI-compatible endpoints yet.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {localProfiles.map(profile => {
                const backendMeta =
                  profileBackend(
                    profile.backend === 'openai' ? 'other' : profile.backend
                  ) || PROFILE_BACKENDS.find(item => item.value === 'other')!
                const probe = probeStatusById[profile.id]
                return (
                  <button
                    key={profile.id}
                    type="button"
                    onClick={() => onOpenEdit(profile)}
                    className="hover:bg-muted/40 flex h-16 items-center gap-3 rounded-xl border px-3 text-left transition-colors"
                  >
                    <span className="bg-muted/50 grid size-9 shrink-0 place-items-center rounded-lg">
                      <ProfileBackendIcon
                        icon={backendMeta.icon}
                        className="size-5 rounded-md"
                      />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        {profile.label}
                      </span>
                      {probe?.probing ? (
                        <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
                          <Loader2 className="size-3.5 animate-spin" />
                          Checking…
                        </span>
                      ) : probe?.tone === 'ok' ? (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                          <Check className="size-3.5 shrink-0" />
                          Connected
                        </span>
                      ) : probe ? (
                        <span
                          className={cn(
                            'block truncate text-xs font-medium',
                            probe.tone === 'warn' &&
                              'text-amber-600 dark:text-amber-400',
                            probe.tone === 'error' && 'text-destructive',
                            probe.tone !== 'warn' &&
                              probe.tone !== 'error' &&
                              'text-muted-foreground'
                          )}
                          title={probe.detail || undefined}
                        >
                          {probe.label}
                        </span>
                      ) : (
                        <span className="text-muted-foreground block text-xs">
                          Not checked
                        </span>
                      )}
                    </span>
                    <ChevronRight className="text-muted-foreground size-4 shrink-0" />
                  </button>
                )
              })}
            </div>
          )}
        </div>
      ) : null}
    </section>
  )
}
