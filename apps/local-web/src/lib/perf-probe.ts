/**
 * Lightweight in-app performance counters.
 *
 * Hot paths call `perfCount('name')`; the e2e/perf harness reads the
 * totals through `window.__sandwalkPerf` (dev builds, or any build when
 * the page URL carries `?perf=1`). Increments are a single property
 * write, so it is safe to leave the calls in production code.
 */

export type PerfCounters = Record<string, number>

type PerfProbe = {
  counters: PerfCounters
  reset: () => void
  snapshot: () => PerfCounters
  /** Live xterm instances by terminal id (harness reads buffer state). */
  terminals: Map<string, unknown>
}

declare global {
  interface Window {
    __sandwalkPerf?: PerfProbe
  }
}

const counters: PerfCounters = {}

export function perfCount(name: string, by = 1): void {
  counters[name] = (counters[name] ?? 0) + by
}

export function perfSnapshot(): PerfCounters {
  return { ...counters }
}

export function perfReset(): void {
  for (const key of Object.keys(counters)) delete counters[key]
}

function shouldExpose(): boolean {
  if (typeof window === 'undefined') return false
  if (import.meta.env.DEV) return true
  try {
    return new URLSearchParams(window.location.search).get('perf') === '1'
  } catch {
    return false
  }
}

export function installPerfProbe(): void {
  if (!shouldExpose() || window.__sandwalkPerf) return
  window.__sandwalkPerf = {
    counters,
    reset: perfReset,
    snapshot: perfSnapshot,
    terminals: new Map()
  }
}

/** Track a live xterm for the harness; no-op when the probe is hidden. */
export function perfTrackTerminal(id: string, term: unknown | null): void {
  const probe = typeof window === 'undefined' ? undefined : window.__sandwalkPerf
  if (!probe) return
  if (term) probe.terminals.set(id, term)
  else probe.terminals.delete(id)
}
