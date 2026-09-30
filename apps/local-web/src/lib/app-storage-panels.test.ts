import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  dropUnbalancedPanelLayouts,
  SESSION_PANELS_AUTO_SAVE_ID
} from './app-storage'

const KEY = `react-resizable-panels:${SESSION_PANELS_AUTO_SAVE_ID}`

describe('dropUnbalancedPanelLayouts', () => {
  beforeEach(() => {
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
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('removes a saved layout whose sizes do not add up to 100', () => {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        'chat,draft-terminal': { layout: [65, 40], expandToSizes: {} },
        'chat,files': { layout: [65, 35], expandToSizes: {} }
      })
    )
    dropUnbalancedPanelLayouts(SESSION_PANELS_AUTO_SAVE_ID)
    const left = JSON.parse(localStorage.getItem(KEY) || '{}') as Record<string, unknown>
    expect(left['chat,draft-terminal']).toBeUndefined()
    expect(left['chat,files']).toBeTruthy()
  })

  it('clears the key when every saved layout is unbalanced', () => {
    localStorage.setItem(KEY, JSON.stringify({ a: { layout: [65, 40] } }))
    dropUnbalancedPanelLayouts(SESSION_PANELS_AUTO_SAVE_ID)
    expect(localStorage.getItem(KEY)).toBeNull()
  })
})
