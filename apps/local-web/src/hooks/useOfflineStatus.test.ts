import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import {
  mergeOfflineSignals,
  normalizeOfflinePayload,
  useOfflineStatus
} from './useOfflineStatus'

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

  it('prefers an unreachable API and a server message', () => {
    expect(mergeOfflineSignals(true, null, true).message).toBe(
      'Cannot reach the Sandwalk server'
    )
    expect(
      mergeOfflineSignals(
        true,
        {
          isOffline: true,
          justOnline: false,
          reason: null,
          message: '',
          featuresAffected: ['Slack'],
          lastCheck: null,
          targetsChecked: null,
          forced: false
        },
        false
      ).message
    ).toMatch(/Offline/)
  })
})

describe('useOfflineStatus', () => {
  it('polls the server and flashes back online', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          isOffline: true,
          message: 'dns',
          featuresAffected: ['Slack'],
          lastCheck: 'now',
          targetsChecked: ['slack.com'],
          forced: true
        })
      }))
    )
    const { result } = renderHook(() => useOfflineStatus(50_000))
    await waitFor(() => expect(result.current.status.isOffline).toBe(true))
    expect(result.current.status.featuresAffected).toEqual(['Slack'])
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ isOffline: false, message: 'ok' })
      }))
    )
    await act(async () => {
      await result.current.refetch()
    })
    await waitFor(() => expect(result.current.status.justOnline).toBe(true))
    vi.unstubAllGlobals()
  })
})
