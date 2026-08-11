import {
  injectedDesktopApiKey,
  isLocalBackendUrl,
  normalizeBackendUrl
} from '@/lib/backend-url'
import { desktopGetAuth, isTauri } from '@/lib/desktop'
import {
  persistRememberedApiKey,
  readRememberedApiKey
} from '@/lib/remembered-auth'

/**
 * Resolve an API key for a backend URL without prompting.
 * Order: window inject → remembered localStorage → local desktop control plane.
 */
export async function resolveBackendApiKey(
  backendUrl: string,
  explicit?: string | null
): Promise<string | undefined> {
  const trimmed = explicit?.trim()
  if (trimmed) return trimmed

  const url = normalizeBackendUrl(backendUrl)
  const injected = injectedDesktopApiKey()?.trim()
  if (injected) return injected

  const remembered = readRememberedApiKey(url)?.trim()
  if (remembered) return remembered

  if (!isTauri() || !isLocalBackendUrl(url)) return undefined

  try {
    const auth = await desktopGetAuth()
    const key = auth?.api_key?.trim()
    if (!key) return undefined
    // Only auto-apply when the local server actually requires auth.
    if (!auth.auth_enabled && !auth.api_key_configured) return undefined
    persistRememberedApiKey(url, key)
    return key
  } catch {
    return undefined
  }
}
