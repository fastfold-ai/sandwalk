import type {
  ServerSystemInfo,
  SessionSandboxStatus
} from '@sandwalk/agent-ui-core'
import { ChevronDown, Loader } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

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
  onLoadLocalSystem
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
}) {
  const [sandboxPickerOpen, setSandboxPickerOpen] = useState(false)
  const [sandboxDraft, setSandboxDraft] = useState(() =>
    draftFromSandboxStatus(sandboxStatus)
  )
  const [sandboxConfirming, setSandboxConfirming] = useState(false)
  const [localSystem, setLocalSystem] = useState<ServerSystemInfo | null>(null)
  const [localSystemLoading, setLocalSystemLoading] = useState(false)

  useEffect(() => {
    if (!sandboxPickerOpen) return
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
  }, [sandboxPickerOpen, onLoadLocalSystem, sandboxStatus])

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
          className="text-muted-foreground hover:text-foreground inline-flex shrink-0 items-center gap-1.5 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
          aria-label="Sandbox backend"
        >
          {sandboxPhase !== 'idle' ||
          sandboxStatus?.status === 'starting' ||
          sandboxStatus?.status === 'stopping' ? (
            <Loader className="text-muted-foreground size-3.5 shrink-0 animate-spin" />
          ) : sandboxStatus?.backend === 'modal' ? (
            <>
              <ModalGlyph />
              <span
                className={cn(
                  'size-1.5 rounded-full',
                  sandboxStatusDotClass(sandboxStatus, sandboxPhase)
                )}
              />
            </>
          ) : (
            <span
              className={cn(
                'size-1.5 rounded-full',
                sandboxStatusDotClass(sandboxStatus, sandboxPhase)
              )}
            />
          )}
          <span className="font-medium">
            {sandboxStatusLabel(sandboxStatus, sandboxPhase)}
          </span>
          <ChevronDown className="text-muted-foreground size-3.5" />
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
