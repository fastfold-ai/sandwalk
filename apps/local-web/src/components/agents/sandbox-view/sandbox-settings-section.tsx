import { Check, Loader, RotateCcw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import {
  DEFAULT_CPU_IMAGE,
  DEFAULT_GPU_IMAGE,
  DEFAULT_MODAL_APP,
  DEFAULT_PIP,
  type ImageDraft
} from './sandbox-view-utils'

export function SandboxSettingsSection({
  draft,
  formDisabled,
  atDefaults,
  dirty,
  busy,
  overlayMessage,
  onDraftChange,
  onRestoreDefaults,
  onApply
}: {
  draft: ImageDraft
  formDisabled: boolean
  atDefaults: boolean
  dirty: boolean
  busy: boolean
  overlayMessage: string | null
  onDraftChange: (updater: (current: ImageDraft) => ImageDraft) => void
  onRestoreDefaults: () => void
  onApply: () => void
}) {
  return (
    <section className="space-y-4">
      <h3 className="text-base font-semibold">Sandbox settings</h3>

      <label className="space-y-1.5 text-sm">
        <span className="text-muted-foreground text-xs">App name</span>
        <Input
          value={draft.modalApp}
          disabled={formDisabled}
          placeholder={DEFAULT_MODAL_APP}
          onChange={event =>
            onDraftChange(current => ({
              ...current,
              modalApp: event.target.value
            }))
          }
        />
      </label>

      <label className="space-y-1.5 text-sm">
        <span className="text-muted-foreground text-xs">Idle TTL (seconds)</span>
        <Input
          type="number"
          min={60}
          max={86400}
          step={60}
          value={draft.idleTtlSeconds}
          disabled={formDisabled}
          onChange={event =>
            onDraftChange(current => ({
              ...current,
              idleTtlSeconds: event.target.value
            }))
          }
        />
      </label>

      <label className="space-y-1.5 text-sm">
        <span className="text-muted-foreground text-xs">CPU base image</span>
        <Input
          value={draft.cpuImage}
          disabled={formDisabled}
          placeholder={DEFAULT_CPU_IMAGE}
          className="font-mono text-xs"
          onChange={event =>
            onDraftChange(current => ({
              ...current,
              cpuImage: event.target.value
            }))
          }
        />
      </label>

      <label className="space-y-1.5 text-sm">
        <span className="text-muted-foreground text-xs">GPU base image</span>
        <Input
          value={draft.gpuImage}
          disabled={formDisabled}
          placeholder={DEFAULT_GPU_IMAGE}
          className="font-mono text-xs"
          onChange={event =>
            onDraftChange(current => ({
              ...current,
              gpuImage: event.target.value
            }))
          }
        />
      </label>

      <label className="space-y-1.5 text-sm">
        <span className="text-muted-foreground text-xs">Default pip installs</span>
        <Input
          value={draft.pipPackages}
          disabled={formDisabled}
          placeholder={DEFAULT_PIP}
          className="text-xs"
          onChange={event =>
            onDraftChange(current => ({
              ...current,
              pipPackages: event.target.value
            }))
          }
        />
      </label>

      <div className="flex flex-wrap items-center justify-end gap-2 pt-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={formDisabled || atDefaults}
          onClick={onRestoreDefaults}
        >
          <RotateCcw className="size-3.5" />
          Restore to defaults
        </Button>
        <Button
          size="sm"
          disabled={formDisabled || !dirty}
          onClick={() => onApply()}
        >
          {busy && overlayMessage?.startsWith('Saving') ? (
            <Loader className="animate-spin" />
          ) : (
            <Check />
          )}
          Save settings
        </Button>
      </div>
    </section>
  )
}
