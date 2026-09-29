import { expect, type Page } from '@playwright/test'

import { E2EApi } from './api'
import type { E2EEnv } from './env'

export type GridFixture = {
  groupId: string
  chatIds: string[]
  terminalIds: string[]
  /** localStorage entries that make the SPA boot into the group. */
  storage: Record<string, string>
  /** Rows × columns to lay the panes out in (default: one row). */
  layout: { rows: number; cols: number } | null
  /** Remove everything this seed created on the API. */
  cleanup: () => Promise<void>
}

/** Parse "4x2" → { rows: 4, cols: 2 }. */
export function parseGridSpec(spec: string): { rows: number; cols: number } {
  const match = /^(\d+)\s*x\s*(\d+)$/i.exec(spec.trim())
  if (!match) throw new Error(`bad grid spec "${spec}" (expected RxC, e.g. 4x2)`)
  return { rows: Number(match[1]), cols: Number(match[2]) }
}

export type SeededGrid = GridFixture

const E2E_TITLE_PREFIX = '[e2e]'

function randomId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`
}

/**
 * Create `chats` sessions and `terminals` terminals through the API and
 * build the localStorage payload that boots the SPA into a split group
 * containing all of them. Groups are client-side state, so we write the
 * same keys `app-storage.ts` reads (`fastfold.tab-groups`, open tabs, auth).
 * Pair with `openGrid(page, fixture)`; `seedGrid` does both.
 */
export async function createGridFixture(
  env: E2EEnv,
  options: {
    chats: number
    terminals: number
    layout?: { rows: number; cols: number } | null
    /** Provider/model for the chats (live bench); default = server config. */
    provider?: string | null
    model?: string | null
  }
): Promise<GridFixture> {
  const api = new E2EApi(env)
  if (!(await api.health())) {
    throw new Error(
      `Sandwalk API is not reachable at ${env.apiUrl}. Start it with: cd cli && .venv/bin/sandwalk serve --host 127.0.0.1 --port 8787`
    )
  }

  const chats = []
  for (let i = 0; i < options.chats; i += 1) {
    chats.push(
      await api.createSession(`${E2E_TITLE_PREFIX} chat ${i + 1}`, {
        provider: options.provider,
        model: options.model
      })
    )
  }
  const terminals = []
  for (let i = 0; i < options.terminals; i += 1) {
    terminals.push(await api.createTerminal(`${E2E_TITLE_PREFIX} term ${i + 1}`))
  }
  const chatIds = chats.map(s => s.id)
  const terminalIds = terminals.map(t => t.id)
  const itemIds = [...chatIds, ...terminalIds]
  const groupId = randomId('grp')

  const group = {
    id: groupId,
    name: `${E2E_TITLE_PREFIX} grid ${itemIds.length}`,
    color: null,
    pinned: false,
    itemIds,
    activeChatId: chatIds[0] ?? terminalIds[0]
  }

  const storage: Record<string, string> = {
    'fastfold.backend.url': env.apiUrl,
    'fastfold.tab-groups': JSON.stringify([group]),
    'fastfold.open-session-tabs-by-project': JSON.stringify({ __all__: [groupId] }),
    'fastfold.project-scope-id': '',
    // Skip first-run flows and keep the sidebar predictable.
    'fastfold.sidebar-collapsed': 'false'
  }
  if (env.apiKey) {
    storage['sandwalk.remembered-auth'] = JSON.stringify({
      [env.apiUrl]: { apiKey: env.apiKey, expiresAt: Date.now() + 60 * 60 * 1000 }
    })
  }

  return {
    groupId,
    chatIds,
    terminalIds,
    storage,
    layout: options.layout ?? null,
    cleanup: async () => {
      await Promise.allSettled([
        ...chatIds.map(id => api.deleteSession(id)),
        ...terminalIds.map(id => api.deleteTerminal(id))
      ])
    }
  }
}

/** Boot `page` into the seeded group and wait for every pane to mount. */
export async function openGrid(page: Page, fixture: GridFixture): Promise<void> {
  await page.addInitScript(
    ({ entries, layout, itemIds }) => {
      for (const [key, value] of Object.entries(entries)) {
        if (value === '') window.localStorage.removeItem(key)
        else window.localStorage.setItem(key, value)
      }
      if (!layout) return
      // Lay the panes out as rows × cols. The tree is keyed by the same
      // monitor fingerprint `monitor-fingerprint.ts` computes in-page
      // (screen size × DPR), so it must be built here, not in Node.
      const fp = `${Math.round(window.screen.width)}x${Math.round(window.screen.height)}@${Math.round(window.devicePixelRatio || 1)}`
      const leaf = (id: string) =>
        id.startsWith('term_') ? { type: 'terminal', terminalId: id } : { type: 'chat', chatId: id }
      const rows: unknown[] = []
      for (let r = 0; r < layout.rows; r += 1) {
        const slice = itemIds.slice(r * layout.cols, (r + 1) * layout.cols)
        if (slice.length === 0) break
        rows.push(
          slice.length === 1
            ? leaf(slice[0])
            : {
                type: 'branch',
                direction: 'horizontal',
                ratios: slice.map(() => 1 / slice.length),
                children: slice.map(leaf)
              }
        )
      }
      const tree =
        rows.length === 1
          ? rows[0]
          : { type: 'branch', direction: 'vertical', ratios: rows.map(() => 1 / rows.length), children: rows }
      const raw = window.localStorage.getItem('fastfold.tab-groups')
      if (!raw) return
      const groups = JSON.parse(raw) as Array<{ layout?: unknown }>
      for (const group of groups) group.layout = { perMonitor: { [fp]: tree } }
      window.localStorage.setItem('fastfold.tab-groups', JSON.stringify(groups))
    },
    { entries: fixture.storage, layout: fixture.layout, itemIds: [...fixture.chatIds, ...fixture.terminalIds] }
  )
  await page.goto(`/agents/${fixture.groupId}?perf=1`)
  await expect(page.locator('[data-pane-id]')).toHaveCount(
    fixture.chatIds.length + fixture.terminalIds.length,
    { timeout: 30_000 }
  )
}

/** Create the fixture and open it on `page` in one step. */
export async function seedGrid(
  page: Page,
  env: E2EEnv,
  options: { chats: number; terminals: number; layout?: { rows: number; cols: number } | null }
): Promise<SeededGrid> {
  const fixture = await createGridFixture(env, options)
  await openGrid(page, fixture)
  return fixture
}

/**
 * Wait until every terminal in the grid has an attached, positioned xterm
 * and its shell has printed a prompt (PTY WebSocket connected).
 */
export async function waitForTerminals(page: Page, terminalIds: string[]): Promise<void> {
  for (const id of terminalIds) {
    const host = page.locator(`[data-terminal-portal-host="${id}"]`)
    await expect(host).toBeVisible({ timeout: 30_000 })
    await expect(host.locator('.xterm-screen')).toBeVisible({ timeout: 30_000 })
    await expect
      .poll(async () => (await readTerminalText(page, id)).trim().length, {
        timeout: 30_000,
        message: `shell prompt for ${id}`
      })
      .toBeGreaterThan(0)
  }
  // A restored terminal paints its snapshot before the PTY socket is up;
  // wait for every socket so typed input reaches the shell.
  await expect
    .poll(
      () => page.evaluate(() => window.__sandwalkPerf?.counters['terminal.wsOpen'] ?? 0),
      { timeout: 30_000, message: 'pty websockets open' }
    )
    .toBeGreaterThanOrEqual(terminalIds.length)
}

/** Focus a terminal pane by clicking its xterm. */
export async function focusTerminal(page: Page, terminalId: string): Promise<void> {
  const host = page.locator(`[data-terminal-portal-host="${terminalId}"]`)
  await host.locator('.xterm-screen').click()
  await page.waitForTimeout(150)
}

/**
 * Give a pane focus the way a user would. Terminal panes are covered by
 * their fixed-position portal host, so the click must land on the xterm;
 * chat panes take a click on their header strip.
 */
export async function focusPane(page: Page, paneId: string): Promise<void> {
  const pane = page.locator(`[data-pane-id="${paneId}"]`)
  const kind = await pane.getAttribute('data-pane-kind')
  if (kind === 'terminal') {
    await focusTerminal(page, paneId)
    return
  }
  // Below the 52px header: at 8+ panes the header is so narrow that its
  // action icons sit where the title normally is, and a header click
  // would toggle Files / Preview instead of just focusing.
  await pane.click({ position: { x: 24, y: 80 } })
}

/**
 * A scrollable surface that is NOT a terminal: the first chat transcript
 * viewport if the chat has messages, else the sidebar session list.
 */
export async function nonTerminalScroller(page: Page, chatId: string): Promise<string> {
  const transcript = `[data-pane-id="${chatId}"] [data-transcript] [data-radix-scroll-area-viewport]`
  if ((await page.locator(transcript).count()) > 0) return transcript
  const paneViewport = `[data-pane-id="${chatId}"] [data-radix-scroll-area-viewport]`
  if ((await page.locator(paneViewport).count()) > 0) return paneViewport
  return 'aside [data-radix-scroll-area-viewport]'
}

export type TerminalBufferState = { length: number; cols: number; rows: number; lastLines: string[] }

/** Read xterm buffer state through the dev perf probe. */
export async function readTerminalBuffer(
  page: Page,
  terminalId: string,
  tailLines = 5
): Promise<TerminalBufferState> {
  return page.evaluate(
    ([id, tail]) => {
      const probe = window.__sandwalkPerf
      const term = probe?.terminals.get(id as string) as
        | {
            cols: number
            rows: number
            buffer: { active: { length: number; getLine: (i: number) => { translateToString: (trim?: boolean) => string } | undefined } }
          }
        | undefined
      if (!term) throw new Error(`terminal ${id} is not tracked by the perf probe`)
      const buf = term.buffer.active
      const lines: string[] = []
      for (let i = Math.max(0, buf.length - (tail as number)); i < buf.length; i += 1) {
        lines.push(buf.getLine(i)?.translateToString(true) ?? '')
      }
      return { length: buf.length, cols: term.cols, rows: term.rows, lastLines: lines }
    },
    [terminalId, tailLines] as const
  )
}

/**
 * All non-empty logical lines currently in the buffer. Rows that xterm
 * soft-wrapped (`isWrapped`) are stitched back onto their logical line so
 * assertions do not depend on the pane width.
 */
export async function readTerminalText(page: Page, terminalId: string): Promise<string> {
  return page.evaluate(id => {
    type Line = { isWrapped: boolean; translateToString: (trim?: boolean) => string }
    const term = window.__sandwalkPerf?.terminals.get(id) as
      | { buffer: { active: { length: number; getLine: (i: number) => Line | undefined } } }
      | undefined
    if (!term) return ''
    const buf = term.buffer.active
    const out: string[] = []
    for (let i = 0; i < buf.length; i += 1) {
      const line = buf.getLine(i)
      if (!line) continue
      // Wrapped continuation rows keep their trailing spaces meaningful
      // only when more text follows; trim the logical line at the end.
      const text = line.translateToString(false)
      if (line.isWrapped && out.length > 0) {
        out[out.length - 1] += text
      } else {
        out.push(text)
      }
    }
    return out
      .map(l => l.replace(/\s+$/, ''))
      .filter(l => l.length > 0)
      .join('\n')
  }, terminalId)
}
