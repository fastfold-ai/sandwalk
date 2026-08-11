import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  persistRememberedApiKey,
  REMEMBERED_AUTH_STORAGE_KEY
} from './remembered-auth'
import { resolveBackendApiKey } from './resolve-backend-api-key'

function installMemoryLocalStorage() {
  const store = new Map<string, string>()
  const memory: Storage = {
    get length() {
      return store.size
    },
    clear() {
      store.clear()
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null
    },
    key(index: number) {
      return [...store.keys()][index] ?? null
    },
    removeItem(key: string) {
      store.delete(key)
    },
    setItem(key: string, value: string) {
      store.set(key, String(value))
    }
  }
  vi.stubGlobal('localStorage', memory)
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: memory
  })
}

vi.mock('@/lib/desktop', () => ({
  isTauri: vi.fn(() => false),
  desktopGetAuth: vi.fn()
}))

describe('resolveBackendApiKey', () => {
  beforeEach(() => {
    installMemoryLocalStorage()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-26T12:00:00Z'))
    delete (globalThis as { __SANDWALK_API_KEY__?: string }).__SANDWALK_API_KEY__
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('prefers an explicit key', async () => {
    persistRememberedApiKey('http://127.0.0.1:8787', 'sk-remembered')
    await expect(
      resolveBackendApiKey('http://127.0.0.1:8787', 'sk-explicit')
    ).resolves.toBe('sk-explicit')
  })

  it('uses remembered key when no explicit key', async () => {
    persistRememberedApiKey('http://127.0.0.1:8787', 'sk-remembered')
    await expect(resolveBackendApiKey('http://127.0.0.1:8787')).resolves.toBe(
      'sk-remembered'
    )
    expect(localStorage.getItem(REMEMBERED_AUTH_STORAGE_KEY)).toContain(
      'sk-remembered'
    )
  })
})
