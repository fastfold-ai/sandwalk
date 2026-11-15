import type {
  ServerSystemInfo,
  SessionSandboxStatus
} from '@sandwalk/agent-ui-core'
import { Container, Loader } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { ComposerSandboxPopoverContent } from '@/components/agents/composer/ComposerSandboxPopoverContent'
import { ModalGlyph } from '@/components/agents/composer/ModalGlyph'
import {
  draftFromSandboxStatus,
  type SandboxActionPhase,
  type SandboxComputeChange,
  sandboxDraftChangesSettings,
  sandboxStatusDotClass,
  sandboxStatusLabel
} from '@/components/agents/composer/sandbox-utils'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'

export function ComposerSandboxPicker({
  sandboxStatus = null,
  sandboxPhase = 'idle',
  embedded = false,
  variant = 'chooser',
  onRequestClose,
  onSandboxBackendSelect,
  onSandboxComputeChange,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart,
  onLoadLocalSystem,
  onRefreshSandbox
}: {
  sandboxStatus?: SessionSandboxStatus | null
  sandboxPhase?: SandboxActionPhase
  /** Render only the panel, for a parent menu flyout. */
  embedded?: boolean
  /** `edit`: settings of an existing Modal sandbox, without the on/off switch. */
  variant?: 'chooser' | 'edit'
  onRequestClose?: () => void
  onSandboxBackendSelect: (
    backend: 'builtin' | 'modal'
  ) => void | Promise<void>
  onSandboxComputeChange?: (
    changes: SandboxComputeChange
  ) => void | Promise<void>
  onSandboxStart?: () => void | Promise<void>
  onSandboxStop?: () => void | Promise<void>
  onSandboxRestart?: () => void | Promise<void>
  onLoadLocalSystem?: () => Promise<ServerSystemInfo | null>
  /** Re-fetch sandbox status when the picker opens (picks up Modal setup done elsewhere). */
  onRefreshSandbox?: () => void | Promise<void>
}) {
  const [sandboxPickerOpen, setSandboxPickerOpen] = useState(embedded)
  const [sandboxDraft, setSandboxDraft] = useState(() =>
    draftFromSandboxStatus(sandboxStatus)
  )
  const [sandboxConfirming, setSandboxConfirming] = useState(false)
  const [localSystem, setLocalSystem] = useState<ServerSystemInfo | null>(null)
  const [localSystemLoading, setLocalSystemLoading] = useState(false)
  const refreshedOpenRef = useRef(false)
  // Status is re-fetched while a sandbox runs (uptime, idle time). Only a
  // change to what this form edits may reset the draft, or an edit in
  // progress would be thrown away on every refresh.
  const statusRef = useRef(sandboxStatus)
  statusRef.current = sandboxStatus
  const settingsKey = [
    sandboxStatus?.backend,
    sandboxStatus?.computeType,
    sandboxStatus?.gpuClass,
    sandboxStatus?.cpuCores,
    sandboxStatus?.ramGb,
    sandboxStatus?.configuredIdleTimeoutSeconds,
    sandboxStatus?.configuredMaxLifetimeSeconds,
    sandboxStatus?.modalConfigured
  ].join('|')

  useEffect(() => {
    if (!embedded && !sandboxPickerOpen) {
      refreshedOpenRef.current = false
      return
    }
    // Modal may have been configured on the Sandbox/Integrations page while
    // this chat stayed open — refresh so "not set up" clears without reload.
    if (!refreshedOpenRef.current) {
      refreshedOpenRef.current = true
      void onRefreshSandbox?.()
    }
    setSandboxDraft(draftFromSandboxStatus(statusRef.current))
    if (!onLoadLocalSystem) {
      setLocalSystem(null)
      return
    }
    let cancelled = false
    setLocalSystemLoading(true)
    void onLoadLocalSystem()
      .then(info => {
        if (!cancelled) setLocalSystem(info)
      })
      .catch(() => {
        if (!cancelled) setLocalSystem(null)
      })
      .finally(() => {
        if (!cancelled) setLocalSystemLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [embedded, sandboxPickerOpen, onLoadLocalSystem, onRefreshSandbox, settingsKey])

  const appliedSandboxBackend =
    sandboxStatus?.backend === 'modal' ? 'modal' : 'builtin'
  const sandboxDraftDirty = useMemo(() => {
    if (sandboxDraft.backend !== appliedSandboxBackend) return true
    if (sandboxDraft.backend !== 'modal') return false
    return sandboxDraftChangesSettings(sandboxDraft, sandboxStatus)
  }, [appliedSandboxBackend, sandboxDraft, sandboxStatus])

  async function confirmSandboxDraft() {
    if (!onSandboxBackendSelect || sandboxPhase !== 'idle' || sandboxConfirming) {
      return
    }
    setSandboxConfirming(true)
    try {
      if (sandboxDraft.backend === 'modal' && onSandboxComputeChange) {
        const settingsDirty = sandboxDraftChangesSettings(
          sandboxDraft,
          sandboxStatus
        )
        if (settingsDirty || sandboxDraft.backend !== appliedSandboxBackend) {
          await onSandboxComputeChange({
            computeType: sandboxDraft.computeType,
            gpuClass: sandboxDraft.gpuClass,
            cpuCores: sandboxDraft.cpuCores,
            ramGb: sandboxDraft.ramGb,
            idleTtlSeconds: sandboxDraft.idleTimeoutSeconds,
            maxLifetimeSeconds: sandboxDraft.maxLifetimeSeconds
          })
        }
      }
      if (sandboxDraft.backend !== appliedSandboxBackend) {
        await onSandboxBackendSelect(sandboxDraft.backend)
      }
      setSandboxPickerOpen(false)
      onRequestClose?.()
    } finally {
      setSandboxConfirming(false)
    }
  }

  const panel = (
    <ComposerSandboxPopoverContent
      sandboxStatus={sandboxStatus}
      sandboxPhase={sandboxPhase}
      sandboxDraft={sandboxDraft}
      sandboxDraftDirty={sandboxDraftDirty}
      sandboxConfirming={sandboxConfirming}
      appliedSandboxBackend={appliedSandboxBackend}
      localSystem={localSystem}
      localSystemLoading={localSystemLoading}
      onClose={() => {
        setSandboxPickerOpen(false)
        onRequestClose?.()
      }}
      onDraftChange={setSandboxDraft}
      onConfirm={confirmSandboxDraft}
      onSandboxStart={onSandboxStart}
      onSandboxStop={onSandboxStop}
      onSandboxRestart={onSandboxRestart}
      variant={variant}
    />
  )

  if (embedded) {
    return (
      <div className={variant === 'edit' ? 'w-full' : 'w-[16.5rem]'}>
        {panel}
      </div>
    )
  }

  return (
    <Popover open={sandboxPickerOpen} onOpenChange={setSandboxPickerOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground hover:bg-muted/50 relative inline-flex size-7 shrink-0 items-center justify-center rounded-md"
          aria-label={`Sandbox: ${sandboxStatusLabel(sandboxStatus, sandboxPhase)}`}
          title={sandboxStatusLabel(sandboxStatus, sandboxPhase)}
        >
          {sandboxPhase !== 'idle' ||
          sandboxStatus?.status === 'starting' ||
          sandboxStatus?.status === 'stopping' ? (
            <Loader className="size-4 animate-spin" />
          ) : sandboxStatus?.backend === 'modal' ? (
            <ModalGlyph className="size-4" />
          ) : (
            <Container className="size-4" />
          )}
          {sandboxPhase === 'idle' &&
          sandboxStatus?.status !== 'starting' &&
          sandboxStatus?.status !== 'stopping' ? (
            <span
              className={cn(
                'pointer-events-none absolute right-1 bottom-1 size-1.5 rounded-full',
                sandboxStatusDotClass(sandboxStatus, sandboxPhase)
              )}
            />
          ) : null}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        side="top"
        sideOffset={6}
        className="w-[16.5rem] overflow-hidden p-0"
        onOpenAutoFocus={event => event.preventDefault()}
        onCloseAutoFocus={event => event.preventDefault()}
      >
        {panel}
      </PopoverContent>
    </Popover>
  )
}
