import { useEffect, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'

import {
  AUTO_TITLE_FIRST_RESPONSE_THRESHOLD,
  isLowSignalTitle
} from '@/lib/sessions'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentMessage, AgentSession } from '@sandwalk/agent-ui-core'

type AutoTitleArgs = {
  sessionId: string | null
  runActive: boolean
  sessionTitle: string | undefined
  titleSource: AgentSession['titleSource']
  messages: AgentMessage[]
  client: LocalAgentClient
  setSessions: Dispatch<SetStateAction<AgentSession[]>>
}

function isTitlePending(
  source: AgentSession['titleSource'],
  title: string | undefined
): boolean {
  // Missing source (older payloads) — treat as pending so old chats can catch up.
  if (source == null || source === 'pending') return true
  // Heal create bug that marked "Untitled session" as a settled user rename.
  return source === 'user' && isLowSignalTitle(title || '')
}

export function useAppAutoTitle({
  sessionId,
  runActive,
  sessionTitle,
  titleSource,
  messages,
  client,
  setSessions
}: AutoTitleArgs) {
  const autoTitlePassCountRef = useRef<Record<string, number>>({})
  const autoTitleInFlightRef = useRef<Record<string, boolean>>({})
  const prevRunActiveForTitleRef = useRef<Record<string, boolean>>({})

  useEffect(() => {
    if (!sessionId) return
    const justFinished =
      Boolean(prevRunActiveForTitleRef.current[sessionId]) && !runActive
    prevRunActiveForTitleRef.current[sessionId] = runActive
    if (!justFinished || autoTitleInFlightRef.current[sessionId]) return
    const conversationCount = messages.filter(
      message => message.role === 'user' || message.role === 'assistant'
    ).length
    if (conversationCount < AUTO_TITLE_FIRST_RESPONSE_THRESHOLD) return
    if (!isTitlePending(titleSource, sessionTitle)) return
    if ((autoTitlePassCountRef.current[sessionId] || 0) >= 3) return

    autoTitleInFlightRef.current[sessionId] = true
    const titledSessionId = sessionId
    void (async () => {
      try {
        const updated = await client.autoTitleSession(titledSessionId, {
          force: true
        })
        const title = String(updated.title || '').trim()
        if (!title) return
        setSessions(current =>
          current.map(item =>
            item.id === titledSessionId
              ? {
                  ...item,
                  title,
                  titleSource: updated.titleSource ?? item.titleSource,
                  updatedAt: updated.updatedAt
                }
              : item
          )
        )
        autoTitlePassCountRef.current[titledSessionId] =
          (autoTitlePassCountRef.current[titledSessionId] || 0) + 1
      } catch {
        // Best effort; retry on a later completed run.
      } finally {
        autoTitleInFlightRef.current[titledSessionId] = false
      }
    })()
  }, [
    client,
    messages,
    runActive,
    sessionTitle,
    titleSource,
    sessionId,
    setSessions
  ])
}
