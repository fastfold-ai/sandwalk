import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentEvent, BackendHealth } from '@sandwalk/agent-ui-core'
import { useEffect, useRef, useState } from 'react'

import {
  dispatchLifecycleSse,
  dispatchTranscriptSse,
  subscribeTranscriptRegistry,
  subscribedTranscriptSessionIds
} from '@/lib/events-mux-registry'

export function useEventsMux({
  client,
  health
}: {
  client: LocalAgentClient
  health: BackendHealth | null
}) {
  const [sessionKey, setSessionKey] = useState(() =>
    subscribedTranscriptSessionIds().join(',')
  )
  const afterBySessionRef = useRef<Record<string, number>>({})

  useEffect(() => subscribeTranscriptRegistry(() => {
    setSessionKey(subscribedTranscriptSessionIds().join(','))
  }), [])

  const enabled = Boolean(health?.capabilities?.eventMux)

  useEffect(() => {
    if (!health || !enabled) return
    const sessionIds = sessionKey ? sessionKey.split(',').filter(Boolean) : []
    const controller = new AbortController()
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
    return () => controller.abort()
  }, [client, enabled, health, sessionKey])
}
