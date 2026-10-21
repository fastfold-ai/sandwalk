export const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8787'
export const BACKEND_URL_STORAGE_KEY = 'fastfold.backend.url'

type WindowBind = {
  http?: string
  apiKey?: string
  snap?: string
}

const BIND_NAME_PREFIX = 'sandwalk-bind:'

function readWindowNameBind(): WindowBind | null {
  try {
    const raw = window.name || ''
    if (!raw.startsWith(BIND_NAME_PREFIX)) return null
    const parsed = JSON.parse(raw.slice(BIND_NAME_PREFIX.length)) as WindowBind
    if (!parsed || typeof parsed !== 'object') return null
    return parsed
  } catch {
    return null
  }
}

function writeWindowNameBind(patch: WindowBind) {
  try {
    const prev = readWindowNameBind() || {}
    const next: WindowBind = {
      http: patch.http ?? prev.http,
      apiKey: patch.apiKey ?? prev.apiKey,
      snap: patch.snap ?? prev.snap
    }
    window.name = BIND_NAME_PREFIX + JSON.stringify(next)
  } catch {
    // ignore
  }
}

function applyBind(http?: string | null, apiKey?: string | null, snap?: string | null) {
  const patch: WindowBind = {}
  if (http?.trim()) {
    const normalized = http.trim().replace(/\/+$/, '')
    ;(globalThis as { __SANDWALK_HTTP__?: string }).__SANDWALK_HTTP__ = normalized
    patch.http = normalized
  }
  if (apiKey?.trim()) {
    const key = apiKey.trim()
    ;(globalThis as { __SANDWALK_API_KEY__?: string }).__SANDWALK_API_KEY__ = key
    patch.apiKey = key
  }
  if (snap?.trim()) {
    ;(globalThis as { __SANDWALK_SNAPSHOT_ID__?: string }).__SANDWALK_SNAPSHOT_ID__ =
      snap.trim()
    patch.snap = snap.trim()
  }
  if (patch.http || patch.apiKey || patch.snap) writeWindowNameBind(patch)
}

/** One-shot bootstrap from `?sw_http=` / `?sw_key=` / `?sw_snap=` (desktop WebView). */
function consumeQueryBootstrap(): void {
  if (typeof window === 'undefined') return
  try {
    const params = new URLSearchParams(window.location.search)
    const http = params.get('sw_http')?.trim() || null
    const apiKey = params.get('sw_key')?.trim() || null
    const snap = params.get('sw_snap')?.trim() || null
    if (!http && !apiKey && !snap) return
    applyBind(http, apiKey, snap)
    params.delete('sw_http')
    params.delete('sw_key')
    params.delete('sw_snap')
    const next = `${window.location.pathname}${
      params.toString() ? `?${params}` : ''
    }${window.location.hash}`
    window.history.replaceState(null, '', next)
  } catch {
    // ignore
  }
}

let bootstrapped = false
function ensureDesktopBindBootstrap() {
  if (bootstrapped) return
  bootstrapped = true
  consumeQueryBootstrap()
  // Rehydrate from per-window `window.name` if inject globals were cleared (HMR).
  const named = readWindowNameBind()
  if (named) {
    if (named.http && !(globalThis as { __SANDWALK_HTTP__?: unknown }).__SANDWALK_HTTP__) {
      ;(globalThis as { __SANDWALK_HTTP__?: string }).__SANDWALK_HTTP__ = named.http
    }
    if (
      named.apiKey &&
      !(globalThis as { __SANDWALK_API_KEY__?: unknown }).__SANDWALK_API_KEY__
    ) {
      ;(globalThis as { __SANDWALK_API_KEY__?: string }).__SANDWALK_API_KEY__ =
        named.apiKey
    }
    if (
      named.snap &&
      !(globalThis as { __SANDWALK_SNAPSHOT_ID__?: unknown }).__SANDWALK_SNAPSHOT_ID__
    ) {
      ;(globalThis as { __SANDWALK_SNAPSHOT_ID__?: string }).__SANDWALK_SNAPSHOT_ID__ =
        named.snap
    }
  }
  // Mirror live inject into window.name so reloads keep the remote bind.
  const http = (globalThis as { __SANDWALK_HTTP__?: unknown }).__SANDWALK_HTTP__
  const apiKey = (globalThis as { __SANDWALK_API_KEY__?: unknown }).__SANDWALK_API_KEY__
  const snap = (globalThis as { __SANDWALK_SNAPSHOT_ID__?: unknown })
    .__SANDWALK_SNAPSHOT_ID__
  applyBind(
    typeof http === 'string' ? http : null,
    typeof apiKey === 'string' ? apiKey : null,
    typeof snap === 'string' ? snap : null
  )
}

function injectedBackendUrl(): string | null {
  ensureDesktopBindBootstrap()
  const injected = (globalThis as { __SANDWALK_HTTP__?: unknown }).__SANDWALK_HTTP__
  if (typeof injected === 'string' && injected.trim()) {
    return injected.trim().replace(/\/+$/, '')
  }
  const named = readWindowNameBind()?.http
  if (named?.trim()) {
    const normalized = named.trim().replace(/\/+$/, '')
    ;(globalThis as { __SANDWALK_HTTP__?: string }).__SANDWALK_HTTP__ = normalized
    return normalized
  }
  return null
}

/**
 * True when this WebView is pinned to a *remote* backend. Local binds still use
 * shared localStorage so Change Server / prefs keep working on the main window.
 */
export function hasDesktopBackendInject(): boolean {
  const url = injectedBackendUrl()
  return url != null && !isLocalBackendUrl(url)
}

/**
 * Desktop multi-window: do not write the shared localStorage backend URL when
 * this window is bound to a remote host (avoids poisoning sibling windows).
 */
export function shouldPersistActiveBackendUrl(): boolean {
  return !hasDesktopBackendInject()
}

/** Keep per-window inject / window.name in sync after in-app Change server. */
export function pinDesktopBackendBind(url: string, apiKey?: string | null) {
  const normalized = normalizeBackendUrl(url)
  const key = apiKey?.trim() || null
  ;(globalThis as { __SANDWALK_HTTP__?: string }).__SANDWALK_HTTP__ = normalized
  if (key) {
    ;(globalThis as { __SANDWALK_API_KEY__?: string }).__SANDWALK_API_KEY__ = key
  } else {
    delete (globalThis as { __SANDWALK_API_KEY__?: string }).__SANDWALK_API_KEY__
  }
  writeWindowNameBind({
    http: normalized,
    apiKey: key || '',
    snap: readWindowNameBind()?.snap
  })
}

export function injectedDesktopApiKey(): string | null {
  ensureDesktopBindBootstrap()
  const injected = (globalThis as { __SANDWALK_API_KEY__?: unknown })
    .__SANDWALK_API_KEY__
  if (typeof injected === 'string' && injected.trim()) return injected.trim()
  const named = readWindowNameBind()?.apiKey
  if (named?.trim()) {
    ;(globalThis as { __SANDWALK_API_KEY__?: string }).__SANDWALK_API_KEY__ =
      named.trim()
    return named.trim()
  }
  return null
}

/** Backend URL this WebView is pinned to (inject / window.name), if any. */
export function injectedDesktopBackendUrl(): string | null {
  const url = injectedBackendUrl()
  return url ? normalizeBackendUrl(url) : null
}

/**
 * Injected key only when this window is bound to `backendUrl`.
 * Prevents Welcome / sibling windows from leaking another host’s key.
 */
export function injectedDesktopApiKeyFor(
  backendUrl: string
): string | null {
  const bound = injectedDesktopBackendUrl()
  if (!bound || bound !== normalizeBackendUrl(backendUrl)) return null
  return injectedDesktopApiKey()
}

/**
 * When the dashboard is served by the API itself (production on :8787), a
 * browser on another machine must call that host — not 127.0.0.1, which is
 * the other machine. Vite (:1420 / :5173) and the Tauri webview are excluded.
 */
export function backendUrlFromPage(location: {
  protocol: string
  hostname: string
  origin: string
  port: string
}): string | null {
  if (location.protocol !== 'http:' && location.protocol !== 'https:') return null
  if (location.port === '1420' || location.port === '5173') return null
  const host = location.hostname.trim().toLowerCase()
  if (!host || host === 'localhost' || host === '127.0.0.1' || host === '[::1]' || host === '::1') {
    return null
  }
  return location.origin.replace(/\/+$/, '')
}

export function isLocalBackendUrl(url: string): boolean {
  const trimmed = url.trim()
  if (!trimmed) return true
  try {
    const parsed = new URL(
      trimmed.includes('://') ? trimmed : `http://${trimmed}`
    )
    const host = parsed.hostname.toLowerCase()
    const isLoopback =
      host === '127.0.0.1' ||
      host === 'localhost' ||
      host === '::1' ||
      host === '[::1]'
    if (!isLoopback) return false
    // Only port 8787 (or default/empty) is the local Sandwalk server.
    // Non-8787 loopback ports are SSH port-forwarded remote tunnels (`ssh -L <port>:127.0.0.1:8787`).
    return parsed.port === '' || parsed.port === '8787'
  } catch {
    return /127\.0\.0\.1:8787|localhost:8787/i.test(trimmed)
  }
}

/** Trim trailing slashes; fall back to the default when empty. */
export function normalizeBackendUrl(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, '')
  return trimmed || DEFAULT_BACKEND_URL
}

export function readStoredBackendUrl(): string {
  const fromDesktop = injectedBackendUrl()
  if (fromDesktop) return normalizeBackendUrl(fromDesktop)
  if (typeof window !== 'undefined') {
    const fromPage = backendUrlFromPage(window.location)
    if (fromPage) return normalizeBackendUrl(fromPage)
  }
  try {
    const stored = localStorage.getItem(BACKEND_URL_STORAGE_KEY)
    if (stored?.trim()) return normalizeBackendUrl(stored)
  } catch {
    // ignore
  }
  return DEFAULT_BACKEND_URL
}

export function persistBackendUrl(url: string): string {
  const next = normalizeBackendUrl(url)
  if (!shouldPersistActiveBackendUrl()) return next
  try {
    localStorage.setItem(BACKEND_URL_STORAGE_KEY, next)
  } catch {
    // ignore
  }
  return next
}
