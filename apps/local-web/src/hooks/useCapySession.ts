import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentEvent, AgentSession, BackendHealth } from '@sandwalk/agent-ui-core'
import { useEffect, useRef, useState } from 'react'

import { reduceChatOnAgentEvent } from '@/lib/chat-actions'
import { registerTranscriptSseHandler } from '@/lib/events-mux-registry'
import {
  emptySessionChatState,
  type SessionChatState
} from '@/lib/sessions'

export function useCapySession({
  client,
  health,
  enabled
}: {
  client: LocalAgentClient
  health: BackendHealth | null
  enabled: boolean
}) {
  const [session, setSession] = useState<AgentSession | null>(null)
  const [chat, setChat] = useState<SessionChatState>(emptySessionChatState)
  const chatRef = useRef(chat)
  chatRef.current = chat

  useEffect(() => {
    if (!health || !enabled) return
    let cancelled = false
    void client.getCapySession().then(async next => {
      if (cancelled) return
      setSession(next)
      const messages = await client.listMessages(next.id)
      if (cancelled) return
      setChat({
        ...emptySessionChatState(),
        messages,
        messagesLoaded: true
      })
    })
    return () => {
      cancelled = true
    }
  }, [client, health, enabled])

  useEffect(() => {
    if (!session?.id || !enabled) return
    return registerTranscriptSseHandler(session.id, (event: AgentEvent) => {
      setChat(prev => reduceChatOnAgentEvent(prev, event))
    })
  }, [session?.id, enabled])

  const send = async (content: string) => {
    if (!session || !content.trim()) return
    setChat(prev => ({
      ...prev,
      messages: [
        ...prev.messages,
        {
          id: `local-${Date.now()}`,
          sessionId: session.id,
          role: 'user',
          content,
          createdAt: new Date().toISOString()
        }
      ],
      composer: '',
      runActive: true,
      liveDelta: ''
    }))
    await client.sendMessage(session.id, content)
  }

  const stop = async () => {
    if (!session) return
    await client.interrupt(session.id)
  }

  const reset = async () => {
    if (!session) return
    await client.resetCapySession()
    setChat({ ...emptySessionChatState(), messagesLoaded: true })
  }

  return { session, setSession, chat, send, stop, reset, setChat }
}
