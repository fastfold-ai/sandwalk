import { describe, expect, it } from 'vitest'

import {
  LOCAL_SERVER_START_GRACE_MS,
  shouldShowLocalServerStarting
} from './local-server-wait'

describe('shouldShowLocalServerStarting', () => {
  it('shows wait copy while the first local connect is in flight', () => {
    expect(
      shouldShowLocalServerStarting({
        local: true,
        connecting: true,
        unavailable: false,
        elapsedMs: 0,
        desktopState: null
      })
    ).toBe(true)
  })

  it('keeps waiting through a local unreachable error inside the grace window', () => {
    expect(
      shouldShowLocalServerStarting({
        local: true,
        connecting: false,
        unavailable: true,
        elapsedMs: 5_000,
        desktopState: null
      })
    ).toBe(true)
  })

  it('falls through to the error card after grace when desktop is running', () => {
    expect(
      shouldShowLocalServerStarting({
        local: true,
        connecting: false,
        unavailable: true,
        elapsedMs: LOCAL_SERVER_START_GRACE_MS + 1,
        desktopState: 'running'
      })
    ).toBe(false)
  })

  it('keeps waiting while the helper reports starting even after grace', () => {
    expect(
      shouldShowLocalServerStarting({
        local: true,
        connecting: false,
        unavailable: true,
        elapsedMs: LOCAL_SERVER_START_GRACE_MS + 1,
        desktopState: 'starting'
      })
    ).toBe(true)
  })

  it('shows the error immediately when the helper has failed', () => {
    expect(
      shouldShowLocalServerStarting({
        local: true,
        connecting: true,
        unavailable: true,
        elapsedMs: 100,
        desktopState: 'failed'
      })
    ).toBe(false)
  })

  it('never treats a remote backend as starting', () => {
    expect(
      shouldShowLocalServerStarting({
        local: false,
        connecting: true,
        unavailable: true,
        elapsedMs: 0,
        desktopState: 'starting'
      })
    ).toBe(false)
  })
})
