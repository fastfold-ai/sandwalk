import { afterEach, describe, expect, it } from 'vitest'

import {
  installPerfProbe,
  perfCount,
  perfReset,
  perfSnapshot,
  perfTrackTerminal
} from './perf-probe'

afterEach(() => {
  perfReset()
  delete window.__sandwalkPerf
})

describe('perf probe', () => {
  it('counts, snapshots, and resets', () => {
    perfCount('gridReady')
    perfCount('gridReady', 2)
    expect(perfSnapshot()).toEqual({ gridReady: 3 })
    perfReset()
    expect(perfSnapshot()).toEqual({})
  })

  it('exposes the probe in dev and tracks terminals', () => {
    installPerfProbe()
    expect(window.__sandwalkPerf?.snapshot()).toEqual({})
    installPerfProbe()
    const term = { buffer: true }
    perfTrackTerminal('t1', term)
    expect(window.__sandwalkPerf?.terminals.get('t1')).toBe(term)
    perfTrackTerminal('t1', null)
    expect(window.__sandwalkPerf?.terminals.has('t1')).toBe(false)
  })
})
