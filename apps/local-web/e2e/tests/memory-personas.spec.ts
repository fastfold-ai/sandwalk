import { expect, test } from '@playwright/test'

import { resolveE2EEnv } from '../fixtures/env'

test.describe('Memory, Omnigraph Cookbooks, and Persona Specialists UI', () => {
  test('renders Persona Specialists grid, Profile drawer, and Memory & Wiki Ontology Explorer', async ({
    page
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    const env = resolveE2EEnv()
    await page.addInitScript(
      ({ apiUrl, apiKey }) => {
        window.localStorage.setItem('fastfold.backend.url', apiUrl)
        window.localStorage.setItem('fastfold.sidebar-collapsed', 'false')
        if (apiKey) {
          window.localStorage.setItem(
            'sandwalk.remembered-auth',
            JSON.stringify({
              [apiUrl]: {
                apiKey,
                expiresAt: Date.now() + 60 * 60 * 1000
              }
            })
          )
        }
      },
      { apiUrl: env.apiUrl, apiKey: env.apiKey }
    )

    // 1. Navigate to Specialists (Agents Persona Grid)
    await page.goto('/dashboard/specialists')
    await expect(page.getByRole('heading', { name: 'Agents' })).toBeVisible({
      timeout: 15_000
    })
    await expect(page.getByText('Otium').first()).toBeVisible()
    await expect(page.getByText('Nova').first()).toBeVisible()
    await expect(page.getByText('Atlas').first()).toBeVisible()
    await expect(page.getByText('Milo').first()).toBeVisible()
    await expect(page.getByText('Soren').first()).toBeVisible()

    // Click Otium card to open the right-side Profile Inspector Drawer
    await page.getByText('Otium').first().click()
    await expect(page.getByRole('heading', { name: 'Profile' })).toBeVisible()
    await expect(
      page.getByText('Cognitive Priors & Biases (PRIORS.md)')
    ).toBeVisible()

    // Switch to Memories tab inside the Profile drawer
    await page.getByRole('button', { name: /^Memories/ }).click()
    await expect(
      page.getByPlaceholder(/Teach Otium a durable rule or memory/i)
    ).toBeVisible()

    // Click "Start Chat with Otium" play button in the Profile drawer
    await page.getByTitle('Start Chat with Otium').click()
    const specialistChip = page.getByTestId('composer-selected-specialist-chip')
    await expect(specialistChip).toBeVisible({ timeout: 15_000 })
    await expect(specialistChip).toContainText('Otium')

    // Click the specialist chip to open the + menu Specialist flyout with O'Reilly animal icons
    await specialistChip.locator('button').first().click()
    await expect(page.getByText('SPECIALIST', { exact: false }).first()).toBeVisible()

    // 2. Navigate to Memory & Wiki (/dashboard/memory)
    await page.goto('/dashboard/memory')
    await expect(
      page.getByRole('heading', { name: /Memory & Knowledge/i })
    ).toBeVisible({ timeout: 15_000 })

    // Verify Level 1 Ontology Blueprint view renders layers and node types
    await expect(
      page.getByRole('button', { name: /Level 1 · Ontology Blueprint/i })
    ).toBeVisible()

    // Switch to Level 2 Instance Graph view
    await page
      .getByRole('button', { name: /Level 2 · Instance Graph/i })
      .click()

    // Switch to Cookbooks Studio tab and verify 06 Second brain is Active Mode
    await page.getByRole('button', { name: /Cookbook Modes/i }).click()
    await expect(
      page.getByRole('heading', { name: 'Start from a working graph' })
    ).toBeVisible()
    await expect(page.getByText('Industry intel').first()).toBeVisible()
    await expect(page.getByText('Pharma intel').first()).toBeVisible()
    await expect(page.getByText('Biomed research').first()).toBeVisible()
    await expect(page.getByText('Second brain').first()).toBeVisible()

    // Switch to Models, Control & Omnigraph tab
    await page
      .getByRole('button', { name: /Models, Control & Omnigraph/i })
      .click()
    await expect(
      page.getByRole('heading', { name: 'Local Omnigraph Engine' })
    ).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'Models & User Control' })
    ).toBeVisible()

    // 3. Verify /dashboard/skills/boltz does NOT loop catalog detail/audit fetches
    let catalogFetchCount = 0
    page.on('request', req => {
      if (req.url().includes('/skills/catalog/')) {
        catalogFetchCount += 1
      }
    })
    await page.goto('/dashboard/skills/boltz')
    await expect(page.getByRole('heading', { name: '/boltz' })).toBeVisible({
      timeout: 15_000
    })
    await page.waitForTimeout(500)
    const countAfterLoad = catalogFetchCount
    await page.waitForTimeout(1000)
    expect(catalogFetchCount).toBe(countAfterLoad)
  })
})
