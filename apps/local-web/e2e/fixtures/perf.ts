import { execSync } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import type { Page } from '@playwright/test'

export type PerfCounters = Record<string, number>

export type Measurement = {
  name: string
  durationMs: number
  /** Long tasks (>50ms) observed during the measurement. */
  longTasks: number
  longTaskMs: number
  /** Animation frames delivered while measuring → rough FPS. */
  frames: number
  fps: number
  /** Delta of `window.__sandwalkPerf` counters. */
  counters: PerfCounters
}

export type BenchReport = {
  suite: string
  createdAt: string
  gitSha: string | null
  config: Record<string, unknown>
  measurements: Measurement[]
}

declare global {
  interface Window {
    __sandwalkBench?: {
      longTasks: number
      longTaskMs: number
      frames: number
      rafId: number | null
      observer: PerformanceObserver | null
    }
  }
}

async function startCollectors(page: Page): Promise<void> {
  await page.evaluate(() => {
    const state = { longTasks: 0, longTaskMs: 0, frames: 0, rafId: null as number | null, observer: null as PerformanceObserver | null }
    try {
      const observer = new PerformanceObserver(list => {
        for (const entry of list.getEntries()) {
          state.longTasks += 1
          state.longTaskMs += entry.duration
        }
      })
      observer.observe({ type: 'longtask', buffered: false })
      state.observer = observer
    } catch {
      // longtask not supported — counts stay 0
    }
    const tick = () => {
      state.frames += 1
      state.rafId = window.requestAnimationFrame(tick)
    }
    state.rafId = window.requestAnimationFrame(tick)
    window.__sandwalkBench = state
    window.__sandwalkPerf?.reset()
  })
}

async function stopCollectors(page: Page): Promise<{ longTasks: number; longTaskMs: number; frames: number; counters: PerfCounters }> {
  return page.evaluate(() => {
    const state = window.__sandwalkBench
    if (!state) return { longTasks: 0, longTaskMs: 0, frames: 0, counters: {} }
    if (state.rafId != null) window.cancelAnimationFrame(state.rafId)
    state.observer?.disconnect()
    const counters = window.__sandwalkPerf?.snapshot() ?? {}
    window.__sandwalkBench = undefined
    return { longTasks: state.longTasks, longTaskMs: Math.round(state.longTaskMs), frames: state.frames, counters }
  })
}

/** Run `action` while collecting long tasks, frames and perf counters. */
export async function measure(page: Page, name: string, action: () => Promise<void>): Promise<Measurement> {
  await startCollectors(page)
  const started = Date.now()
  await action()
  const durationMs = Date.now() - started
  const collected = await stopCollectors(page)
  const fps = durationMs > 0 ? Math.round((collected.frames / durationMs) * 1000) : 0
  return { name, durationMs, ...collected, fps }
}

/** Scroll a container with wheel events for `ms` milliseconds. */
export async function wheelScroll(page: Page, selector: string, ms: number, deltaY = 120): Promise<void> {
  const box = await page.locator(selector).first().boundingBox()
  if (!box) throw new Error(`no bounding box for ${selector}`)
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  const until = Date.now() + ms
  let direction = 1
  while (Date.now() < until) {
    await page.mouse.wheel(0, deltaY * direction)
    await page.waitForTimeout(16)
    if (Math.random() < 0.05) direction *= -1
  }
}

const RESULTS_DIR = join(process.cwd(), 'e2e', 'results')

function latestPath(suite: string, dir = RESULTS_DIR): string {
  return join(dir, `${suite}-latest.json`)
}

function readLatest(suite: string, dir = RESULTS_DIR): BenchReport | null {
  try {
    return JSON.parse(readFileSync(latestPath(suite, dir), 'utf8')) as BenchReport
  } catch {
    return null
  }
}

/**
 * Upsert one measurement into `<suite>-latest.json` right away. A failing
 * spec makes Playwright restart the worker (and with it any in-memory
 * list), so the report is assembled on disk, one measurement at a time.
 * `runId` groups measurements from one `playwright test` invocation.
 */
export function recordMeasurement(
  suite: string,
  measurement: Measurement,
  config: Record<string, unknown>,
  runId: string,
  dir = RESULTS_DIR
): string {
  mkdirSync(dir, { recursive: true })
  const existing = readLatest(suite, dir)
  const sameRun = existing?.config?.runId === runId
  const measurements = sameRun ? existing!.measurements.filter(m => m.name !== measurement.name) : []
  measurements.push(measurement)
  const report: BenchReport = {
    suite,
    createdAt: new Date().toISOString(),
    gitSha: gitSha(),
    config: { ...config, runId },
    measurements
  }
  const latest = latestPath(suite, dir)
  writeFileSync(latest, JSON.stringify(report, null, 2))
  return latest
}

/** Copy the current latest report to a timestamped archive file. */
export function archiveReport(suite: string, dir = RESULTS_DIR): { path: string; report: BenchReport } | null {
  const report = readLatest(suite, dir)
  if (!report) return null
  const stamp = report.createdAt.replace(/[:.]/g, '-')
  const path = join(dir, `${suite}-${stamp}.json`)
  writeFileSync(path, JSON.stringify(report, null, 2))
  return { path, report }
}

export function gitSha(): string | null {
  try {
    return execSync('git rev-parse --short HEAD', { encoding: 'utf8' }).trim()
  } catch {
    return null
  }
}
