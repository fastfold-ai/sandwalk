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
  /** Seconds idle before Modal stops the sandbox. */
  idleTtlSeconds?: number
  /** Seconds after creation when Modal stops the sandbox, busy or not. */
  maxLifetimeSeconds?: number
}

export type SandboxDraft = {
  backend: 'builtin' | 'modal'
  computeType: 'cpu' | 'gpu'
  gpuClass: string
  cpuCores: number
  ramGb: number
  idleTimeoutSeconds: number
  maxLifetimeSeconds: number
}

const MINUTE = 60
const HOUR = 3600
/** Modal's ceiling for one sandbox. */
export const SANDBOX_MAX_LIFETIME_SECONDS = 24 * HOUR
export const DEFAULT_SANDBOX_IDLE_SECONDS = 10 * MINUTE
export const DEFAULT_SANDBOX_LIFETIME_SECONDS = 30 * MINUTE
const IDLE_CHOICES = [
  5 * MINUTE,
  10 * MINUTE,
  30 * MINUTE,
  HOUR,
  2 * HOUR,
  4 * HOUR
]
const LIFETIME_CHOICES = [
  30 * MINUTE,
  HOUR,
  2 * HOUR,
  4 * HOUR,
  8 * HOUR,
  12 * HOUR,
  SANDBOX_MAX_LIFETIME_SECONDS
]

function withCurrent(choices: number[], current: number) {
  return choices.includes(current)
    ? choices
    : [...choices, current].sort((a, b) => a - b)
}

/** Idle timeouts to offer. A value set elsewhere stays selectable. */
export function sandboxIdleChoices(current: number) {
  return withCurrent(IDLE_CHOICES, current)
}

/** Time limits to offer: always longer than the idle timeout, up to 24 hours. */
export function sandboxLifetimeChoices(current: number, idleSeconds: number) {
  return withCurrent(LIFETIME_CHOICES, current).filter(
    seconds => seconds > idleSeconds
  )
}

/** The time limit must outlast the idle timeout. Move it up when it does not. */
export function lifetimeForIdle(lifetimeSeconds: number, idleSeconds: number) {
  if (lifetimeSeconds > idleSeconds) return lifetimeSeconds
  return (
    LIFETIME_CHOICES.find(seconds => seconds > idleSeconds) ??
    SANDBOX_MAX_LIFETIME_SECONDS
  )
}

function configuredSeconds(value: unknown, fallback: number) {
  const seconds = Number(value)
  return Number.isFinite(seconds) && seconds > 0 ? seconds : fallback
}

/** True when the draft's compute or lifetime differs from what is saved. */
export function sandboxDraftChangesSettings(
  draft: SandboxDraft,
  status: SessionSandboxStatus | null | undefined
) {
  const saved = draftFromSandboxStatus(status)
  return (
    draft.computeType !== saved.computeType ||
    draft.gpuClass !== saved.gpuClass ||
    Number(draft.cpuCores) !== Number(status?.cpuCores) ||
    Number(draft.ramGb) !== Number(status?.ramGb) ||
    draft.idleTimeoutSeconds !== saved.idleTimeoutSeconds ||
    draft.maxLifetimeSeconds !== saved.maxLifetimeSeconds
  )
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
    ramGb: computeType === 'gpu' ? gpuPreset.ram : cpuPreset.ram,
    idleTimeoutSeconds: configuredSeconds(
      status?.configuredIdleTimeoutSeconds,
      DEFAULT_SANDBOX_IDLE_SECONDS
    ),
    maxLifetimeSeconds: configuredSeconds(
      status?.configuredMaxLifetimeSeconds,
      DEFAULT_SANDBOX_LIFETIME_SECONDS
    )
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

/** A launched or transitioning sandbox, not the idle local default. */
export function sandboxIsLive(
  status: SessionSandboxStatus | null | undefined,
  phase: SandboxActionPhase = 'idle'
) {
  if (phase !== 'idle') return true
  if (!status) return false
  if (
    status.status === 'running' ||
    status.status === 'starting' ||
    status.status === 'stopping'
  ) {
    return true
  }
  return status.backend === 'modal' && status.status === 'ready'
}

/** Modal ended it on its own and the server still remembers when and why. */
export function sandboxStoppedOnItsOwn(
  status: SessionSandboxStatus | null | undefined,
  phase: SandboxActionPhase = 'idle'
) {
  return (
    phase === 'idle' &&
    status?.backend === 'modal' &&
    status.status === 'stopped' &&
    Boolean(status.stoppedAt)
  )
}

/** The floating sandbox chip shows for a live sandbox and for one that just ended. */
export function sandboxChipVisible(
  status: SessionSandboxStatus | null | undefined,
  phase: SandboxActionPhase = 'idle'
) {
  return sandboxIsLive(status, phase) || sandboxStoppedOnItsOwn(status, phase)
}

/** A configured limit, e.g. 600 → "10 min", 7200 → "2 h". */
export function formatSandboxLimit(seconds: number) {
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.round((seconds % 3600) / 60)
    return minutes ? `${hours} h ${minutes} min` : `${hours} h`
  }
  if (seconds >= 60) return `${Math.round(seconds / 60)} min`
  return `${seconds} s`
}

function msUntil(iso: string | null | undefined, now: number) {
  const at = iso ? Date.parse(iso) : Number.NaN
  return Number.isFinite(at) ? at - now : null
}

/**
 * When a running sandbox will stop, e.g.
 * "Stops after 10 min idle (about 7m 12s left) · 30 min limit (28m 6s left)".
 * The idle part is our estimate: Modal does not report idle time.
 */
export function sandboxLifecycleLine(
  status: SessionSandboxStatus | null | undefined,
  now: number
) {
  if (!status || status.status !== 'running') return ''
  const parts: string[] = []
  const idle = Number(status.idleTimeoutSeconds)
  if (Number.isFinite(idle) && idle > 0) {
    const sinceActive = msUntil(status.lastActiveAt, now)
    if (status.busy) {
      parts.push(`Running a command · stops after ${formatSandboxLimit(idle)} idle`)
    } else if (sinceActive == null) {
      parts.push(`Stops after ${formatSandboxLimit(idle)} idle`)
    } else {
      const left = sinceActive + idle * 1000
      parts.push(
        left > 0
          ? `Stops after ${formatSandboxLimit(idle)} idle (about ${formatSandboxElapsed(left)} left)`
          : `Stops after ${formatSandboxLimit(idle)} idle (any moment now)`
      )
    }
  }
  const limit = Number(status.maxLifetimeSeconds)
  if (Number.isFinite(limit) && limit > 0) {
    const left = msUntil(status.expiresAt, now)
    parts.push(
      left == null
        ? `${formatSandboxLimit(limit)} limit`
        : `${formatSandboxLimit(limit)} limit (${formatSandboxElapsed(left)} left)`
    )
  }
  return parts.join(' · ')
}

/** A rough duration for a glance: "under a minute", "3 min", "2 h 10 min". */
export function formatSandboxRough(ms: number) {
  const minutes = Math.round(Math.max(0, ms) / 60_000)
  if (minutes < 1) return 'under a minute'
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} h ${rest} min` : `${hours} h`
}

/**
 * The one thing worth a glance: when the sandbox stops next, e.g.
 * "Stops in 3 min if idle" or "Stops in 23 min". `sandboxLifecycleLine` has
 * both rules in full for a tooltip.
 */
export function sandboxLifecycleSummary(
  status: SessionSandboxStatus | null | undefined,
  now: number
) {
  if (!status || status.status !== 'running') return ''
  const idle = Number(status.idleTimeoutSeconds)
  const hasIdle = Number.isFinite(idle) && idle > 0
  const sinceActive = msUntil(status.lastActiveAt, now)
  const idleLeft =
    hasIdle && !status.busy && sinceActive != null
      ? sinceActive + idle * 1000
      : null
  const limitLeft = msUntil(status.expiresAt, now)
  if (idleLeft != null && (limitLeft == null || idleLeft <= limitLeft)) {
    return idleLeft > 0
      ? `Stops in ${formatSandboxRough(idleLeft)} if idle`
      : 'Stops any moment'
  }
  if (limitLeft != null) {
    return limitLeft > 0
      ? `Stops in ${formatSandboxRough(limitLeft)}`
      : 'Stops any moment'
  }
  if (hasIdle && !status.busy) {
    return `Stops after ${formatSandboxLimit(idle)} idle`
  }
  return ''
}

/** "Stopped 4 min ago · idle timeout" for a sandbox Modal ended. */
export function sandboxStopSummary(
  status: SessionSandboxStatus | null | undefined,
  now: number
) {
  const since = msUntil(status?.stoppedAt, now)
  if (!status || since == null) return ''
  const ago = `Stopped ${formatSandboxRough(-since)} ago`
  if (status.stopReason === 'idle') return `${ago} · idle timeout`
  if (status.stopReason === 'time_limit') return `${ago} · time limit`
  if (status.stopReason === 'timeout') return `${ago} · timeout`
  return ago
}

/** "Stopped 4m 10s ago after 10 min idle" for a sandbox Modal ended. */
export function sandboxStopLine(
  status: SessionSandboxStatus | null | undefined,
  now: number
) {
  const since = msUntil(status?.stoppedAt, now)
  if (!status || since == null) return ''
  const ago = `Stopped ${formatSandboxElapsed(-since)} ago`
  const idle = Number(status.idleTimeoutSeconds)
  const limit = Number(status.maxLifetimeSeconds)
  if (status.stopReason === 'idle' && idle > 0) {
    return `${ago} after ${formatSandboxLimit(idle)} idle`
  }
  if (status.stopReason === 'time_limit' && limit > 0) {
    return `${ago} at the ${formatSandboxLimit(limit)} limit`
  }
  if (status.stopReason === 'timeout') return `${ago} on a timeout`
  return ago
}

export function formatSandboxElapsed(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}

export function sandboxBackendName(
  status: SessionSandboxStatus | null | undefined
) {
  return status?.backend === 'modal' ? 'Modal' : 'Local'
}

/** Compute line for the sandbox row, e.g. "T4 GPU · 4 CPU · 16 GB RAM". */
export function sandboxSpecs(status: SessionSandboxStatus | null | undefined) {
  if (!status) return ''
  const parts: string[] = []
  const gpu = String(status.gpuClass || '').trim()
  if (status.computeType === 'gpu' && gpu) parts.push(`${gpu} GPU`)
  const cpu = Number(status.cpuCores)
  if (Number.isFinite(cpu) && cpu > 0) parts.push(`${cpu} CPU`)
  const ram = Number(status.ramGb)
  if (Number.isFinite(ram) && ram > 0) parts.push(`${ram} GB RAM`)
  return parts.join(' · ')
}

/** Shown in place of the uptime while the sandbox is changing state. */
export function sandboxTransitionLabel(
  status: SessionSandboxStatus | null | undefined,
  phase: SandboxActionPhase = 'idle'
) {
  if (phase === 'restarting') return 'Restarting…'
  if (phase === 'starting' || status?.status === 'starting') return 'Starting…'
  if (phase === 'stopping' || status?.status === 'stopping') return 'Stopping…'
  return null
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
