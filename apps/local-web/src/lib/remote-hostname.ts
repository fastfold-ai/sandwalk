import { isLocalBackendUrl, normalizeBackendUrl } from '@/lib/backend-url'

const cache = new Map<string, string>()

function shortHostname(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return ''
  const noLocal = trimmed.endsWith('.local')
    ? trimmed.slice(0, -'.local'.length)
    : trimmed
  return noLocal.split('.')[0] || noLocal
}

/** Cached friendly hostname for a backend URL (from `/v1/discover` or LAN scan). */
export function readCachedRemoteHostname(backendUrl: string): string | null {
  const key = normalizeBackendUrl(backendUrl)
  const hit = cache.get(key)
  return hit || null
}

export function rememberRemoteHostname(backendUrl: string, hostname: string | null | undefined) {
  const key = normalizeBackendUrl(backendUrl)
  const short = shortHostname(hostname || '')
  if (!short || isLocalBackendUrl(key)) return
  try {
    const ip = new URL(key).hostname
    if (short.toLowerCase() === ip.toLowerCase()) return
  } catch {
    // ignore
  }
  cache.set(key, short)
}

/** Fetch `/v1/discover` (auth-exempt) and cache the hostname. */
export async function resolveRemoteHostname(
  backendUrl: string
): Promise<string | null> {
  const key = normalizeBackendUrl(backendUrl)
  if (isLocalBackendUrl(key)) return null
  const cached = cache.get(key)
  if (cached) return cached
  try {
    const res = await fetch(`${key}/v1/discover`, {
      method: 'GET',
      headers: { Accept: 'application/json' }
    })
    if (!res.ok) return null
    const body = (await res.json()) as { hostname?: string }
    rememberRemoteHostname(key, body.hostname)
    return cache.get(key) || null
  } catch {
    return null
  }
}

/**
 * Dock suffix: prefer hostname (`Julios-Mac-mini`).
 * Falls back to `host:port` when discover is unavailable.
 */
export function remoteDockSuffix(
  backendUrl: string,
  hostname?: string | null
): string | null {
  if (isLocalBackendUrl(backendUrl)) return null
  try {
    const parsed = new URL(normalizeBackendUrl(backendUrl))
    const hostport = parsed.port
      ? `${parsed.hostname}:${parsed.port}`
      : parsed.hostname
    const short =
      shortHostname(hostname || '') ||
      readCachedRemoteHostname(backendUrl) ||
      ''
    if (short && short.toLowerCase() !== parsed.hostname.toLowerCase()) {
      return short
    }
    return hostport || null
  } catch {
    return null
  }
}
