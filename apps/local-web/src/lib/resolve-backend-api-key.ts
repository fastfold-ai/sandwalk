import {
  injectedDesktopApiKeyFor,
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
 * Order: explicit → remembered for this URL → inject only if this
 * window is bound to the same URL → local desktop control plane.
 *
 * Never reuse another host’s injected key (Welcome → Open Recent).
 */
export async function resolveBackendApiKey(
  backendUrl: string,
  explicit?: string | null
): Promise<string | undefined> {
  const trimmed = explicit?.trim()
  if (trimmed) return trimmed

  const url = normalizeBackendUrl(backendUrl)

  const remembered = readRememberedApiKey(url)?.trim()
  if (remembered) return remembered

  const injected = injectedDesktopApiKeyFor(url)?.trim()
  if (injected) return injected

  if (!isTauri() || !isLocalBackendUrl(url)) return undefined

  try {
    const auth = await desktopGetAuth()
    const key = auth?.api_key?.trim()
    if (!auth || !key) return undefined
    // Only auto-apply when the local server actually requires auth.
    if (!auth.auth_enabled && !auth.api_key_configured) return undefined
    persistRememberedApiKey(url, key)
    return key
  } catch {
    return undefined
  }
}
