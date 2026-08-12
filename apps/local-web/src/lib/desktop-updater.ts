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

export async function checkDesktopUpdate(): Promise<DesktopUpdateCheckResult> {
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
export async function installDesktopUpdate(): Promise<{
  ok: boolean
  message?: string
}> {
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

    await update.downloadAndInstall()
    await relaunch()
    return { ok: true }
  } catch (err) {
    return {
      ok: false,
      message: err instanceof Error ? err.message : String(err)
    }
  }
}
