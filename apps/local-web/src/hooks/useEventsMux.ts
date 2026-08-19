import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentEvent, BackendHealth } from '@sandwalk/agent-ui-core'
import { useEffect, useMemo, useRef, useState } from 'react'

import {
  dispatchLifecycleSse,
  dispatchTranscriptSse,
  subscribeTranscriptRegistry,
  subscribedTranscriptSessionIds
} from '@/lib/events-mux-registry'

/** Coalesce split-panel mounts so we don't abort EventSource 3× on open. */
const MUX_SESSION_DEBOUNCE_MS = 50

function sessionKeyFrom(ids: string[]): string {
  return [...new Set(ids.filter(Boolean))].sort().join(',')
}

export function useEventsMux({
  client,
  health,
  pinnedSessionIds = []
}: {
  client: LocalAgentClient
  health: BackendHealth | null
  /** Split-view chat ids — always on the mux, focused or not. */
  pinnedSessionIds?: string[]
}) {
  const [registeredKey, setRegisteredKey] = useState(() =>
    subscribedTranscriptSessionIds().join(',')
  )
  const afterBySessionRef = useRef<Record<string, number>>({})
  const pinnedKey = sessionKeyFrom(pinnedSessionIds)
  const sessionKey = useMemo(() => {
    const registered = registeredKey ? registeredKey.split(',') : []
    const pinned = pinnedKey ? pinnedKey.split(',') : []
    return sessionKeyFrom([...pinned, ...registered])
  }, [pinnedKey, registeredKey])

  useEffect(
    () =>
      subscribeTranscriptRegistry(() => {
        setRegisteredKey(subscribedTranscriptSessionIds().join(','))
      }),
    []
  )

  const enabled = Boolean(health?.capabilities?.eventMux)

  useEffect(() => {
    if (!enabled) return
    const sessionIds = sessionKey ? sessionKey.split(',').filter(Boolean) : []
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void client
        .streamMuxEvents({
          sessionIds,
          afterBySession: afterBySessionRef.current,
          signal: controller.signal,
          onFrame: frame => {
            if (frame.channel === 'transcript' && frame.sessionId) {
              const event = frame.event as unknown as AgentEvent
              if (typeof event.sequence === 'number' && event.sequence > 0) {
                const prev = afterBySessionRef.current[frame.sessionId] || 0
                if (event.sequence > prev) {
                  afterBySessionRef.current[frame.sessionId] = event.sequence
                }
              }
              dispatchTranscriptSse(frame.sessionId, event)
              return
            }
            if (frame.channel === 'lifecycle') {
              const event = frame.event as {
                sequence: number
                type: string
                timestamp: number
                payload: Record<string, unknown>
              }
              dispatchLifecycleSse(event)
            }
          }
        })
        .catch(() => {
          // Reconnect is owned by the next effect run (id list / health change).
        })
    }, MUX_SESSION_DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [client, enabled, sessionKey])
}
