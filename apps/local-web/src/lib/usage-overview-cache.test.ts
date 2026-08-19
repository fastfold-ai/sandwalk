import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { UsageOverview } from '@sandwalk/agent-ui-core'

import {
  invalidateUsageOverviewCache,
  prefetchUsageOverview,
  readUsageOverviewCache,
  writeUsageOverviewCache
} from './usage-overview-cache'

function overview(n: number): UsageOverview {
  return { lifetimeTokens: n } as UsageOverview
}

describe('usage-overview-cache', () => {
  beforeEach(() => {
    invalidateUsageOverviewCache()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-19T12:00:00.000Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    invalidateUsageOverviewCache()
  })

  it('returns null before a write', () => {
    expect(readUsageOverviewCache('http://local')).toBeNull()
  })

  it('reads back a matching scope and misses a different project', () => {
    writeUsageOverviewCache('http://local', overview(1))
    expect(readUsageOverviewCache('http://local')?.lifetimeTokens).toBe(1)
    expect(readUsageOverviewCache('http://local', 'p1')).toBeNull()
    writeUsageOverviewCache('http://local', overview(2), 'p1')
    expect(readUsageOverviewCache('http://local', 'p1')?.lifetimeTokens).toBe(2)
  })

  it('expires after the TTL', () => {
    writeUsageOverviewCache('http://local', overview(3))
    vi.setSystemTime(new Date('2026-08-19T12:00:46.000Z'))
    expect(readUsageOverviewCache('http://local')).toBeNull()
  })

  it('prefetch is a no-op when a warm entry exists', () => {
    writeUsageOverviewCache('http://local', overview(4))
    const fetch = vi.fn()
    prefetchUsageOverview('http://local', fetch)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('prefetch writes on success and ignores a later failure', async () => {
    const fetch = vi.fn().mockResolvedValue(overview(5))
    prefetchUsageOverview('http://local', fetch)
    await vi.waitFor(() => {
      expect(readUsageOverviewCache('http://local')?.lifetimeTokens).toBe(5)
    })
    const fail = vi.fn().mockRejectedValue(new Error('down'))
    prefetchUsageOverview('http://other', fail)
    await vi.waitFor(() => {
      expect(fail).toHaveBeenCalled()
    })
    expect(readUsageOverviewCache('http://other')).toBeNull()
  })

  it('coalesces in-flight prefetch for the same key', () => {
    let resolveFirst: (value: UsageOverview) => void = () => undefined
    const first = new Promise<UsageOverview>(resolve => {
      resolveFirst = resolve
    })
    const fetch = vi.fn().mockReturnValue(first)
    prefetchUsageOverview('http://local', fetch)
    prefetchUsageOverview('http://local', fetch)
    expect(fetch).toHaveBeenCalledTimes(1)
    resolveFirst(overview(6))
  })
})
