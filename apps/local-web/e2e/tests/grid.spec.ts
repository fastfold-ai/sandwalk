import { expect, test } from '@playwright/test'

import { resolveE2EEnv } from '../fixtures/env'
import { focusTerminal, readTerminalText, type SeededGrid, seedGrid, waitForTerminals } from '../fixtures/seed'

const env = resolveE2EEnv()

test.describe('split grid with chats and terminals', () => {
  let grid: SeededGrid

  test.beforeEach(async ({ page }) => {
    grid = await seedGrid(page, env, { chats: 3, terminals: 2 })
  })

  test.afterEach(async () => {
    await grid?.cleanup()
  })

  test('renders every pane once and keeps the strip/sidebar in sync', async ({ page }) => {
    for (const id of [...grid.chatIds, ...grid.terminalIds]) {
      await expect(page.locator(`[data-pane-id="${id}"]`)).toHaveCount(1)
      await expect(page.locator(`[data-pane-id="${id}"]`)).toBeVisible()
    }
    await expect(page.locator('[data-pane-kind="chat"]')).toHaveCount(grid.chatIds.length)
    await expect(page.locator('[data-pane-kind="terminal"]')).toHaveCount(grid.terminalIds.length)
    // The group chip is the only open tab in the strip.
    await expect(page.locator(`[data-tab-id="${grid.groupId}"]`)).toBeVisible()
    // Exactly one pane is focused.
    await expect(page.locator('[data-pane-focused="true"]')).toHaveCount(1)
  })

  test('terminal portal hosts sit over their placeholders', async ({ page }) => {
    await waitForTerminals(page, grid.terminalIds)
    for (const id of grid.terminalIds) {
      const placeholder = await page.locator(`[data-terminal-placeholder="${id}"]`).boundingBox()
      const host = await page.locator(`[data-terminal-portal-host="${id}"]`).boundingBox()
      expect(placeholder, `placeholder ${id}`).not.toBeNull()
      expect(host, `host ${id}`).not.toBeNull()
      if (!placeholder || !host) continue
      expect(Math.abs(host.x - placeholder.x)).toBeLessThan(2)
      expect(Math.abs(host.y - placeholder.y)).toBeLessThan(2)
      expect(Math.abs(host.width - placeholder.width)).toBeLessThan(2)
      expect(Math.abs(host.height - placeholder.height)).toBeLessThan(2)
    }
  })

  test('typing in a terminal round-trips through the PTY', async ({ page }) => {
    await waitForTerminals(page, grid.terminalIds)
    const id = grid.terminalIds[0]
    await focusTerminal(page, id)
    const marker = `e2e-marker-${Date.now()}`
    await page.keyboard.type(`echo ${marker}\n`)
    await expect.poll(() => readTerminalText(page, id), { timeout: 20_000 }).toContain(marker)
  })

  test('clicking a pane moves focus and repositions nothing else', async ({ page }) => {
    await waitForTerminals(page, grid.terminalIds)
    const [first, second] = grid.chatIds
    const before = await page.locator(`[data-terminal-portal-host="${grid.terminalIds[0]}"]`).boundingBox()
    await page.locator(`[data-pane-id="${second}"]`).click({ position: { x: 24, y: 80 } })
    await expect(page.locator(`[data-pane-id="${second}"][data-pane-focused="true"]`)).toHaveCount(1)
    await page.locator(`[data-pane-id="${first}"]`).click({ position: { x: 24, y: 80 } })
    await expect(page.locator(`[data-pane-id="${first}"][data-pane-focused="true"]`)).toHaveCount(1)
    const after = await page.locator(`[data-terminal-portal-host="${grid.terminalIds[0]}"]`).boundingBox()
    expect(before).not.toBeNull()
    expect(after).not.toBeNull()
    if (before && after) {
      expect(Math.abs(after.x - before.x)).toBeLessThan(2)
      expect(Math.abs(after.width - before.width)).toBeLessThan(2)
    }
  })
})
