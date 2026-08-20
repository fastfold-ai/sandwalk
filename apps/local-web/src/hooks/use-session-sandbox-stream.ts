import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { BackendHealth, SessionSandboxStatus } from '@sandwalk/agent-ui-core'
import { isSessionGroupId } from '@sandwalk/agent-ui-core'
import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useEffect
} from 'react'

import type { SandboxActionPhase } from '@/components/agents/Composer'
import { isDraftAgentSessionId } from '@/lib/draft-agent'

import { syncSandboxPhaseFromStatus } from './session-sandbox-status-sync'

export function useSessionSandboxStream({
  client,
  health,
  sessionId,
  sandboxBackend,
  sandboxActionSessionRef,
  setSessionSandboxStatus,
  setSessionSandboxPhase
}: {
  client: LocalAgentClient
  health: BackendHealth | null
  sessionId: string | null
  sandboxBackend?: string | null
  sandboxActionSessionRef: MutableRefObject<string | null>
  setSessionSandboxStatus: Dispatch<SetStateAction<SessionSandboxStatus | null>>
  setSessionSandboxPhase: Dispatch<SetStateAction<SandboxActionPhase>>
}) {
  useEffect(() => {
    // Group ids arrive here only via defensive paths; the group's child
    // chats each own their own sandbox stream. Opening a WS to
    // /sessions/grp_*/sandbox/stream 404s and burns reconnect budget.
    // S2: `term_*` ids también deben skipearse — terminales no tienen
    // sandbox (viven en su propio endpoint /v1/terminals/:id).
    if (
      !sessionId ||
      !health ||
      isDraftAgentSessionId(sessionId) ||
      isSessionGroupId(sessionId) ||
      sessionId.startsWith('term_')
    ) {
      setSessionSandboxStatus(null)
      setSessionSandboxPhase('idle')
      sandboxActionSessionRef.current = null
      return
    }
    if (sandboxActionSessionRef.current !== sessionId) {
      setSessionSandboxPhase('idle')
    }
    let cancelled = false
    let socket: WebSocket | null = null
    let reconnectTimer: number | null = null
    let reconnectDelayMs = 1000
    let hardFailures = 0

    const applyStatus = (status: SessionSandboxStatus) => {
      if (cancelled) return
      setSessionSandboxStatus(status)
      syncSandboxPhaseFromStatus(
        status,
        sessionId,
        sandboxActionSessionRef,
        setSessionSandboxPhase
      )
    }

    const refresh = () => {
      void client
        .getSessionSandbox(sessionId)
        .then(status => {
          if (!cancelled) applyStatus(status)
        })
        .catch(() => {
          if (!cancelled) setSessionSandboxStatus(null)
        })
    }

    const connect = () => {
      if (cancelled) return
      try {
        socket?.close()
      } catch {
        // ignore
      }
      const ws = new WebSocket(client.sandboxStreamUrl(sessionId))
      socket = ws
      ws.onopen = () => {
        reconnectDelayMs = 1000
        hardFailures = 0
        refresh()
      }
      ws.onmessage = event => {
        try {
          const payload = JSON.parse(String(event.data)) as SessionSandboxStatus & {
            type?: string
          }
          if (payload?.sessionId) applyStatus(payload)
        } catch {
          // ignore malformed frames
        }
      }
      ws.onclose = event => {
        if (cancelled) return
        if (event.code === 1006 || event.code === 4401 || event.code === 1011) {
          hardFailures += 1
          reconnectDelayMs = Math.min(
            Math.max(reconnectDelayMs, 2000) * 2,
            hardFailures >= 5 ? 30000 : 15000
          )
        }
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = null
          connect()
        }, reconnectDelayMs)
        if (!(event.code === 1006 || event.code === 4401 || event.code === 1011)) {
          reconnectDelayMs = Math.min(reconnectDelayMs * 2, 8000)
        }
      }
      ws.onerror = () => {
        try {
          ws.close()
        } catch {
          // ignore
        }
      }
    }

    refresh()
    connect()
    return () => {
      cancelled = true
      if (reconnectTimer != null) window.clearTimeout(reconnectTimer)
      try {
        socket?.close()
      } catch {
        // ignore
      }
    }
  }, [
    client,
    health,
    sessionId,
    sandboxActionSessionRef,
    sandboxBackend,
    setSessionSandboxPhase,
    setSessionSandboxStatus
  ])
}
