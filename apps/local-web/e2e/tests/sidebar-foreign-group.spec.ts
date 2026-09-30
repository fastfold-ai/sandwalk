/**
 * A split group whose chats are missing from the global sessions list
 * (bench-sourced here; another project's chats in a scoped view) used to
 * leave the sidebar for one frame on every click: the list refresh dropped
 * the hydrated "foreign" chats and the foreign fetch re-added them a frame
 * later. Counts DOM removals of the group row while clicking around.
 *
 * Needs the `sqlite3` CLI to flag the chats as bench (there is no API for
 * that); skipped when it is not installed.
 */
import { execFileSync } from 'node:child_process'
import { homedir } from 'node:os'
import { join } from 'node:path'

import { expect, test } from '@playwright/test'

import { E2EApi } from '../fixtures/api'
import { resolveE2EEnv } from '../fixtures/env'

const env = resolveE2EEnv()

function hasSqlite(): boolean {
  try {
    execFileSync('sqlite3', ['-version'], { stdio: 'ignore' })
    return true
  } catch {
    return false
  }
}

function markBench(ids: string[]) {
  const db = join(homedir(), '.sandwalk', 'agent-server.db')
  const list = ids.map(id => `'${id}'`).join(',')
  execFileSync('sqlite3', [db, `UPDATE sessions SET source='bench' WHERE id IN (${list});`])
}

test('a group of foreign (bench) chats stays in the sidebar across clicks', async ({ page }) => {
  test.skip(!hasSqlite(), 'needs the sqlite3 CLI to mark chats as bench')
  const api = new E2EApi(env)
  const mk = async (t: string) => (await api.createSession(t)).id
  const foreign = [await mk('[probe] f1'), await mk('[probe] f2')]
  const normal = [await mk('[probe] n1'), await mk('[probe] n2')]
  const solo = await mk('[probe] solo')
  markBench(foreign)
  const gF = `grp_${Math.random().toString(36).slice(2, 10)}`
  const gN = `grp_${Math.random().toString(36).slice(2, 10)}`
  const groups = [
    { id: gF, name: '[probe] GF', color: null, pinned: false, itemIds: foreign, activeChatId: foreign[0] },
    { id: gN, name: '[probe] GN', color: null, pinned: false, itemIds: normal, activeChatId: normal[0] }
  ]
  const storage: Record<string, string> = {
    'fastfold.backend.url': env.apiUrl,
    'fastfold.tab-groups': JSON.stringify(groups),
    'fastfold.open-session-tabs-by-project': JSON.stringify({ __all__: [gF, gN, solo] }),
    'fastfold.project-scope-id': '',
    'fastfold.sidebar-collapsed': 'false'
  }
  if (env.apiKey) {
    storage['sandwalk.remembered-auth'] = JSON.stringify({
      [env.apiUrl]: { apiKey: env.apiKey, expiresAt: Date.now() + 3_600_000 }
    })
  }
  await page.addInitScript(entries => {
    for (const [k, v] of Object.entries(entries)) window.localStorage.setItem(k, v)
  }, storage)
  await page.goto(`/agents/${gN}?perf=1`)
  await expect(page.locator('[data-pane-id]')).toHaveCount(2, { timeout: 30_000 })
  const sidebar = page.locator('[data-radix-scroll-area-viewport]').first()
  await expect(sidebar.locator('button', { hasText: '[probe] GF' })).toBeVisible({ timeout: 15_000 })

  // Count every removal of the GF row from the DOM.
  await page.evaluate(() => {
    const log: string[] = []
    ;(window as unknown as { __gone: string[] }).__gone = log
    new MutationObserver(muts => {
      for (const m of muts) {
        for (const n of Array.from(m.removedNodes)) {
          if (n instanceof HTMLElement && /\[probe\] GF/.test(n.textContent || '')) log.push('GF removed')
        }
      }
    }).observe(document.body, { subtree: true, childList: true })
  })

  const rowByText = (t: string) => sidebar.locator('button', { hasText: t }).first()
  for (const t of ['[probe] solo', '[probe] GN', '[probe] solo', '[probe] GN', '[probe] solo']) {
    await rowByText(t).click()
    await page.waitForTimeout(600)
  }
  const gone = await page.evaluate(() => (window as unknown as { __gone: string[] }).__gone)
  await Promise.allSettled([...foreign, ...normal, solo].map(id => api.deleteSession(id)))
  expect(gone, 'foreign group row was removed from the sidebar').toEqual([])
})
