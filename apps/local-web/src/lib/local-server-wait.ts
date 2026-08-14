/** How long a local unreachable API is treated as boot, not a crash. */
export const LOCAL_SERVER_START_GRACE_MS = 60_000

export const LOCAL_SERVER_START_RETRY_MS = 1_500

export const LOCAL_SERVER_DOWN_RETRY_MS = 5_000

const BOOTING_STATES = new Set([
  'starting',
  'stopped',
  'stopping',
  'partial',
  'unknown'
])

/** True while the nested agent is expected to come up (desktop cold start / relaunch). */
export function shouldShowLocalServerStarting(input: {
  local: boolean
  connecting: boolean
  unavailable: boolean
  elapsedMs: number
  desktopState: string | null
}): boolean {
  if (!input.local) return false
  if (input.desktopState === 'failed') return false
  if (input.connecting) return true
  if (!input.unavailable) return false
  if (input.desktopState && BOOTING_STATES.has(input.desktopState)) return true
  return input.elapsedMs < LOCAL_SERVER_START_GRACE_MS
}
