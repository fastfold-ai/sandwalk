import { isLocalBackendUrl, normalizeBackendUrl } from '@/lib/backend-url'

const hostnameCache = new Map<string, string>()
const platformCache = new Map<string, string>()

const PLATFORM_STORAGE_KEY = 'sandwalk.remote-platforms'

function shortHostname(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return ''
  const noLocal = trimmed.endsWith('.local')
    ? trimmed.slice(0, -'.local'.length)
    : trimmed
  return noLocal.split('.')[0] || noLocal
}

function loadPlatformStorage() {
  if (platformCache.size > 0) return
  try {
    const raw = localStorage.getItem(PLATFORM_STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as Record<string, string>
    for (const [url, platform] of Object.entries(parsed)) {
      if (url && platform) platformCache.set(url, platform)
    }
  } catch {
    // ignore
  }
}

function persistPlatformStorage() {
  try {
    const obj: Record<string, string> = {}
    for (const [url, platform] of platformCache) obj[url] = platform
    localStorage.setItem(PLATFORM_STORAGE_KEY, JSON.stringify(obj))
  } catch {
    // ignore
  }
}

/** Cached friendly hostname for a backend URL (from `/v1/discover` or LAN scan). */
export function readCachedRemoteHostname(backendUrl: string): string | null {
  const key = normalizeBackendUrl(backendUrl)
  const hit = hostnameCache.get(key)
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
  hostnameCache.set(key, short)
}

/** OS from LAN scan / discover — used by Open Recent icons (no live probe). */
export function readCachedRemotePlatform(backendUrl: string): string | null {
  loadPlatformStorage()
  const key = normalizeBackendUrl(backendUrl)
  return platformCache.get(key) || null
}

export function rememberRemotePlatform(
  backendUrl: string,
  platform: string | null | undefined
) {
  const key = normalizeBackendUrl(backendUrl)
  const trimmed = (platform || '').trim()
  if (!trimmed || isLocalBackendUrl(key)) return
  loadPlatformStorage()
  platformCache.set(key, trimmed)
  persistPlatformStorage()
}

/** Fetch `/v1/discover` (auth-exempt) and cache the hostname. */
export async function resolveRemoteHostname(
  backendUrl: string
): Promise<string | null> {
  const key = normalizeBackendUrl(backendUrl)
  if (isLocalBackendUrl(key)) return null
  const cached = hostnameCache.get(key)
  if (cached) return cached
  try {
    const res = await fetch(`${key}/v1/discover`, {
      method: 'GET',
      headers: { Accept: 'application/json' }
    })
    if (!res.ok) return null
    const body = (await res.json()) as { hostname?: string; platform?: string }
    rememberRemoteHostname(key, body.hostname)
    rememberRemotePlatform(key, body.platform)
    return hostnameCache.get(key) || null
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
