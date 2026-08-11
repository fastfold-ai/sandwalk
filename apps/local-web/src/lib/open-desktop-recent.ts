import { isLocalBackendUrl, normalizeBackendUrl } from '@/lib/backend-url'
import { openDesktopWindow } from '@/lib/desktop'
import { readRememberedApiKey } from '@/lib/remembered-auth'
import { rememberRemoteHostname } from '@/lib/remote-hostname'

export type DesktopRecentRef = {
  url: string
  route?: string | null
  title?: string | null
  id?: string | null
  hostname?: string | null
}

/**
 * Reopen an Open Recent snapshot. Local / remembered-key remotes open
 * immediately; otherwise the caller should show the remote auth dialog.
 * Returns true when a window was opened.
 */
export async function openDesktopRecent(
  row: DesktopRecentRef
): Promise<{ opened: boolean; url: string }> {
  const url = normalizeBackendUrl(row.url)
  const key = readRememberedApiKey(url)
  const route = row.route?.trim() || '/'
  const title = row.title?.trim() || null
  const snapshotId = row.id?.trim() || null
  const hostname = row.hostname?.trim() || null
  if (hostname) rememberRemoteHostname(url, hostname)
  if (key || isLocalBackendUrl(url)) {
    await openDesktopWindow({
      backendUrl: url,
      apiKey: key || null,
      route,
      title,
      snapshotId,
      hostname,
      focusExisting: true
    })
    return { opened: true, url }
  }
  return { opened: false, url }
}
