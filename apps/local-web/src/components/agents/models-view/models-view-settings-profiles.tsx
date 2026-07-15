import type { ModelProfile } from '@sandwalk/agent-ui-core'
import { ChevronDown, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { ProfileBackendIcon } from './models-view-shared'
import {
  PROFILE_BACKENDS,
  profileBackend
} from './models-view-utils'

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
