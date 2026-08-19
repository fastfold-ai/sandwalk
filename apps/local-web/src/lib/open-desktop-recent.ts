import { normalizeBackendUrl } from '@/lib/backend-url'
import { openDesktopWindow } from '@/lib/desktop'
import {
  rememberRemoteHostname,
  rememberRemotePlatform
} from '@/lib/remote-hostname'
import { resolveBackendApiKey } from '@/lib/resolve-backend-api-key'

export type DesktopRecentRef = {
  url: string
  route?: string | null
  title?: string | null
  id?: string | null
  hostname?: string | null
  platform?: string | null
}

/**
 * Reopen an Open Recent snapshot. Always opens the window; a remembered key
 * is applied silently, otherwise LoginView collects auth once.
 */
export async function openDesktopRecent(
  row: DesktopRecentRef
): Promise<{ opened: boolean; url: string }> {
  const url = normalizeBackendUrl(row.url)
  const key = await resolveBackendApiKey(url)
  const route = row.route?.trim() || '/'
  const title = row.title?.trim() || null
  const snapshotId = row.id?.trim() || null
  const hostname = row.hostname?.trim() || null
  const platform = row.platform?.trim() || null
  if (hostname) rememberRemoteHostname(url, hostname)
  if (platform) rememberRemotePlatform(url, platform)
  await openDesktopWindow({
    backendUrl: url,
    apiKey: key || null,
    route,
    title,
    snapshotId,
    hostname,
    platform,
    focusExisting: true
  })
  return { opened: true, url }
}
