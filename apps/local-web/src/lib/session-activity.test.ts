import { describe, expect, it } from 'vitest'

import { deriveSessionActivity } from './session-activity'
import { emptySessionChatState, type SessionChatState } from './sessions'

function chat(overrides: Partial<SessionChatState>): SessionChatState {
  return { ...emptySessionChatState(), ...overrides }
}

describe('deriveSessionActivity', () => {
  it('keeps only sessions with a spinner or approval badge', () => {
    const map = deriveSessionActivity({
      a: chat({ runActive: true }),
      b: chat({ pendingApproval: { id: 'x' } as never }),
      c: chat({ composer: 'typing but idle' }),
      d: undefined
    })
    expect(Object.keys(map).sort()).toEqual(['a', 'b'])
    expect(map.a).toEqual({ runActive: true, pendingApproval: false })
    expect(map.b).toEqual({ runActive: false, pendingApproval: true })
  })

  it('returns the previous reference when flags did not change', () => {
    const first = deriveSessionActivity({ a: chat({ runActive: true }) })
    const second = deriveSessionActivity(
      // New store object (a token streamed) but same flags.
      { a: chat({ runActive: true, composer: 'changed' }) },
      first
    )
    expect(second).toBe(first)
  })

  it('returns a new reference when a flag flips or a session appears', () => {
    const first = deriveSessionActivity({ a: chat({ runActive: true }) })
    const flipped = deriveSessionActivity({ a: chat({ runActive: false }) }, first)
    expect(flipped).not.toBe(first)
    expect(Object.keys(flipped)).toEqual([])

    const grown = deriveSessionActivity(
      { a: chat({ runActive: true }), b: chat({ runActive: true }) },
      first
    )
    expect(grown).not.toBe(first)
    expect(Object.keys(grown).sort()).toEqual(['a', 'b'])
  })

  it('shares one frozen empty map while nothing is active', () => {
    const a = deriveSessionActivity({})
    const b = deriveSessionActivity({ x: chat({}) }, a)
    expect(b).toBe(a)
    expect(Object.isFrozen(a)).toBe(true)
  })
})
