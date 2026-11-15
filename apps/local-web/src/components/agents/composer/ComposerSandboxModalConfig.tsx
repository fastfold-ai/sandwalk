import type { SessionSandboxStatus } from '@sandwalk/agent-ui-core'
import type { ReactNode } from 'react'

import {
  formatSandboxLimit,
  lifetimeForIdle,
  type SandboxActionPhase,
  type SandboxDraft,
  sandboxIdleChoices,
  sandboxLifetimeChoices,
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
  onDraftChange,
  wide = false,
  footer
}: {
  sandboxStatus: SessionSandboxStatus | null
  sandboxDraft: SandboxDraft
  sandboxPhase: SandboxActionPhase
  sandboxConfirming: boolean
  onDraftChange: (updater: (current: SandboxDraft) => SandboxDraft) => void
  /** Spread the fields across a wide container instead of stacking them. */
  wide?: boolean
  /** Wide layout only: actions placed at the end of the last row. */
  footer?: ReactNode
}) {
  if (
    sandboxDraft.backend !== 'modal' ||
    sandboxStatus?.modalConfigured !== true
  ) {
    return null
  }

  // Modal fixes both limits when a sandbox is created. A running one keeps
  // the limits it started with until it is restarted.
  const running = sandboxStatus?.status === 'running'
  const runningDiffers =
    running &&
    ((sandboxStatus?.idleTimeoutSeconds != null &&
      sandboxStatus.idleTimeoutSeconds !== sandboxDraft.idleTimeoutSeconds) ||
      (sandboxStatus?.maxLifetimeSeconds != null &&
        sandboxStatus.maxLifetimeSeconds !== sandboxDraft.maxLifetimeSeconds))
  const limitsNote = runningDiffers
    ? 'The running sandbox keeps its current limits. Restart it to use these.'
    : 'Modal allows up to 24 h per sandbox. You pay while it is running.'

  const modeToggle = (
    <div
      className={cn(
        'rounded border p-0.5',
        wide ? 'flex h-7 w-full items-stretch' : 'inline-flex'
      )}
    >
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
          wide && 'flex-1 text-[11px]',
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
          wide && 'flex-1 text-[11px]',
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
  )

  const computeSelect =
    sandboxDraft.computeType === 'gpu' ? (
      <select
        aria-label="Compute"
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
        aria-label="Compute"
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
        {matchCpuPresetId(sandboxDraft.cpuCores, sandboxDraft.ramGb) ===
        null ? (
          <option value="custom">
            {sandboxDraft.cpuCores} CPU · {sandboxDraft.ramGb} GB
          </option>
        ) : null}
      </select>
    )

  const idleSelect = (
    <select
      aria-label="Stop when idle for"
      className={selectClassName}
      disabled={sandboxPhase !== 'idle' || sandboxConfirming}
      value={sandboxDraft.idleTimeoutSeconds}
      onChange={event => {
        const idle = Number(event.target.value)
        onDraftChange(current => ({
          ...current,
          idleTimeoutSeconds: idle,
          maxLifetimeSeconds: lifetimeForIdle(current.maxLifetimeSeconds, idle)
        }))
      }}
    >
      {sandboxIdleChoices(sandboxDraft.idleTimeoutSeconds).map(seconds => (
        <option key={seconds} value={seconds}>
          {formatSandboxLimit(seconds)}
        </option>
      ))}
    </select>
  )

  const limitSelect = (
    <select
      aria-label="Time limit"
      className={selectClassName}
      disabled={sandboxPhase !== 'idle' || sandboxConfirming}
      value={sandboxDraft.maxLifetimeSeconds}
      onChange={event => {
        const lifetime = Number(event.target.value)
        onDraftChange(current => ({
          ...current,
          maxLifetimeSeconds: lifetime
        }))
      }}
    >
      {sandboxLifetimeChoices(
        sandboxDraft.maxLifetimeSeconds,
        sandboxDraft.idleTimeoutSeconds
      ).map(seconds => (
        <option key={seconds} value={seconds}>
          {formatSandboxLimit(seconds)}
        </option>
      ))}
    </select>
  )

  const baseImage =
    sandboxDraft.computeType === 'gpu'
      ? sandboxStatus?.baseImage ||
        sandboxStatus?.gpuImage ||
        'pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime'
      : sandboxStatus?.baseImage ||
        sandboxStatus?.cpuImage ||
        'python:3.12-slim'

  if (wide) {
    // Inside the sandbox card: one row of fields across the full width,
    // then the notes on the left and the actions on the right.
    const field = 'text-muted-foreground min-w-0 space-y-1 text-[11px]'
    return (
      <>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(8rem,1fr))] gap-x-3 gap-y-2">
          <div className={field}>
            <span>Mode</span>
            {modeToggle}
          </div>
          <label className={cn(field, 'block')}>
            <span>Compute</span>
            {computeSelect}
          </label>
          <label className={cn(field, 'block')}>
            <span>Stop when idle for</span>
            {idleSelect}
          </label>
          <label className={cn(field, 'block')}>
            <span>Time limit</span>
            {limitSelect}
          </label>
        </div>
        <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
          <div className="text-muted-foreground min-w-0 flex-1 space-y-0.5 text-[11px] leading-snug">
            <p>{limitsNote}</p>
            <p className="truncate">
              Base image{' '}
              <span className="text-foreground font-mono">{baseImage}</span>
            </p>
          </div>
          {footer}
        </div>
      </>
    )
  }

  return (
    <>
      <div className="text-muted-foreground flex items-center justify-between gap-2 px-0.5 text-[10px]">
        <span>Mode</span>
        {modeToggle}
      </div>

      <div className="text-muted-foreground space-y-1 px-0.5 text-[10px]">
        <div className="flex items-center justify-between gap-2">
          <span>Compute</span>
        </div>
        {computeSelect}
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <label className="text-muted-foreground space-y-0.5 px-0.5 text-[10px]">
          <span>Stop when idle for</span>
          {idleSelect}
        </label>
        <label className="text-muted-foreground space-y-0.5 px-0.5 text-[10px]">
          <span>Time limit</span>
          {limitSelect}
        </label>
      </div>
      <p className="text-muted-foreground px-0.5 text-[10px] leading-snug">
        {limitsNote}
      </p>

      <div className="text-muted-foreground space-y-0.5 px-0.5 text-[10px]">
        <span>Base image</span>
        <div className="text-foreground truncate font-mono text-[10px]">
          {baseImage}
        </div>
      </div>
    </>
  )
}
