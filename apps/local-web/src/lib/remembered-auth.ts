import { normalizeBackendUrl } from '@/lib/backend-url'

export const REMEMBERED_AUTH_STORAGE_KEY = 'sandwalk.remembered-auth'

/** Match server `SESSION_REMEMBER_MAX_AGE` (30 days). */
const SESSION_REMEMBER_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000

type RememberedAuthEntry = {
  apiKey: string
  expiresAt: number
}

type RememberedAuthMap = Record<string, RememberedAuthEntry>

function readMap(): RememberedAuthMap {
  try {
    const raw = localStorage.getItem(REMEMBERED_AUTH_STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as RememberedAuthMap
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writeMap(map: RememberedAuthMap) {
  try {
    localStorage.setItem(REMEMBERED_AUTH_STORAGE_KEY, JSON.stringify(map))
  } catch {
    // Private mode / quota — ignore.
  }
}

/** Restore a non-expired remembered key for this backend, or undefined. */
export function readRememberedApiKey(backendUrl: string): string | undefined {
  const key = normalizeBackendUrl(backendUrl)
  const entry = readMap()[key]
  if (!entry?.apiKey || typeof entry.expiresAt !== 'number') return undefined
  if (Date.now() >= entry.expiresAt) {
    clearRememberedApiKey(key)
    return undefined
  }
  return entry.apiKey
}

/** Persist for ~30 days (matches server SESSION_REMEMBER_MAX_AGE). */
export function persistRememberedApiKey(backendUrl: string, apiKey: string) {
  const key = normalizeBackendUrl(backendUrl)
  const trimmed = apiKey.trim()
  if (!trimmed) return
  const map = readMap()
  map[key] = {
    apiKey: trimmed,
    expiresAt: Date.now() + SESSION_REMEMBER_MAX_AGE_MS
  }
  writeMap(map)
}

export function clearRememberedApiKey(backendUrl: string) {
  const key = normalizeBackendUrl(backendUrl)
  const map = readMap()
  if (!(key in map)) return
  delete map[key]
  writeMap(map)
}
