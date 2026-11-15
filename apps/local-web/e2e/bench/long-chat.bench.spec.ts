import { expect, type Page, test } from '@playwright/test'

import { E2EApi } from '../fixtures/api'
import { resolveE2EEnv } from '../fixtures/env'
import {
  archiveReport,
  type Measurement,
  recordMeasurement,
  startCollectors,
  stopCollectors
} from '../fixtures/perf'

const env = resolveE2EEnv()
const SUITE = 'longchat'
const TURNS = Number(process.env.SANDWALK_E2E_LONG_CHAT_TURNS || 150)
const CONFIG = { turns: TURNS, viewport: '1600x1000' }
const RUN_ID = process.env.SANDWALK_BENCH_RUN_ID ?? `${Date.now()}`
const START = 'bench-first-prompt'
const END = 'bench-last-answer'

/** What a research chat looks like: prose, a list, a code block, a table. */
function answer(turn: number, marker: string): string {
  return [
    `## Result ${turn}`,
    `The run finished and the **summary** for step ${turn} is below. ${marker}`,
    `- first finding for turn ${turn}\n- second finding with \`inline_code\`\n- third finding`,
    '```python\nimport numpy as np\n\ndef score(x):\n    return float(np.mean(x) * ' +
      turn +
      ')\n\nprint(score([1, 2, 3]))\n```',
    '| metric | value |\n|---|---|\n| rmsd | 1.2 |\n| plddt | 87.4 |\n| ptm | 0.81 |',
    'Next I would validate the top candidates against the held-out set before reporting.'
  ].join('\n\n')
}

function longHistory(sessionId: string) {
  const data = []
  for (let turn = 0; turn < TURNS; turn += 1) {
    const at = new Date(Date.UTC(2026, 0, 1, 0, turn)).toISOString()
    data.push({
      id: `bench_u${turn}`,
      sessionId,
      role: 'user',
      content: turn === 0 ? `${START} design a binder` : `follow-up question number ${turn}`,
      createdAt: at
    })
    data.push({
      id: `bench_a${turn}`,
      sessionId,
      role: 'assistant',
      content: answer(turn, turn === TURNS - 1 ? END : ''),
      createdAt: at
    })
  }
  return { data, feedback: {} }
}

/**
 * Opening a long chat. No model is involved: the chat is a real (empty)
 * session and its message list is served from a fixture, so the numbers
 * are render cost only.
 *
 *   longChatOpen     click in the sidebar → newest message on screen
 *   longChatSettled  click → the whole history is mounted
 *   longChatReopen   leave and come back → newest message on screen
 *
 * `longTask.maxMs` is the worst single freeze, `longTaskMs` the total.
 */
test.describe('long chat benchmarks', () => {
  const api = new E2EApi(env)
  let longId = ''
  let shortId = ''
  const longTitle = `[e2e] long chat ${RUN_ID}`
  const shortTitle = `[e2e] short chat ${RUN_ID}`

  const record = (m: Measurement) => {
    const latest = recordMeasurement(SUITE, m, CONFIG, RUN_ID)
    // eslint-disable-next-line no-console
    console.log(
      `  ${m.name.padEnd(18)} ${String(m.durationMs).padStart(6)}ms  longTasks=${m.longTasks} (${m.longTaskMs}ms, max ${m.counters['longTask.maxMs'] ?? 0}ms)  ` +
        ['render.TimelineItem', 'render.MessageEntry', 'render.ChatTranscript']
          .map(key => `${key}=${m.counters[key] ?? 0}`)
          .join(' ') +
        `\n  → ${latest}`
    )
  }

  test.beforeAll(async () => {
    longId = (await api.createSession(longTitle)).id
    shortId = (await api.createSession(shortTitle)).id
  })

  test.afterAll(async () => {
    archiveReport(SUITE)
    await Promise.allSettled([api.deleteSession(longId), api.deleteSession(shortId)])
  })

  async function boot(page: Page) {
    await page.route(`**/v1/sessions/${longId}/messages`, route =>
      route.request().method() === 'GET'
        ? route.fulfill({ json: longHistory(longId) })
        : route.fallback()
    )
    const storage: Record<string, string> = {
      'fastfold.backend.url': env.apiUrl,
      'fastfold.open-session-tabs-by-project': JSON.stringify({ __all__: [shortId] }),
      'fastfold.project-scope-id': '',
      'fastfold.sidebar-collapsed': 'false'
    }
    if (env.apiKey) {
      storage['sandwalk.remembered-auth'] = JSON.stringify({
        [env.apiUrl]: { apiKey: env.apiKey, expiresAt: Date.now() + 3_600_000 }
      })
    }
    await page.addInitScript(entries => {
      for (const [key, value] of Object.entries(entries)) {
        if (value === '') window.localStorage.removeItem(key)
        else window.localStorage.setItem(key, value)
      }
    }, storage)
    await page.goto(`/agents/${shortId}?perf=1`)
    await expect(row(page, longTitle)).toBeVisible({ timeout: 30_000 })
    // Let bootstrap fetches and first paints finish before measuring.
    await page.waitForTimeout(1500)
  }

  const row = (page: Page, title: string) =>
    page.locator('aside button', { hasText: title }).first()
  const transcript = (page: Page) => page.locator('[data-transcript]')

  async function timed(
    page: Page,
    name: string,
    action: () => Promise<void>
  ): Promise<Measurement> {
    await startCollectors(page)
    const started = Date.now()
    await action()
    const durationMs = Date.now() - started
    const collected = await stopCollectors(page)
    return { name, durationMs, ...collected, fps: 0 }
  }

  test('open: newest message on screen', async ({ page }) => {
    await boot(page)
    record(
      await timed(page, 'longChatOpen', async () => {
        await row(page, longTitle).click()
        await expect(transcript(page).getByText(END)).toBeVisible({ timeout: 60_000 })
      })
    )
  })

  test('settled: whole history mounted', async ({ page }) => {
    await boot(page)
    record(
      await timed(page, 'longChatSettled', async () => {
        await row(page, longTitle).click()
        await expect(transcript(page).getByText(START)).toBeAttached({ timeout: 60_000 })
        // Two frames with nothing left to mount.
        await page.evaluate(
          () =>
            new Promise<void>(resolve =>
              requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
            )
        )
      })
    )
    // The chat must end up at the newest message, not wherever history grew.
    await expect(transcript(page).getByText(END)).toBeInViewport()
  })

  test('reopen: leave and come back', async ({ page }) => {
    await boot(page)
    await row(page, longTitle).click()
    await expect(transcript(page).getByText(START)).toBeAttached({ timeout: 60_000 })
    await page.waitForTimeout(500)
    await row(page, shortTitle).click()
    await expect(transcript(page).getByText(END)).toHaveCount(0)
    await page.waitForTimeout(500)
    record(
      await timed(page, 'longChatReopen', async () => {
        await row(page, longTitle).click()
        await expect(transcript(page).getByText(END)).toBeVisible({ timeout: 60_000 })
      })
    )
  })
})
