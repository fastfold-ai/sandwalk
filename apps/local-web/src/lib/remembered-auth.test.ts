import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearRememberedApiKey,
  persistRememberedApiKey,
  readRememberedApiKey,
  REMEMBERED_AUTH_STORAGE_KEY
} from './remembered-auth'

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

describe('remembered-auth', () => {
  beforeEach(() => {
    installMemoryLocalStorage()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-26T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('round-trips a remembered key', () => {
    persistRememberedApiKey('http://127.0.0.1:8787/', 'sk-test')
    expect(readRememberedApiKey('http://127.0.0.1:8787')).toBe('sk-test')
  })

  it('expires after 30 days', () => {
    persistRememberedApiKey('http://127.0.0.1:8787', 'sk-test')
    vi.setSystemTime(new Date('2026-08-26T12:00:01Z'))
    expect(readRememberedApiKey('http://127.0.0.1:8787')).toBeUndefined()
    expect(localStorage.getItem(REMEMBERED_AUTH_STORAGE_KEY)).toBe('{}')
  })

  it('clears on logout', () => {
    persistRememberedApiKey('http://127.0.0.1:8787', 'sk-test')
    clearRememberedApiKey('http://127.0.0.1:8787')
    expect(readRememberedApiKey('http://127.0.0.1:8787')).toBeUndefined()
  })
})
