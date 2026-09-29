import { expect, test } from '@playwright/test'

import { resolveE2EEnv } from '../fixtures/env'
import {
  focusTerminal,
  readTerminalBuffer,
  readTerminalText,
  seedGrid,
  type SeededGrid,
  waitForTerminals
} from '../fixtures/seed'

const env = resolveE2EEnv()

/**
 * FAS-121 regression: switching the active pane in a split used to clip
 * lines from the terminal scrollback (resize storm → SIGWINCH → shell
 * redraw). The buffer must keep every line across many pane switches.
 */
test.describe('terminal scrollback survives pane switches (FAS-121)', () => {
  let grid: SeededGrid

  test.beforeEach(async ({ page }) => {
    grid = await seedGrid(page, env, { chats: 2, terminals: 1 })
    await waitForTerminals(page, grid.terminalIds)
  })

  test.afterEach(async () => {
    await grid?.cleanup()
  })

  test('300 lines stay in the buffer after 10 pane switches', async ({ page }) => {
    const termId = grid.terminalIds[0]
    await focusTerminal(page, termId)
    const marker = `fas121-${Date.now()}`
    await page.keyboard.type(`for i in $(seq 1 300); do echo ${marker}-$i; done\n`)
    await expect
      .poll(() => readTerminalText(page, termId), { timeout: 30_000 })
      .toContain(`${marker}-300`)
    // Let the prompt settle so the buffer length is stable.
    await page.waitForTimeout(500)
    const before = await readTerminalBuffer(page, termId)
    const textBefore = await readTerminalText(page, termId)
    const markerLinesBefore = textBefore.split('\n').filter(l => l.includes(marker)).length
    expect(markerLinesBefore).toBeGreaterThanOrEqual(300)

    const [chatA, chatB] = grid.chatIds
    for (let i = 0; i < 5; i += 1) {
      await page.locator(`[data-pane-id="${chatA}"]`).click({ position: { x: 24, y: 80 } })
      await page.waitForTimeout(120)
      await page.locator(`[data-pane-id="${chatB}"]`).click({ position: { x: 24, y: 80 } })
      await page.waitForTimeout(120)
    }
    // Back to the terminal, then give any debounced fit time to run.
    await focusTerminal(page, termId)
    await page.waitForTimeout(400)

    const after = await readTerminalBuffer(page, termId)
    const textAfter = await readTerminalText(page, termId)
    const markerLinesAfter = textAfter.split('\n').filter(l => l.includes(marker)).length

    expect(markerLinesAfter, 'marker lines lost after pane switches').toBe(markerLinesBefore)
    expect(after.length, 'buffer length shrank').toBeGreaterThanOrEqual(before.length)
    expect(textAfter).toContain(`${marker}-1`)
    expect(textAfter).toContain(`${marker}-300`)
    // A pane switch in a fixed-size grid must not change the terminal grid.
    expect(after.cols).toBe(before.cols)
    expect(after.rows).toBe(before.rows)
  })

  test('pane switches do not spam PTY resizes', async ({ page }) => {
    const termId = grid.terminalIds[0]
    await focusTerminal(page, termId)
    await page.evaluate(() => window.__sandwalkPerf?.reset())
    const [chatA, chatB] = grid.chatIds
    for (let i = 0; i < 5; i += 1) {
      await page.locator(`[data-pane-id="${chatA}"]`).click({ position: { x: 24, y: 80 } })
      await page.waitForTimeout(100)
      await page.locator(`[data-pane-id="${chatB}"]`).click({ position: { x: 24, y: 80 } })
      await page.waitForTimeout(100)
    }
    await page.waitForTimeout(300)
    const counters = await page.evaluate(() => window.__sandwalkPerf?.snapshot() ?? {})
    // The pane box does not change on focus, so no fit and no RPC should run.
    expect(counters['terminal.ptyResizeRpc'] ?? 0).toBeLessThanOrEqual(1)
    expect(counters['terminal.fit'] ?? 0).toBeLessThanOrEqual(2)
  })
})
