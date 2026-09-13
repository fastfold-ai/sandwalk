import { describe, expect, it } from 'vitest'

import { mergeOfflineSignals, normalizeOfflinePayload } from './useOfflineStatus'

describe('normalizeOfflinePayload', () => {
  it('reads snake_case from the API', () => {
    const status = normalizeOfflinePayload({
      is_offline: true,
      message: 'Offline — dns',
      features_affected: ['Slack'],
      last_check: '2026-01-01T00:00:00Z',
      targets_checked: ['slack.com'],
      forced: false
    })
    expect(status.isOffline).toBe(true)
    expect(status.featuresAffected).toEqual(['Slack'])
    expect(status.lastCheck).toBe('2026-01-01T00:00:00Z')
  })
})

describe('mergeOfflineSignals', () => {
  it('treats a down browser link as offline even if the API is up', () => {
    const next = mergeOfflineSignals(false, null, false)
    expect(next.isOffline).toBe(true)
    expect(next.message).toBe('No internet connection')
  })

  it('treats a reachable API as online when the browser is online', () => {
    const next = mergeOfflineSignals(true, null, false)
    expect(next.isOffline).toBe(false)
    expect(next.message).toBe('Back online')
  })
})
