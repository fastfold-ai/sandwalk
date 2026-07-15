import type { SessionSandboxStatus } from '@sandwalk/agent-ui-core'

import {
  CPU_PRESETS,
  DEFAULT_CPU_PRESET,
  DEFAULT_GPU_PRESET,
  matchCpuPresetId,
  matchGpuPreset
} from '@/lib/sandbox-presets'

export const selectClassName =
  'border-input bg-background h-7 w-full rounded-md border px-2 text-xs disabled:cursor-not-allowed disabled:opacity-60'

export type SandboxComputeChange = {
  computeType: 'cpu' | 'gpu'
  gpuClass: string
  cpuCores: number
  ramGb: number
}

export type SandboxDraft = {
  backend: 'builtin' | 'modal'
  computeType: 'cpu' | 'gpu'
  gpuClass: string
  cpuCores: number
  ramGb: number
}

export function formatSandboxBytes(bytes: number): string {
  const value = Math.max(0, bytes)
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB'] as const
  let n = value / 1024
  for (let i = 0; i < units.length; i += 1) {
    if (n < 1024 || i === units.length - 1) {
      return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
    }
    n /= 1024
  }
  return `${value} B`
}

export function draftFromSandboxStatus(
  status: SessionSandboxStatus | null | undefined
): SandboxDraft {
  const computeType = status?.computeType === 'gpu' ? 'gpu' : 'cpu'
  const gpuPreset =
    matchGpuPreset(String(status?.gpuClass || '')) ?? DEFAULT_GPU_PRESET
  const cpuPreset =
    CPU_PRESETS.find(
      item =>
        item.id ===
        matchCpuPresetId(Number(status?.cpuCores), Number(status?.ramGb))
    ) ?? DEFAULT_CPU_PRESET
  return {
    backend: status?.backend === 'modal' ? 'modal' : 'builtin',
    computeType,
    gpuClass: gpuPreset.gpu,
    cpuCores: computeType === 'gpu' ? gpuPreset.cpu : cpuPreset.cpu,
    ramGb: computeType === 'gpu' ? gpuPreset.ram : cpuPreset.ram
  }
}

export function formatTokenCount(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}k`
  return `${Math.max(0, Math.round(tokens))}`
}

export type SandboxActionPhase =
  | 'idle'
  | 'starting'
  | 'stopping'
  | 'restarting'

export function sandboxStatusLabel(
  status: SessionSandboxStatus | null | undefined,
  phase: SandboxActionPhase = 'idle'
) {
  if (phase === 'starting' || status?.status === 'starting') return 'Starting'
  if (phase === 'stopping' || status?.status === 'stopping') return 'Stopping'
  if (phase === 'restarting') return 'Restarting'
  if (!status) return 'Sandbox'
  if (status.backend !== 'modal') return 'Local Sandbox'
  if (status.status === 'running') return 'Modal Sandbox'
  if (status.status === 'unavailable') return 'Unavailable'
  return 'Modal Sandbox'
}

export function sandboxStatusDotClass(
  status: SessionSandboxStatus | null | undefined,
  phase: SandboxActionPhase = 'idle'
) {
  if (
    phase !== 'idle' ||
    status?.status === 'starting' ||
    status?.status === 'stopping'
  ) {
    return 'bg-muted-foreground/50'
  }
  if (!status || status.backend !== 'modal') return 'bg-muted-foreground/40'
  if (status.status === 'running') return 'bg-emerald-500'
  if (status.status === 'unavailable') return 'bg-amber-500'
  return 'bg-muted-foreground/50'
}
