import type { SessionSandboxStatus } from '@sandwalk/agent-ui-core'

import {
  type SandboxActionPhase,
  type SandboxDraft,
  selectClassName
} from '@/components/agents/composer/sandbox-utils'
import {
  CPU_PRESETS,
  DEFAULT_CPU_PRESET,
  DEFAULT_GPU_PRESET,
  GPU_PRESETS,
  matchCpuPresetId,
  matchGpuPreset
} from '@/lib/sandbox-presets'
import { cn } from '@/lib/utils'

export function ComposerSandboxModalConfig({
  sandboxStatus,
  sandboxDraft,
  sandboxPhase,
  sandboxConfirming,
  onDraftChange
}: {
  sandboxStatus: SessionSandboxStatus | null
  sandboxDraft: SandboxDraft
  sandboxPhase: SandboxActionPhase
  sandboxConfirming: boolean
  onDraftChange: (updater: (current: SandboxDraft) => SandboxDraft) => void
}) {
  if (
    sandboxDraft.backend !== 'modal' ||
    sandboxStatus?.modalConfigured !== true
  ) {
    return null
  }

  return (
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
                    matchCpuPresetId(sandboxDraft.cpuCores, sandboxDraft.ramGb)
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
              matchGpuPreset(sandboxDraft.gpuClass)?.gpu ?? DEFAULT_GPU_PRESET.gpu
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
              matchCpuPresetId(sandboxDraft.cpuCores, sandboxDraft.ramGb) ??
              'custom'
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
          {sandboxDraft.computeType === 'gpu'
            ? sandboxStatus?.baseImage ||
              sandboxStatus?.gpuImage ||
              'pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime'
            : sandboxStatus?.baseImage ||
              sandboxStatus?.cpuImage ||
              'python:3.12-slim'}
        </div>
      </div>
    </>
  )
}
