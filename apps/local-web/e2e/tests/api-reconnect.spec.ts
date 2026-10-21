import { expect, test } from '@playwright/test'

import { resolveE2EEnv } from '../fixtures/env'
import { type SeededGrid,seedGrid } from '../fixtures/seed'

const env = resolveE2EEnv()

/**
 * The API goes away (serve restart, menubar helper relaunch) and comes back.
 * The SPA must notice on its own and re-bootstrap — sessions list, event
 * streams — without a page reload. Simulated by refusing every /v1 request
 * for a while; the health watchdog + local-server retry loop do the rest.
 */
test.describe('UI recovers from an API outage', () => {
  let grid: SeededGrid

  test.beforeEach(async ({ page }) => {
    grid = await seedGrid(page, env, { chats: 2, terminals: 0 })
  })

  test.afterEach(async () => {
    await grid?.cleanup()
  })

  test('re-bootstraps after the backend is unreachable for a while', async ({ page }) => {
    test.setTimeout(120_000)
    const apiHost = new URL(env.apiUrl).host
    const seen: string[] = []
    let outage = false
    let outageRequests = 0
    page.on('request', req => {
      const url = req.url()
      if (!url.includes(apiHost)) return
      const path = new URL(url).pathname
      if (outage) outageRequests += 1
      else seen.push(path)
    })

    // Let the first boot settle, then pull the plug.
    await page.waitForTimeout(3_000)
    await page.route(`**/${apiHost}/**`, route => route.abort('connectionrefused'))
    outage = true
    // Watchdog: 2 misses × 5s, plus the retry loop's first tick.
    await page.waitForTimeout(16_000)
    expect(outageRequests, 'app kept probing while the API was down').toBeGreaterThan(2)

    seen.length = 0
    outage = false
    await page.unroute(`**/${apiHost}/**`)

    // Recovery: connect() runs (health), reloads the list, reopens streams.
    await expect
      .poll(() => seen.some(p => p === '/v1/health'), { timeout: 30_000, message: 'health probe after recovery' })
      .toBe(true)
    await expect
      .poll(() => seen.some(p => p === '/v1/sessions'), { timeout: 30_000, message: 'sessions list reloaded' })
      .toBe(true)
    await expect
      .poll(() => seen.some(p => p.startsWith('/v1/events')), { timeout: 30_000, message: 'event stream reopened' })
      .toBe(true)
    // And the grid is still there (no gate stuck on screen).
    await expect(page.locator('[data-pane-id]')).toHaveCount(grid.chatIds.length)
  })
})
