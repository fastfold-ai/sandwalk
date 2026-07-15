import type { SessionSandboxStatus } from '@sandwalk/agent-ui-core'
import type { MutableRefObject } from 'react'

import type { SandboxActionPhase } from '@/components/agents/Composer'

export function syncSandboxPhaseFromStatus(
  status: SessionSandboxStatus,
  sessionId: string,
  sandboxActionSessionRef: MutableRefObject<string | null>,
  setSessionSandboxPhase: (phase: SandboxActionPhase) => void
) {
  if (status.status === 'starting') {
    setSessionSandboxPhase('starting')
    sandboxActionSessionRef.current = sessionId
    return
  }
  if (status.status === 'stopping') {
    setSessionSandboxPhase('stopping')
    sandboxActionSessionRef.current = sessionId
    return
  }
  if (status.status === 'running') {
    if (sandboxActionSessionRef.current === sessionId) {
      sandboxActionSessionRef.current = null
    }
    setSessionSandboxPhase('idle')
    return
  }
  if (
    (status.status === 'stopped' ||
      status.status === 'unavailable' ||
      status.status === 'ready') &&
    sandboxActionSessionRef.current !== sessionId
  ) {
    setSessionSandboxPhase('idle')
  }
}
