export const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8787'
export const BACKEND_URL_STORAGE_KEY = 'fastfold.backend.url'

function injectedBackendUrl(): string | null {
  const injected = (globalThis as { __SANDWALK_HTTP__?: unknown }).__SANDWALK_HTTP__
  if (typeof injected === 'string' && injected.trim()) {
    return injected.trim().replace(/\/+$/, '')
  }
  return null
}

export function isLocalBackendUrl(url: string): boolean {
  return /127\.0\.0\.1|localhost/i.test(url)
}

/** Trim trailing slashes; fall back to the default when empty. */
export function normalizeBackendUrl(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, '')
  return trimmed || DEFAULT_BACKEND_URL
}

export function readStoredBackendUrl(): string {
  const fromDesktop = injectedBackendUrl()
  if (fromDesktop) return normalizeBackendUrl(fromDesktop)
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
  try {
    localStorage.setItem(BACKEND_URL_STORAGE_KEY, next)
  } catch {
    // ignore
  }
  return next
}
