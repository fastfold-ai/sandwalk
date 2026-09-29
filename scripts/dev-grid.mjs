#!/usr/bin/env node
/* global process, console, fetch */
/**
 * Open an R×C split of fresh chats in the running Sandwalk UI and give each
 * one something to say — for eyeballing the grid, terminals, and streaming.
 *
 *   node scripts/dev-grid.mjs 4x4            # 16 chats, one random prompt each
 *   node scripts/dev-grid.mjs 2x3 --quiet    # no messages, just the grid
 *   node scripts/dev-grid.mjs 3x3 --model claude-sonnet-5 --provider anthropic
 *   node scripts/dev-grid.mjs --cleanup      # delete every "[grid]" chat
 *
 * Needs the API (scripts/dev-api.sh) and the UI (scripts/dev-ui.sh) running.
 * The UI receives a `ui.command` over its event stream and builds the group
 * itself, so this works for the Tauri window and any open browser tab alike.
 */
import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const args = process.argv.slice(2)
const flag = name => {
  const i = args.indexOf(`--${name}`)
  return i >= 0 ? args[i + 1] : undefined
}
const has = name => args.includes(`--${name}`)
const spec = args.find(a => /^\d+x\d+$/i.test(a)) ?? '2x2'
const [rows, cols] = spec.toLowerCase().split('x').map(Number)
const API = (process.env.SANDWALK_API_URL || 'http://127.0.0.1:8787').replace(/\/+$/, '')

function apiKey() {
  if (process.env.SANDWALK_API_KEY) return process.env.SANDWALK_API_KEY.trim()
  const candidates = [
    process.env.SANDWALK_SETTINGS_PATH,
    join(homedir(), 'Library', 'Application Support', 'Sandwalk', 'settings.json'),
    join(homedir(), '.config', 'sandwalk', 'settings.json')
  ].filter(Boolean)
  for (const path of candidates) {
    if (!existsSync(path)) continue
    try {
      const parsed = JSON.parse(readFileSync(path, 'utf8'))
      if (parsed.auth?.auth_enabled === false) return null
      if (parsed.auth?.api_key) return String(parsed.auth.api_key).trim()
    } catch {
      /* next */
    }
  }
  return null
}

const key = apiKey()
const headers = { 'content-type': 'application/json', ...(key ? { Authorization: `Bearer ${key}` } : {}) }

async function api(path, init = {}) {
  const res = await fetch(`${API}/v1${path}`, { ...init, headers: { ...headers, ...(init.headers || {}) } })
  if (!res.ok) throw new Error(`API ${res.status} ${init.method || 'GET'} ${path}: ${(await res.text()).slice(0, 200)}`)
  const text = await res.text()
  return text ? JSON.parse(text) : undefined
}

const PROMPTS = [
  'In one sentence, what is a protein kinase?',
  'Give me a haiku about Python packaging.',
  'What is the difference between RNA-seq and scRNA-seq? Two sentences max.',
  'Name three common docking tools and one line about each.',
  'Explain SIGWINCH to a five-year-old.',
  'What does ADMET stand for? Just expand the acronym.',
  'Suggest a name for a lab mascot that is a capybara.',
  'Reply with a single random emoji and its Unicode name.',
  'What is 17 * 23? Answer with just the number.',
  'One sentence: why do terminals emit OSC 133 sequences?',
  'Write a two-line limerick about a benchmark.',
  'Which is heavier, a mole of carbon or a mole of oxygen? One line.',
  'Give a fun fact about tardigrades in under 20 words.',
  'What is the capital of Uruguay? One word.',
  'Describe a split-pane UI in exactly five words.',
  'Say hello in three languages, comma separated.'
]

async function cleanup() {
  const sessions = await api('/sessions')
  const rows = Array.isArray(sessions) ? sessions : sessions.data ?? []
  const mine = rows.filter(s => String(s.title || '').startsWith('[grid]'))
  await Promise.allSettled(mine.map(s => api(`/sessions/${encodeURIComponent(s.id)}`, { method: 'DELETE' })))
  console.log(`deleted ${mine.length} "[grid]" chat(s)`)
}

async function main() {
  try {
    await api('/health')
  } catch (err) {
    console.error(`no API at ${API} — start scripts/dev-api.sh\n${err.message}`)
    process.exit(1)
  }
  if (has('cleanup')) return cleanup()
  if (!rows || !cols) {
    console.error('usage: node scripts/dev-grid.mjs RxC [--quiet] [--provider p --model m] | --cleanup')
    process.exit(2)
  }
  const n = rows * cols
  const provider = flag('provider')
  const model = flag('model')
  const ids = []
  for (let i = 0; i < n; i += 1) {
    const r = Math.floor(i / cols) + 1
    const c = (i % cols) + 1
    const s = await api('/sessions', {
      method: 'POST',
      body: JSON.stringify({
        title: `[grid] r${r}c${c}`,
        workspacePath: null,
        projectId: null,
        clientSurface: 'ui',
        ...(provider ? { provider } : {}),
        ...(model ? { model } : {})
      })
    })
    ids.push(s.id)
  }
  console.log(`created ${n} chats`)

  await api('/ui/commands', {
    method: 'POST',
    body: JSON.stringify({ action: 'open_split', sessionIds: ids, layout: { rows, cols } })
  })
  console.log(`asked the UI to open a ${rows}x${cols} split`)

  if (has('quiet')) return
  // Small stagger so the panes are mounted before replies start streaming.
  await new Promise(r => setTimeout(r, 1200))
  const sends = ids.map((id, i) =>
    api(`/sessions/${encodeURIComponent(id)}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content: PROMPTS[(i + Math.floor(Math.random() * PROMPTS.length)) % PROMPTS.length] })
    })
  )
  const results = await Promise.allSettled(sends)
  const ok = results.filter(r => r.status === 'fulfilled').length
  console.log(`sent ${ok}/${n} messages — watch them stream in the grid. Cleanup: node scripts/dev-grid.mjs --cleanup`)
}

main().catch(err => {
  console.error(err.message)
  process.exit(1)
})
