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
  sandboxStatusDotClass,
  sandboxStatusLabel
} from '@/components/agents/composer/sandbox-utils'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  DEFAULT_GPU_PRESET,
  matchGpuPreset
} from '@/lib/sandbox-presets'
import { cn } from '@/lib/utils'

export function ComposerSandboxPicker({
  sandboxStatus = null,
  sandboxPhase = 'idle',
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
  const [sandboxPickerOpen, setSandboxPickerOpen] = useState(false)
  const [sandboxDraft, setSandboxDraft] = useState(() =>
    draftFromSandboxStatus(sandboxStatus)
  )
  const [sandboxConfirming, setSandboxConfirming] = useState(false)
  const [localSystem, setLocalSystem] = useState<ServerSystemInfo | null>(null)
  const [localSystemLoading, setLocalSystemLoading] = useState(false)
  const refreshedOpenRef = useRef(false)

  useEffect(() => {
    if (!sandboxPickerOpen) {
      refreshedOpenRef.current = false
      return
    }
    // Modal may have been configured on the Sandbox/Integrations page while
    // this chat stayed open — refresh so "not set up" clears without reload.
    if (!refreshedOpenRef.current) {
      refreshedOpenRef.current = true
      void onRefreshSandbox?.()
    }
    setSandboxDraft(draftFromSandboxStatus(sandboxStatus))
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
  }, [sandboxPickerOpen, onLoadLocalSystem, onRefreshSandbox, sandboxStatus])

  const appliedSandboxBackend =
    sandboxStatus?.backend === 'modal' ? 'modal' : 'builtin'
  const sandboxDraftDirty = useMemo(() => {
    if (sandboxDraft.backend !== appliedSandboxBackend) return true
    if (sandboxDraft.backend !== 'modal') return false
    return (
      sandboxDraft.computeType !==
        (sandboxStatus?.computeType === 'gpu' ? 'gpu' : 'cpu') ||
      sandboxDraft.gpuClass !==
        (matchGpuPreset(String(sandboxStatus?.gpuClass || ''))?.gpu ??
          DEFAULT_GPU_PRESET.gpu) ||
      Number(sandboxDraft.cpuCores) !== Number(sandboxStatus?.cpuCores) ||
      Number(sandboxDraft.ramGb) !== Number(sandboxStatus?.ramGb)
    )
  }, [appliedSandboxBackend, sandboxDraft, sandboxStatus])

  async function confirmSandboxDraft() {
    if (!onSandboxBackendSelect || sandboxPhase !== 'idle' || sandboxConfirming) {
      return
    }
    setSandboxConfirming(true)
    try {
      if (sandboxDraft.backend === 'modal' && onSandboxComputeChange) {
        const computeDirty =
          sandboxDraft.computeType !==
            (sandboxStatus?.computeType === 'gpu' ? 'gpu' : 'cpu') ||
          sandboxDraft.gpuClass !==
            (matchGpuPreset(String(sandboxStatus?.gpuClass || ''))?.gpu ??
              DEFAULT_GPU_PRESET.gpu) ||
          Number(sandboxDraft.cpuCores) !== Number(sandboxStatus?.cpuCores) ||
          Number(sandboxDraft.ramGb) !== Number(sandboxStatus?.ramGb)
        if (computeDirty || sandboxDraft.backend !== appliedSandboxBackend) {
          await onSandboxComputeChange({
            computeType: sandboxDraft.computeType,
            gpuClass: sandboxDraft.gpuClass,
            cpuCores: sandboxDraft.cpuCores,
            ramGb: sandboxDraft.ramGb
          })
        }
      }
      if (sandboxDraft.backend !== appliedSandboxBackend) {
        await onSandboxBackendSelect(sandboxDraft.backend)
      }
      setSandboxPickerOpen(false)
    } finally {
      setSandboxConfirming(false)
    }
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
        <ComposerSandboxPopoverContent
          sandboxStatus={sandboxStatus}
          sandboxPhase={sandboxPhase}
          sandboxDraft={sandboxDraft}
          sandboxDraftDirty={sandboxDraftDirty}
          sandboxConfirming={sandboxConfirming}
          appliedSandboxBackend={appliedSandboxBackend}
          localSystem={localSystem}
          localSystemLoading={localSystemLoading}
          onClose={() => setSandboxPickerOpen(false)}
          onDraftChange={setSandboxDraft}
          onConfirm={confirmSandboxDraft}
          onSandboxStart={onSandboxStart}
          onSandboxStop={onSandboxStop}
          onSandboxRestart={onSandboxRestart}
        />
      </PopoverContent>
    </Popover>
  )
}
