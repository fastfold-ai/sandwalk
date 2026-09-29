import { expect, test } from '@playwright/test'

import { resolveE2EEnv } from '../fixtures/env'
import { archiveReport, measure, type Measurement, recordMeasurement, wheelScroll } from '../fixtures/perf'
import {
  createGridFixture,
  focusPane,
  focusTerminal,
  type GridFixture,
  nonTerminalScroller,
  openGrid,
  readTerminalText,
  waitForTerminals
} from '../fixtures/seed'

const env = resolveE2EEnv()
const SUITE = 'grid'
const CONFIG = { chats: env.benchPanes, terminals: env.benchTerminals, viewport: '1600x1000' }
// One id per `playwright test` invocation; workers inherit the env.
const RUN_ID = process.env.SANDWALK_BENCH_RUN_ID ?? `${Date.now()}`

/**
 * Grid benchmarks. Not assertions on absolute numbers (machines differ) —
 * every measurement is upserted into `e2e/results/grid-latest.json`;
 * compare two runs with `pnpm e2e:compare`. A few loose sanity bounds
 * guard against catastrophic regressions (e.g. the scroll storm coming back).
 */
test.describe('grid benchmarks', () => {
  let grid: GridFixture

  const record = (m: Measurement) => {
    const latest = recordMeasurement(SUITE, m, CONFIG, RUN_ID)
    // eslint-disable-next-line no-console
    console.log(
      `  ${m.name.padEnd(20)} ${String(m.durationMs).padStart(6)}ms  longTasks=${m.longTasks} (${m.longTaskMs}ms)  fps=${m.fps}  ` +
        Object.entries(m.counters)
          .filter(([k]) => k.startsWith('terminal.') || k.startsWith('render.'))
          .map(([k, v]) => `${k}=${v}`)
          .join(' ') +
        `\n  → ${latest}`
    )
  }

  test.beforeAll(async () => {
    grid = await createGridFixture(env, { chats: env.benchPanes, terminals: env.benchTerminals })
  })

  test.afterAll(async () => {
    archiveReport(SUITE)
    await grid?.cleanup()
  })

  test('grid ready (cold open)', async ({ page }) => {
    const started = Date.now()
    await openGrid(page, grid)
    await waitForTerminals(page, grid.terminalIds)
    record({
      name: 'gridReady',
      durationMs: Date.now() - started,
      longTasks: 0,
      longTaskMs: 0,
      frames: 0,
      fps: 0,
      counters: await page.evaluate(() => window.__sandwalkPerf?.snapshot() ?? {})
    })
  })

  test('scroll a chat transcript while terminals are mounted', async ({ page }) => {
    await openGrid(page, grid)
    await waitForTerminals(page, grid.terminalIds)
    const scroller = await nonTerminalScroller(page, grid.chatIds[0])
    // Give the surface something to scroll: pad the DOM with a tall spacer.
    await page.locator(scroller).first().evaluate(el => {
      const spacer = document.createElement('div')
      spacer.style.height = '20000px'
      spacer.dataset.benchSpacer = ''
      el.firstElementChild?.appendChild(spacer)
    })
    const m = await measure(page, 'scrollTranscript', async () => {
      await wheelScroll(page, scroller, 2000)
    })
    record(m)
    // Scrolling a chat must not reposition every terminal per frame.
    const positions = m.counters['terminal.applyPosition'] ?? 0
    const ignored = m.counters['terminal.scrollIgnored'] ?? 0
    expect(ignored, 'scroll events filtered per terminal').toBeGreaterThan(0)
    expect(positions, 'terminal repositions during chat scroll').toBeLessThan(ignored)
    expect(m.counters['terminal.fit'] ?? 0).toBeLessThanOrEqual(grid.terminalIds.length)
  })

  test('switch the active pane across the grid', async ({ page }) => {
    await openGrid(page, grid)
    await waitForTerminals(page, grid.terminalIds)
    const ids = [...grid.chatIds, ...grid.terminalIds]
    const m = await measure(page, 'paneSwitch', async () => {
      for (let round = 0; round < 3; round += 1) {
        for (const id of ids) {
          await focusPane(page, id)
          await page.waitForTimeout(60)
        }
      }
    })
    record(m)
    expect(m.counters['terminal.ptyResizeRpc'] ?? 0).toBeLessThanOrEqual(grid.terminalIds.length)
  })

  test('terminal output burst', async ({ page }) => {
    await openGrid(page, grid)
    await waitForTerminals(page, grid.terminalIds)
    const termId = grid.terminalIds[0]
    await focusTerminal(page, termId)
    const marker = `bench-${Date.now()}`
    const m = await measure(page, 'terminalBurst1k', async () => {
      await page.keyboard.type(`for i in $(seq 1 1000); do echo ${marker}-$i; done\n`)
      await expect
        .poll(() => readTerminalText(page, termId), { timeout: 90_000 })
        .toContain(`${marker}-1000`)
    })
    record(m)
  })
})
