import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  checkDesktopUpdate,
  installDesktopUpdate,
  PREVIEW_UPDATE_STORAGE_KEY,
  UPDATE_CHECK_INTERVAL_MS
} from './desktop-updater'

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
})
