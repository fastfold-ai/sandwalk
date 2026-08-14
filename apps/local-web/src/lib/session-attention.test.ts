import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearAllSessionAttention,
  clearSessionAttention,
  getAttentionSessionIds,
  hasSessionAttention,
  markSessionAttention
} from './session-attention'

// setDockBadge is a Tauri desktop call — mock it out so the tests don't
// try to invoke a native API in jsdom.
vi.mock('@/lib/desktop', () => ({
  setDockBadge: vi.fn(() => Promise.resolve())
}))

beforeEach(() => {
  clearAllSessionAttention()
})

describe('markSessionAttention / hasSessionAttention', () => {
  it('adds an id and reports it as marked', () => {
    markSessionAttention('a')
    expect(hasSessionAttention('a')).toBe(true)
  })

  it('is idempotent — marking twice keeps a single entry', () => {
    markSessionAttention('a')
    markSessionAttention('a')
    expect(getAttentionSessionIds().size).toBe(1)
  })

  it('ignores empty ids', () => {
    markSessionAttention('')
    expect(getAttentionSessionIds().size).toBe(0)
  })
})

describe('clearSessionAttention', () => {
  it('removes a marked id', () => {
    markSessionAttention('a')
    clearSessionAttention('a')
    expect(hasSessionAttention('a')).toBe(false)
  })

  it('is a no-op when the id is not marked', () => {
    clearSessionAttention('never-marked')
    expect(getAttentionSessionIds().size).toBe(0)
  })

  it('leaves other ids untouched', () => {
    markSessionAttention('a')
    markSessionAttention('b')
    clearSessionAttention('a')
    expect(hasSessionAttention('a')).toBe(false)
    expect(hasSessionAttention('b')).toBe(true)
  })
})

describe('clearAllSessionAttention', () => {
  it('empties the set', () => {
    markSessionAttention('a')
    markSessionAttention('b')
    clearAllSessionAttention()
    expect(getAttentionSessionIds().size).toBe(0)
  })

  it('is a no-op when already empty', () => {
    clearAllSessionAttention()
    expect(getAttentionSessionIds().size).toBe(0)
  })
})
