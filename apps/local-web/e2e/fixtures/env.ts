import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

export type E2EEnv = {
  webUrl: string
  webPort: number
  apiUrl: string
  apiKey: string | null
  /** Grid size for benchmarks (chats). */
  benchPanes: number
  /** Terminals to add to the bench grid. */
  benchTerminals: number
}

function settingsPathCandidates(): string[] {
  const out: string[] = []
  if (process.env.SANDWALK_SETTINGS_PATH) out.push(process.env.SANDWALK_SETTINGS_PATH)
  const home = homedir()
  out.push(join(home, 'Library', 'Application Support', 'Sandwalk', 'settings.json'))
  out.push(join(home, '.config', 'sandwalk', 'settings.json'))
  return out
}

/** API key: env first, then the Sandwalk auth settings file (never logged). */
export function resolveApiKey(): string | null {
  const fromEnv = (process.env.SANDWALK_API_KEY || '').trim()
  if (fromEnv) return fromEnv
  for (const path of settingsPathCandidates()) {
    if (!existsSync(path)) continue
    try {
      const parsed = JSON.parse(readFileSync(path, 'utf8')) as {
        auth?: { api_key?: string; auth_enabled?: boolean }
      }
      if (parsed.auth?.auth_enabled === false) return null
      const key = (parsed.auth?.api_key || '').trim()
      if (key) return key
    } catch {
      // fall through to the next candidate
    }
  }
  return null
}

export function resolveE2EEnv(): E2EEnv {
  const webUrl = (process.env.SANDWALK_WEB_URL || 'http://127.0.0.1:1420').replace(/\/+$/, '')
  const webPort = Number(new URL(webUrl).port || 80)
  const apiUrl = (process.env.SANDWALK_API_URL || 'http://127.0.0.1:8787').replace(/\/+$/, '')
  return {
    webUrl,
    webPort,
    apiUrl,
    apiKey: resolveApiKey(),
    benchPanes: Number(process.env.SANDWALK_E2E_PANES || 6),
    benchTerminals: Number(process.env.SANDWALK_E2E_TERMINALS || 2)
  }
}
