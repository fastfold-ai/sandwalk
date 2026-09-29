import { describe, expect, it } from 'vitest'

import { keepArrayIfSame, sameArrayBy, shallowEqualObjects } from './stable-equal'

describe('shallowEqualObjects', () => {
  it('compares own keys with Object.is', () => {
    const shared = { x: 1 }
    expect(shallowEqualObjects({ a: 1, b: shared }, { a: 1, b: shared })).toBe(true)
    expect(shallowEqualObjects({ a: 1, b: { x: 1 } }, { a: 1, b: { x: 1 } })).toBe(false)
    expect(shallowEqualObjects({ a: 1 }, { a: 1, b: 2 })).toBe(false)
    expect(shallowEqualObjects(null, { a: 1 })).toBe(false)
    expect(shallowEqualObjects(undefined, undefined)).toBe(true)
  })
})

describe('sameArrayBy / keepArrayIfSame', () => {
  const key = (s: { id: string; enabled: boolean }) => `${s.id}:${s.enabled}`

  it('treats equal content as the same and keeps the previous reference', () => {
    const prev = [{ id: 'a', enabled: true }, { id: 'b', enabled: false }]
    const next = [{ id: 'a', enabled: true }, { id: 'b', enabled: false }]
    expect(sameArrayBy(prev, next, key)).toBe(true)
    expect(keepArrayIfSame(prev, next, key)).toBe(prev)
  })

  it('detects reorder, length and field changes', () => {
    const prev = [{ id: 'a', enabled: true }, { id: 'b', enabled: false }]
    expect(sameArrayBy(prev, [prev[1], prev[0]], key)).toBe(false)
    expect(sameArrayBy(prev, prev.slice(0, 1), key)).toBe(false)
    const toggled = [{ id: 'a', enabled: true }, { id: 'b', enabled: true }]
    expect(keepArrayIfSame(prev, toggled, key)).toBe(toggled)
  })

  it('handles empty and nullish inputs', () => {
    expect(sameArrayBy([], [], key)).toBe(true)
    expect(sameArrayBy(null, [], key)).toBe(false)
  })
})
