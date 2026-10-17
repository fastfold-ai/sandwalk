import { describe, expect, it } from 'vitest'

import { formatReleaseAge } from './release-date'

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
})
