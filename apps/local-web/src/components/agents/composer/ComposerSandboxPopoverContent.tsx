import type {
  ServerSystemInfo,
  SessionSandboxStatus
} from '@sandwalk/agent-ui-core'
import { Loader, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ModalGlyph } from '@/components/agents/composer/ModalGlyph'
import {
  formatSandboxBytes,
  type SandboxActionPhase,
  type SandboxDraft,
  selectClassName
} from '@/components/agents/composer/sandbox-utils'
import { Button } from '@/components/ui/button'
import {
  CPU_PRESETS,
  DEFAULT_CPU_PRESET,
  DEFAULT_GPU_PRESET,
  GPU_PRESETS,
  matchCpuPresetId,
  matchGpuPreset
} from '@/lib/sandbox-presets'
import { cn } from '@/lib/utils'

export function ComposerSandboxPopoverContent({
  sandboxStatus,
  sandboxPhase,
  sandboxDraft,
  sandboxDraftDirty,
  sandboxConfirming,
  appliedSandboxBackend,
  localSystem,
  localSystemLoading,
  onClose,
  onDraftChange,
  onConfirm,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart
}: {
  sandboxStatus: SessionSandboxStatus | null
  sandboxPhase: SandboxActionPhase
  sandboxDraft: SandboxDraft
  sandboxDraftDirty: boolean
  sandboxConfirming: boolean
  appliedSandboxBackend: 'builtin' | 'modal'
  localSystem: ServerSystemInfo | null
  localSystemLoading: boolean
  onClose: () => void
  onDraftChange: (
    updater: (current: SandboxDraft) => SandboxDraft
  ) => void
  onConfirm: () => void | Promise<void>
  onSandboxStart?: () => void | Promise<void>
  onSandboxStop?: () => void | Promise<void>
  onSandboxRestart?: () => void | Promise<void>
}) {
  return (
    <>
      <div className="flex items-center justify-between gap-2 border-b px-2.5 py-1.5">
        <span className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
          Sandbox
        </span>
        <Link
          to="/dashboard/agent/sandbox"
          className="text-muted-foreground hover:text-foreground text-[10px] font-medium underline-offset-2 hover:underline"
          onClick={onClose}
        >
          Settings
        </Link>
      </div>
      <div className="space-y-1.5 p-2">
        <div className="inline-flex w-full rounded-md border p-0.5">
          <button
            type="button"
            disabled={sandboxPhase !== 'idle' || sandboxConfirming}
            onClick={() =>
              onDraftChange(current => ({
                ...current,
                backend: 'builtin'
              }))
            }
            className={cn(
              'flex flex-1 items-center justify-center gap-1 rounded px-1.5 py-1 text-[11px] font-medium transition-colors',
              sandboxDraft.backend === 'builtin'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
              (sandboxPhase !== 'idle' || sandboxConfirming) &&
                'cursor-not-allowed opacity-60'
            )}
          >
            <span className="bg-muted-foreground/40 size-1.5 rounded-full" />
            Local
          </button>
          {sandboxStatus?.modalConfigured !== true ? (
            <div className="text-muted-foreground flex flex-1 items-center justify-center gap-1 rounded px-1.5 py-1 text-[11px] opacity-60">
              <ModalGlyph className="size-3 opacity-70" />
              Modal
            </div>
          ) : (
            <button
              type="button"
              disabled={sandboxPhase !== 'idle' || sandboxConfirming}
              onClick={() =>
                onDraftChange(current => ({
                  ...current,
                  backend: 'modal'
                }))
              }
              className={cn(
                'flex flex-1 items-center justify-center gap-1 rounded px-1.5 py-1 text-[11px] font-medium transition-colors',
                sandboxDraft.backend === 'modal'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
                (sandboxPhase !== 'idle' || sandboxConfirming) &&
                  'cursor-not-allowed opacity-60'
              )}
            >
              <ModalGlyph className="size-3" />
              Modal
            </button>
          )}
        </div>

        {sandboxStatus?.modalConfigured !== true ? (
          <p className="text-muted-foreground px-0.5 text-[10px] leading-snug">
            Modal not set up.{' '}
            <Link
              to="/dashboard/integrations/modal"
              className="text-foreground font-medium underline underline-offset-2"
              onClick={onClose}
            >
              Set up
            </Link>
          </p>
        ) : null}

        {sandboxDraft.backend === 'builtin' ? (
          <div className="bg-muted/30 space-y-1 rounded-md border border-border/60 px-2 py-1.5 text-[10px]">
            <p className="text-muted-foreground font-medium tracking-wide uppercase">
              This machine
            </p>
            {localSystemLoading && !localSystem ? (
              <p className="text-muted-foreground">Loading system info…</p>
            ) : localSystem ? (
              <div className="text-foreground space-y-0.5">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-muted-foreground">Chip</span>
                  <span className="min-w-0 text-right leading-snug">
                    {localSystem.chipName?.trim() ||
                      localSystem.label ||
                      `${localSystem.platform} · ${localSystem.arch}`}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground">RAM</span>
                  <span className="tabular-nums">
                    {formatSandboxBytes(localSystem.ramUsedBytes)} /{' '}
                    {formatSandboxBytes(localSystem.ramTotalBytes)}
                  </span>
                </div>
                {localSystem.gpuCores != null ? (
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-muted-foreground">GPU cores</span>
                    <span className="tabular-nums">{localSystem.gpuCores}</span>
                  </div>
                ) : null}
                <div className="flex items-center justify-between gap-2">
                  <span className="text-muted-foreground">Arch</span>
                  <span className="truncate">
                    {localSystem.arch}
                    {localSystem.osVersion ? ` · ${localSystem.osVersion}` : ''}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-muted-foreground">
                Local Python environment on this computer.
              </p>
            )}
          </div>
        ) : null}

        {sandboxDraft.backend === 'modal' &&
        sandboxStatus?.modalConfigured === true ? (
          <>
            <div className="text-muted-foreground flex items-center justify-between gap-2 px-0.5 text-[10px]">
              <span>Mode</span>
              <div className="inline-flex rounded border p-0.5">
                <button
                  type="button"
                  disabled={sandboxPhase !== 'idle' || sandboxConfirming}
                  onClick={() => {
                    const preset =
                      CPU_PRESETS.find(
                        item =>
                          item.id ===
                          matchCpuPresetId(
                            sandboxDraft.cpuCores,
                            sandboxDraft.ramGb
                          )
                      ) ?? DEFAULT_CPU_PRESET
                    onDraftChange(current => ({
                      ...current,
                      computeType: 'cpu',
                      cpuCores: preset.cpu,
                      ramGb: preset.ram
                    }))
                  }}
                  className={cn(
                    'rounded px-1.5 py-0.5 text-[10px] font-medium',
                    sandboxDraft.computeType !== 'gpu'
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground',
                    (sandboxPhase !== 'idle' || sandboxConfirming) &&
                      'cursor-not-allowed opacity-60'
                  )}
                >
                  CPU
                </button>
                <button
                  type="button"
                  disabled={sandboxPhase !== 'idle' || sandboxConfirming}
                  onClick={() => {
                    const preset =
                      matchGpuPreset(sandboxDraft.gpuClass) ?? DEFAULT_GPU_PRESET
                    onDraftChange(current => ({
                      ...current,
                      computeType: 'gpu',
                      gpuClass: preset.gpu,
                      cpuCores: preset.cpu,
                      ramGb: preset.ram
                    }))
                  }}
                  className={cn(
                    'rounded px-1.5 py-0.5 text-[10px] font-medium',
                    sandboxDraft.computeType === 'gpu'
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground',
                    (sandboxPhase !== 'idle' || sandboxConfirming) &&
                      'cursor-not-allowed opacity-60'
                  )}
                >
                  GPU
                </button>
              </div>
            </div>

            <div className="text-muted-foreground space-y-1 px-0.5 text-[10px]">
              <div className="flex items-center justify-between gap-2">
                <span>Compute</span>
              </div>
              {sandboxDraft.computeType === 'gpu' ? (
                <select
                  className={selectClassName}
                  disabled={sandboxPhase !== 'idle' || sandboxConfirming}
                  value={
                    matchGpuPreset(sandboxDraft.gpuClass)?.gpu ??
                    DEFAULT_GPU_PRESET.gpu
                  }
                  onChange={event => {
                    const preset =
                      matchGpuPreset(event.target.value) ?? DEFAULT_GPU_PRESET
                    onDraftChange(current => ({
                      ...current,
                      computeType: 'gpu',
                      gpuClass: preset.gpu,
                      cpuCores: preset.cpu,
                      ramGb: preset.ram
                    }))
                  }}
                >
                  {GPU_PRESETS.map(preset => (
                    <option key={preset.gpu} value={preset.gpu}>
                      {preset.shortLabel}
                    </option>
                  ))}
                </select>
              ) : (
                <select
                  className={selectClassName}
                  disabled={sandboxPhase !== 'idle' || sandboxConfirming}
                  value={
                    matchCpuPresetId(
                      sandboxDraft.cpuCores,
                      sandboxDraft.ramGb
                    ) ?? 'custom'
                  }
                  onChange={event => {
                    if (event.target.value === 'custom') return
                    const preset =
                      CPU_PRESETS.find(item => item.id === event.target.value) ??
                      DEFAULT_CPU_PRESET
                    onDraftChange(current => ({
                      ...current,
                      computeType: 'cpu',
                      cpuCores: preset.cpu,
                      ramGb: preset.ram
                    }))
                  }}
                >
                  {CPU_PRESETS.map(preset => (
                    <option key={preset.id} value={preset.id}>
                      {preset.shortLabel}
                    </option>
                  ))}
                  {matchCpuPresetId(
                    sandboxDraft.cpuCores,
                    sandboxDraft.ramGb
                  ) === null ? (
                    <option value="custom">
                      {sandboxDraft.cpuCores} CPU · {sandboxDraft.ramGb} GB
                    </option>
                  ) : null}
                </select>
              )}
            </div>

            <div className="text-muted-foreground space-y-0.5 px-0.5 text-[10px]">
              <span>Base image</span>
              <div className="text-foreground truncate font-mono text-[10px]">
                {sandboxStatus?.cpuImage || 'python:3.12-slim'}
              </div>
            </div>
          </>
        ) : null}

        <div className="flex items-center gap-1 pt-0.5">
          <Button
            type="button"
            size="sm"
            className="h-7 flex-1 px-2 text-[11px]"
            disabled={
              sandboxPhase !== 'idle' ||
              sandboxConfirming ||
              !sandboxDraftDirty ||
              (sandboxDraft.backend === 'modal' &&
                sandboxStatus?.modalConfigured !== true)
            }
            onClick={() => void onConfirm()}
          >
            {sandboxConfirming ? (
              <>
                <Loader className="size-3 animate-spin" />
                Applying…
              </>
            ) : (
              'Confirm'
            )}
          </Button>

          {sandboxDraft.backend === 'modal' &&
          sandboxStatus?.modalConfigured === true &&
          appliedSandboxBackend === 'modal' ? (
            sandboxPhase !== 'idle' ||
            sandboxStatus.status === 'starting' ||
            sandboxStatus.status === 'stopping' ? (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="h-7 px-2 text-[11px]"
                disabled
              >
                <Loader className="size-3 animate-spin" />
              </Button>
            ) : sandboxStatus.status === 'running' ? (
              <>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="text-destructive hover:text-destructive h-7 px-2 text-[11px]"
                  onClick={() => void onSandboxStop?.()}
                >
                  Stop
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  className="h-7 px-2"
                  aria-label="Restart sandbox"
                  onClick={() => void onSandboxRestart?.()}
                >
                  <RefreshCw className="size-3" />
                </Button>
              </>
            ) : (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="h-7 px-2 text-[11px]"
                disabled={
                  sandboxStatus.status === 'unavailable' ||
                  !onSandboxStart ||
                  sandboxConfirming
                }
                onClick={() => void onSandboxStart?.()}
              >
                Start
              </Button>
            )
          ) : null}
        </div>

        {sandboxStatus?.detail &&
        sandboxStatus.status !== 'running' &&
        appliedSandboxBackend === 'modal' ? (
          <p className="text-muted-foreground px-0.5 text-[10px] leading-snug">
            {sandboxStatus.detail}
          </p>
        ) : null}
      </div>
    </>
  )
}
