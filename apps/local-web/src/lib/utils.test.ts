import { afterEach, describe, expect, it, vi } from 'vitest'

import { cn, relativeTime } from './utils'

describe('cn', () => {
  it('merges class names and resolves tailwind conflicts', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
    expect(cn('text-sm', false && 'hidden', 'font-medium')).toBe(
      'text-sm font-medium'
    )
  })
})

describe('relativeTime', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns empty for missing or invalid values', () => {
    expect(relativeTime(null)).toBe('')
    expect(relativeTime(undefined)).toBe('')
    expect(relativeTime('not-a-date')).toBe('')
  })

  it('formats elapsed buckets', () => {
    const now = new Date('2026-07-13T12:00:00.000Z')
    vi.useFakeTimers()
    vi.setSystemTime(now)

    expect(relativeTime('2026-07-13T11:59:30.000Z')).toBe('now')
    expect(relativeTime('2026-07-13T11:45:00.000Z')).toBe('15m ago')
    expect(relativeTime('2026-07-13T09:00:00.000Z')).toBe('3h ago')
    expect(relativeTime('2026-07-11T12:00:00.000Z')).toBe('2d ago')
    expect(relativeTime('2026-06-29T12:00:00.000Z')).toBe('2w ago')
    expect(relativeTime('2026-04-13T12:00:00.000Z')).toBe('3mo ago')
  })
})
