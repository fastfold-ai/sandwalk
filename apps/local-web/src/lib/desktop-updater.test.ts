import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  checkDesktopUpdate,
  formatDesktopVersion,
  installDesktopUpdate,
  PREVIEW_UPDATE_STORAGE_KEY,
  previewUpdateVersion,
  UPDATE_CHECK_INTERVAL_MS
} from './desktop-updater'

const tauri = vi.hoisted(() => ({
  on: false,
  check: vi.fn(),
  relaunch: vi.fn(),
  stop: vi.fn()
}))

vi.mock('@/lib/desktop', () => ({
  isTauri: () => tauri.on,
  desktopServerStop: () => tauri.stop()
}))

vi.mock('@tauri-apps/plugin-updater', () => ({
  check: () => tauri.check()
}))

vi.mock('@tauri-apps/plugin-process', () => ({
  relaunch: () => tauri.relaunch()
}))

const store = new Map<string, string>()

beforeEach(() => {
  store.clear()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value)
    },
    removeItem: (key: string) => {
      store.delete(key)
    }
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('desktop update preview', () => {
  it('rechecks about every 15 minutes', () => {
    expect(UPDATE_CHECK_INTERVAL_MS).toBe(15 * 60 * 1000)
  })

  it('treats a stored preview version as a newer release without calling GitHub', async () => {
    localStorage.setItem(PREVIEW_UPDATE_STORAGE_KEY, '9.8.8')
    const result = await checkDesktopUpdate()
    expect(result.kind).toBe('available')
    if (result.kind === 'available') expect(result.info.version).toBe('9.8.8')
  })

  it('does not download or relaunch a preview update', async () => {
    localStorage.setItem(PREVIEW_UPDATE_STORAGE_KEY, '9.8.8')
    const result = await installDesktopUpdate()
    expect(result.ok).toBe(false)
    expect(result.message).toMatch(/Preview update only/)
  })

  it('formats versions and treats a blank preview as none', () => {
    expect(formatDesktopVersion(null)).toBe('')
    expect(formatDesktopVersion('1.2.3')).toBe('v1.2.3')
    expect(formatDesktopVersion('v1.2.3')).toBe('v1.2.3')
    localStorage.setItem(PREVIEW_UPDATE_STORAGE_KEY, '   ')
    expect(previewUpdateVersion()).toBeNull()
  })

  it('reports the current build when the preview matches it', async () => {
    localStorage.setItem(PREVIEW_UPDATE_STORAGE_KEY, `v${__UI_VERSION__}`)
    const result = await checkDesktopUpdate()
    expect(result.kind).toBe('current')
  })

  it('is unavailable outside the desktop app', async () => {
    tauri.on = false
    expect((await checkDesktopUpdate()).kind).toBe('unavailable')
    const installed = await installDesktopUpdate()
    expect(installed.ok).toBe(false)
    expect(installed.message).toMatch(/Sandwalk\.app/)
  })

  it('downloads a real update and reports progress', async () => {
    tauri.on = true
    const events: Array<{ event: string; data?: { contentLength?: number; chunkLength?: number } }> = [
      { event: 'Started', data: { contentLength: 10 } },
      { event: 'Progress', data: { chunkLength: 4 } },
      { event: 'Finished' }
    ]
    tauri.check.mockResolvedValue({
      version: '9.9.9',
      body: 'notes',
      date: '2026-10-17',
      downloadAndInstall: async (onEvent: (event: (typeof events)[number]) => void) => {
        for (const event of events) onEvent(event)
      }
    })
    tauri.relaunch.mockResolvedValue(undefined)
    tauri.stop.mockResolvedValue(undefined)
    const progress: string[] = []
    const checked = await checkDesktopUpdate()
    expect(checked.kind).toBe('available')
    const installed = await installDesktopUpdate({
      onProgress: update => progress.push(update.phase)
    })
    expect(installed.ok).toBe(true)
    expect(progress).toEqual(['download', 'download', 'install'])
    tauri.on = false
  })

  it('returns the updater error and a missing update', async () => {
    tauri.on = true
    tauri.check.mockRejectedValueOnce(new Error('offline'))
    const failed = await checkDesktopUpdate()
    expect(failed.kind).toBe('error')
    tauri.check.mockResolvedValueOnce(null)
    expect((await checkDesktopUpdate()).kind).toBe('current')
    tauri.check.mockResolvedValueOnce(null)
    const missing = await installDesktopUpdate()
    expect(missing.message).toMatch(/No update available/)
    tauri.check.mockRejectedValueOnce('nope')
    const broken = await installDesktopUpdate()
    expect(broken.message).toBe('nope')
    tauri.on = false
  })
})
