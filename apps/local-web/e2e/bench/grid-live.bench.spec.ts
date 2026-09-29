import { expect, test } from '@playwright/test'

import { E2EApi } from '../fixtures/api'
import { resolveE2EEnv } from '../fixtures/env'
import { archiveReport, measure, type Measurement, recordMeasurement } from '../fixtures/perf'
import { createGridFixture, type GridFixture, openGrid, parseGridSpec } from '../fixtures/seed'

const env = resolveE2EEnv()
const SUITE = 'grid-live'
const RUN_ID = process.env.SANDWALK_BENCH_RUN_ID ?? `${Date.now()}`
/** Token the agent must echo; counted twice in a pane (user + assistant). */
const REPLY_TOKEN = 'ZQX7'
const PROMPT = `Reply with exactly this token and nothing else: ${REPLY_TOKEN}`

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  return Math.round(sorted[Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length))])
}

/**
 * Real-usage benchmark: open an R×C grid of chats, send one message to
 * every pane at once, and measure — per agent — API POST latency, time
 * until its reply is visible in its pane, and time until the run is idle,
 * while the UI counters capture the render cost of N concurrent streams.
 *
 * Costs tokens (one tiny prompt per pane with the configured model), so it
 * only runs with SANDWALK_E2E_LIVE=1. Shapes: SANDWALK_E2E_GRIDS=2x2,4x2,4x4.
 * Pin the model with SANDWALK_E2E_PROVIDER / SANDWALK_E2E_MODEL (a model
 * whose classifier refuses the agent prompt — e.g. Fable 5.x today — shows
 * up as `live.failures` with "stop_reason=refusal" in the transcript).
 */
test.describe('live agent grid', () => {
  test.skip(!env.live, 'set SANDWALK_E2E_LIVE=1 to send real messages')

  test.afterAll(() => {
    archiveReport(SUITE)
  })

  test('POST /messages latency: idle vs 4 concurrent (no UI)', async () => {
    test.setTimeout(120_000)
    const api = new E2EApi(env)
    const ids: string[] = []
    for (let i = 0; i < 5; i += 1) {
      ids.push(
        (await api.createSession(`[e2e] post-latency ${i + 1}`, { provider: env.liveProvider, model: env.liveModel })).id
      )
    }
    try {
      const idle = (await api.sendMessage(ids[0], PROMPT)).latencyMs
      // Let that run's build settle so the concurrent batch starts clean.
      await new Promise(r => setTimeout(r, 6_000))
      const t0 = Date.now()
      const batch = await Promise.all(ids.slice(1).map(id => api.sendMessage(id, PROMPT)))
      const wall = Date.now() - t0
      const m: Measurement = {
        name: 'postLatency',
        durationMs: wall,
        longTasks: 0,
        longTaskMs: 0,
        frames: 0,
        fps: 0,
        counters: {
          'live.postIdleMs': idle,
          'live.postConcurrent4P50Ms': percentile(batch.map(b => b.latencyMs), 50),
          'live.postConcurrent4MaxMs': Math.max(...batch.map(b => b.latencyMs)),
          'live.apiHealthP50Ms': await api.healthLatencyMs()
        }
      }
      recordMeasurement(SUITE, m, { grids: env.liveGrids }, RUN_ID)
      // eslint-disable-next-line no-console
      console.log(`  postLatency idle=${idle}ms  4-concurrent p50/max=${m.counters['live.postConcurrent4P50Ms']}/${m.counters['live.postConcurrent4MaxMs']}ms  wall=${wall}ms`)
      // Wait for the runs to finish before deleting the sessions.
      const deadline = Date.now() + 60_000
      while (Date.now() < deadline) {
        const statuses = await Promise.all(ids.map(id => api.getSession(id).then(s => s.status).catch(() => 'idle')))
        if (statuses.every(s => s === 'idle')) break
        await new Promise(r => setTimeout(r, 500))
      }
    } finally {
      await Promise.allSettled(ids.map(id => api.deleteSession(id)))
    }
  })

  for (const spec of env.liveGrids) {
    const { rows, cols } = parseGridSpec(spec)
    const panes = rows * cols

    test(`${spec}: ${panes} agents reply concurrently`, async ({ page }) => {
      test.setTimeout(env.liveTimeoutMs + 60_000)
      const api = new E2EApi(env)
      const healthP50 = await api.healthLatencyMs()
      let grid: GridFixture | null = null
      try {
        grid = await createGridFixture(env, {
          chats: panes,
          terminals: 0,
          layout: { rows, cols },
          provider: env.liveProvider,
          model: env.liveModel
        })
        await openGrid(page, grid)
        const chatIds = grid.chatIds

        const postLatency: number[] = []
        const firstVisible: number[] = []
        const completed: number[] = []
        let failures = 0
        let stillRunning = 0
        let emptyReply = 0
        let replyNotVisible = 0

        const m: Measurement = await measure(page, `live-${spec}`, async () => {
          const t0 = Date.now()
          // Fire every message at once (what a user with N panes streaming sees).
          const sends = await Promise.allSettled(chatIds.map(id => api.sendMessage(id, PROMPT)))
          for (const s of sends) {
            if (s.status === 'fulfilled') postLatency.push(s.value.latencyMs)
            else failures += 1
          }

          const pending = new Set(chatIds)
          const seen = new Set<string>()
          const deadline = t0 + env.liveTimeoutMs
          while (pending.size > 0 && Date.now() < deadline) {
            // Reply visible in the pane? (token appears for user + assistant)
            const counts = await page.evaluate(
              ({ ids, token }) =>
                ids.map(id => {
                  const text = document.querySelector(`[data-pane-id="${id}"]`)?.textContent ?? ''
                  return text.split(token).length - 1
                }),
              { ids: chatIds, token: REPLY_TOKEN }
            )
            chatIds.forEach((id, i) => {
              if (!seen.has(id) && counts[i] >= 2) {
                seen.add(id)
                firstVisible.push(Date.now() - t0)
              }
            })
            // Run finished on the server?
            const statuses = await Promise.all(
              [...pending].map(async id => {
                try {
                  const session = await api.getSession(id)
                  return { id, status: session.status }
                } catch {
                  return { id, status: 'error' }
                }
              })
            )
            for (const { id, status } of statuses) {
              if (status === 'idle' && seen.has(id)) {
                pending.delete(id)
                completed.push(Date.now() - t0)
              } else if (status === 'error') {
                pending.delete(id)
                failures += 1
              }
            }
            await page.waitForTimeout(250)
          }
          // Classify what is left so a failure points at the right layer:
          // server never finished, model replied empty, or the UI never
          // painted a reply that the API has.
          for (const id of pending) {
            failures += 1
            try {
              const status = (await api.getSession(id)).status
              if (status !== 'idle') {
                stillRunning += 1
                continue
              }
              const reply = (await api.listMessages(id)).filter(msg => msg.role === 'assistant').pop()
              const text = typeof reply?.content === 'string' ? reply.content : JSON.stringify(reply?.content ?? '')
              if (!reply || !text.includes(REPLY_TOKEN)) emptyReply += 1
              else if (!seen.has(id)) replyNotVisible += 1
            } catch {
              stillRunning += 1
            }
          }
        })

        m.counters['live.panes'] = panes
        m.counters['live.failures'] = failures
        m.counters['live.stillRunning'] = stillRunning
        m.counters['live.emptyReply'] = emptyReply
        m.counters['live.replyNotVisible'] = replyNotVisible
        m.counters['live.apiHealthP50Ms'] = healthP50
        m.counters['live.postLatencyP50Ms'] = percentile(postLatency, 50)
        m.counters['live.postLatencyP95Ms'] = percentile(postLatency, 95)
        m.counters['live.firstVisibleP50Ms'] = percentile(firstVisible, 50)
        m.counters['live.firstVisibleP95Ms'] = percentile(firstVisible, 95)
        m.counters['live.completeP50Ms'] = percentile(completed, 50)
        m.counters['live.completeP95Ms'] = percentile(completed, 95)
        m.counters['live.completeMaxMs'] = completed.length ? Math.max(...completed) : 0
        const latest = recordMeasurement(
          SUITE,
          m,
          {
            grids: env.liveGrids,
            viewport: '1600x1000',
            provider: env.liveProvider ?? 'server-default',
            model: env.liveModel ?? 'server-default'
          },
          RUN_ID
        )
        // eslint-disable-next-line no-console
        console.log(
          `  ${spec.padEnd(6)} panes=${panes} fail=${failures} (running=${stillRunning} empty=${emptyReply} notVisible=${replyNotVisible})  post p50/p95=${m.counters['live.postLatencyP50Ms']}/${m.counters['live.postLatencyP95Ms']}ms  ` +
            `first-visible p50/p95=${m.counters['live.firstVisibleP50Ms']}/${m.counters['live.firstVisibleP95Ms']}ms  ` +
            `complete p50/p95/max=${m.counters['live.completeP50Ms']}/${m.counters['live.completeP95Ms']}/${m.counters['live.completeMaxMs']}ms  ` +
            `longTasks=${m.longTasks} (${m.longTaskMs}ms) fps=${m.fps} render.App=${m.counters['render.App'] ?? 0}\n  → ${latest}`
        )
        expect(failures, 'agents that never replied').toBe(0)
      } finally {
        await grid?.cleanup()
      }
    })
  }
})
