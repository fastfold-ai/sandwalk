import type { SessionSandboxStatus } from '@sandwalk/agent-ui-core'
import { describe, expect, it, vi } from 'vitest'

import { syncSandboxPhaseFromStatus } from './session-sandbox-status-sync'

function status(value: SessionSandboxStatus['status']): SessionSandboxStatus {
  return { status: value } as SessionSandboxStatus
}

describe('syncSandboxPhaseFromStatus', () => {
  it('tracks starting and stopping, then clears them when the sandbox is up', () => {
    const ref = { current: null as string | null }
    const setPhase = vi.fn()
    syncSandboxPhaseFromStatus(status('starting'), 's1', ref, setPhase)
    expect(setPhase).toHaveBeenCalledWith('starting')
    expect(ref.current).toBe('s1')
    syncSandboxPhaseFromStatus(status('stopping'), 's1', ref, setPhase)
    expect(setPhase).toHaveBeenCalledWith('stopping')
    syncSandboxPhaseFromStatus(status('running'), 's1', ref, setPhase)
    expect(ref.current).toBeNull()
    expect(setPhase).toHaveBeenCalledWith('idle')
    syncSandboxPhaseFromStatus(status('stopped'), 's1', ref, setPhase)
    expect(setPhase).toHaveBeenLastCalledWith('idle')
  })
})
