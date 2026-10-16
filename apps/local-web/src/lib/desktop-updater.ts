/**
 * Tauri desktop auto-update (GitHub Releases + tauri-plugin-updater).
 * No-op helpers when not running inside the desktop shell.
 */

import { isTauri } from '@/lib/desktop'

export type DesktopUpdateInfo = {
  version: string
  body?: string | null
  date?: string | null
}

export type DesktopUpdateCheckResult =
  | { kind: 'unavailable' }
  | { kind: 'current' }
  | { kind: 'available'; info: DesktopUpdateInfo }
  | { kind: 'error'; message: string }

export function desktopUpdaterAvailable(): boolean {
  return isTauri()
}

/** Quiet re-check while the app stays open. */
export const UPDATE_CHECK_INTERVAL_MS = 15 * 60 * 1000

/**
 * Dev-only stand-in for a newer GitHub release. Set in the browser console,
 * then reload:
 *
 *   localStorage.setItem('sandwalk.update.preview', '9.9.9')
 *
 * Clear it with `localStorage.removeItem('sandwalk.update.preview')`.
 * The Update button appears, but install does not download or relaunch.
 */
export const PREVIEW_UPDATE_STORAGE_KEY = 'sandwalk.update.preview'

export function previewUpdateVersion(): string | null {
  try {
    const value = localStorage.getItem(PREVIEW_UPDATE_STORAGE_KEY)?.trim()
    return value || null
  } catch {
    return null
  }
}

function sameVersion(a: string, b: string): boolean {
  return a.replace(/^v/i, '') === b.replace(/^v/i, '')
}

export type DesktopUpdateProgress = {
  phase: 'download' | 'install'
  received: number
  total: number | null
}

export function formatDesktopVersion(version: string | null | undefined): string {
  if (!version) return ''
  return version.startsWith('v') ? version : `v${version}`
}

export async function checkDesktopUpdate(): Promise<DesktopUpdateCheckResult> {
  const preview = previewUpdateVersion()
  if (preview) {
    const current = typeof __UI_VERSION__ === 'string' ? __UI_VERSION__ : ''
    if (current && sameVersion(preview, current)) return { kind: 'current' }
    return {
      kind: 'available',
      info: {
        version: preview,
        body: 'Preview update. No download will run.'
      }
    }
  }
  if (!isTauri()) return { kind: 'unavailable' }
  try {
    const { check } = await import('@tauri-apps/plugin-updater')
    const update = await check()
    if (!update) return { kind: 'current' }
    return {
      kind: 'available',
      info: {
        version: update.version,
        body: update.body,
        date: update.date
      }
    }
  } catch (err) {
    return {
      kind: 'error',
      message: err instanceof Error ? err.message : String(err)
    }
  }
}

/** Download, install, and relaunch. Stops the nested agent first when possible. */
export async function installDesktopUpdate(options?: {
  onProgress?: (progress: DesktopUpdateProgress) => void
}): Promise<{
  ok: boolean
  message?: string
}> {
  if (previewUpdateVersion()) {
    return {
      ok: false,
      message:
        'Preview update only. Remove sandwalk.update.preview to install a real release.'
    }
  }
  if (!isTauri()) {
    return { ok: false, message: 'Desktop updater is only available in Sandwalk.app' }
  }
  try {
    const { check } = await import('@tauri-apps/plugin-updater')
    const { relaunch } = await import('@tauri-apps/plugin-process')
    const update = await check()
    if (!update) {
      return { ok: false, message: 'No update available' }
    }

    try {
      const { desktopServerStop } = await import('@/lib/desktop')
      await desktopServerStop()
    } catch {
      // Best-effort — updater still replaces the app bundle.
    }

    let received = 0
    let total: number | null = null
    await update.downloadAndInstall(event => {
      if (event.event === 'Started') {
        received = 0
        total = event.data.contentLength ?? null
        options?.onProgress?.({ phase: 'download', received, total })
        return
      }
      if (event.event === 'Progress') {
        received += event.data.chunkLength
        options?.onProgress?.({ phase: 'download', received, total })
        return
      }
      if (event.event === 'Finished') {
        options?.onProgress?.({
          phase: 'install',
          received: total ?? received,
          total
        })
      }
    })
    await relaunch()
    return { ok: true }
  } catch (err) {
    return {
      ok: false,
      message: err instanceof Error ? err.message : String(err)
    }
  }
}
