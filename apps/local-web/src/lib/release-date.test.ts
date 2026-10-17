import { describe, expect, it, vi } from 'vitest'

import { fetchLastReleaseDate, formatReleaseAge } from './release-date'

describe('formatReleaseAge', () => {
  const now = new Date('2026-10-17T04:17:00.000Z')

  it('counts whole days since the release', () => {
    expect(formatReleaseAge('2026-10-13T18:12:00.000Z', now)).toMatch(
      /\(3 days ago\)$/
    )
  })

  it('says today when the release is under a day old', () => {
    expect(formatReleaseAge('2026-10-17T01:00:00.000Z', now)).toMatch(
      /\(today\)$/
    )
  })

  it('says 1 day ago', () => {
    expect(formatReleaseAge('2026-10-15T20:00:00.000Z', now)).toMatch(
      /\(1 day ago\)$/
    )
  })

  it('rejects a bad timestamp', () => {
    expect(formatReleaseAge('not-a-date', now)).toBeNull()
  })
})

describe('fetchLastReleaseDate', () => {
  it('reads pub_date and returns null when the file is missing or broken', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ pub_date: '2026-10-13T18:12:00Z' })
      }))
    )
    expect(await fetchLastReleaseDate()).toBe('2026-10-13T18:12:00Z')

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: false, json: async () => ({}) }))
    )
    expect(await fetchLastReleaseDate()).toBeNull()

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, json: async () => ({ pub_date: 1 }) }))
    )
    expect(await fetchLastReleaseDate()).toBeNull()

    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline') }))
    expect(await fetchLastReleaseDate()).toBeNull()
    vi.unstubAllGlobals()
  })
})
