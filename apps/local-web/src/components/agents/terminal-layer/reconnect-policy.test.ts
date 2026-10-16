import { describe, expect, it } from 'vitest'

import {
  isRespawn,
  PTY_GONE_CLOSE_CODE,
  ptyHandleIsStale,
  RECONNECT_CAP_MS,
  RECONNECT_NOTICE_AFTER,
  reconnectDelayMs,
  shouldDropPtyHandle,
  shouldShowWaitingNotice
} from './reconnect-policy'

describe('reconnectDelayMs', () => {
  it('backs off exponentially from ~500ms', () => {
    expect(reconnectDelayMs(0, 0)).toBe(500)
    expect(reconnectDelayMs(1, 0)).toBe(1000)
    expect(reconnectDelayMs(2, 0)).toBe(2000)
    expect(reconnectDelayMs(3, 0)).toBe(4000)
  })

  it('adds up to 200ms of jitter', () => {
    expect(reconnectDelayMs(0, 0.999)).toBe(699)
  })

  it('caps so a long outage keeps polling instead of stalling', () => {
    expect(reconnectDelayMs(10, 0)).toBe(RECONNECT_CAP_MS)
    expect(reconnectDelayMs(50, 1)).toBe(RECONNECT_CAP_MS)
  })

  it('never produces a terminal "give up" state (any attempt yields a delay)', () => {
    for (const attempt of [0, 12, 100, 10_000]) {
      expect(reconnectDelayMs(attempt, 0)).toBeGreaterThan(0)
    }
  })
})

describe('shouldShowWaitingNotice', () => {
  it('stays quiet for the first few misses', () => {
    for (let i = 0; i < RECONNECT_NOTICE_AFTER; i++) {
      expect(shouldShowWaitingNotice(i, false)).toBe(false)
    }
  })

  it('shows once the threshold is reached', () => {
    expect(shouldShowWaitingNotice(RECONNECT_NOTICE_AFTER, false)).toBe(true)
  })

  it('does not repeat within the same outage', () => {
    expect(shouldShowWaitingNotice(RECONNECT_NOTICE_AFTER + 5, true)).toBe(false)
  })
})

describe('shouldDropPtyHandle', () => {
  it('forgets the PTY id only when the server says it is gone', () => {
    expect(shouldDropPtyHandle(PTY_GONE_CLOSE_CODE)).toBe(true)
    expect(shouldDropPtyHandle(1000)).toBe(false)
    expect(shouldDropPtyHandle(1006)).toBe(false)
    expect(shouldDropPtyHandle(undefined)).toBe(false)
  })
})

describe('ptyHandleIsStale', () => {
  it('never re-checks on the very first connect', () => {
    expect(ptyHandleIsStale(0, 'pty_a', [])).toBe(false)
  })

  it('is stale when a reconnect finds the id missing on the server', () => {
    // Server restarted: browser saw 1006, not 4404, but the PTY is gone.
    expect(ptyHandleIsStale(1, 'pty_a', [])).toBe(true)
    expect(ptyHandleIsStale(3, 'pty_a', ['pty_b'])).toBe(true)
  })

  it('keeps the handle when the PTY survived a plain socket drop', () => {
    expect(ptyHandleIsStale(1, 'pty_a', ['pty_a'])).toBe(false)
  })

  it('has nothing to drop without a handle', () => {
    expect(ptyHandleIsStale(2, null, [])).toBe(false)
  })
})

describe('isRespawn', () => {
  it('is a respawn when a hydrated terminal finds no live PTY', () => {
    expect(isRespawn(0, true)).toBe(true)
  })

  it('is a fresh terminal (no notice) on the very first connect', () => {
    expect(isRespawn(0, false)).toBe(false)
  })

  it('is not a respawn when the PTY survived', () => {
    expect(isRespawn(1, true)).toBe(false)
  })
})
