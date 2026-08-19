import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  applyNotifyApproval,
  applyNotifyCompletion,
  getStoredNotifyApproval,
  getStoredNotifyCompletion,
  NOTIFY_APPROVAL_CHANGE_EVENT,
  NOTIFY_COMPLETION_CHANGE_EVENT,
  shouldNotifyCompletion
} from './notification-settings'

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

describe('notification-settings', () => {
  beforeEach(() => {
    installMemoryLocalStorage()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('notifies unfocused when another chat finished', () => {
    expect(
      shouldNotifyCompletion('unfocused', {
        windowFocused: true,
        viewingSession: false
      })
    ).toBe(true)
    expect(
      shouldNotifyCompletion('unfocused', {
        windowFocused: true,
        viewingSession: true
      })
    ).toBe(false)
  })

  it('defaults completion to unfocused and approval to true', () => {
    expect(getStoredNotifyCompletion()).toBe('unfocused')
    expect(getStoredNotifyApproval()).toBe(true)
  })

  it('persists completion mode and emits change event', () => {
    const handler = vi.fn()
    window.addEventListener(NOTIFY_COMPLETION_CHANGE_EVENT, handler)
    applyNotifyCompletion('always')
    expect(getStoredNotifyCompletion()).toBe('always')
    expect(localStorage.getItem('sandwalk.notify-completion')).toBe('always')
    expect(handler).toHaveBeenCalledOnce()
    window.removeEventListener(NOTIFY_COMPLETION_CHANGE_EVENT, handler)
  })

  it('persists approval toggle and emits change event', () => {
    const handler = vi.fn()
    window.addEventListener(NOTIFY_APPROVAL_CHANGE_EVENT, handler)
    applyNotifyApproval(false)
    expect(getStoredNotifyApproval()).toBe(false)
    expect(localStorage.getItem('sandwalk.notify-approval')).toBe('off')
    expect(handler).toHaveBeenCalledOnce()
    window.removeEventListener(NOTIFY_APPROVAL_CHANGE_EVENT, handler)
  })
})
