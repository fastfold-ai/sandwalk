import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentEvent, AgentSession } from '@sandwalk/agent-ui-core'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { reduceChatOnAgentEvent } from '@/lib/chat-actions'
import { registerTranscriptSseHandler } from '@/lib/events-mux-registry'
import {
  emptySessionChatState,
  type SessionChatState
} from '@/lib/sessions'

function sendErrorMessage(cause: unknown) {
  return cause instanceof Error ? cause.message : 'Capy could not send that message.'
}

export function useCapySession({
  client,
  enabled
}: {
  client: LocalAgentClient
  enabled: boolean
}) {
  const [session, setSession] = useState<AgentSession | null>(null)
  const [chat, setChat] = useState<SessionChatState>(emptySessionChatState)
  const sessionRef = useRef<AgentSession | null>(null)
  const hydrateRef = useRef<Promise<AgentSession> | null>(null)
  sessionRef.current = session

  const ensureSession = () => {
    if (sessionRef.current) return Promise.resolve(sessionRef.current)
    if (!hydrateRef.current) {
      hydrateRef.current = client.getCapySession().then(next => {
        sessionRef.current = next
        setSession(next)
        void client.listMessages(next.id).then(messages => {
          setChat(prev => {
            if (prev.messages.length > 0) {
              return { ...prev, messagesLoaded: true }
            }
            return {
              ...emptySessionChatState(),
              messages,
              messagesLoaded: true,
              composer: prev.composer
            }
          })
        })
        return next
      })
      hydrateRef.current.catch(() => {
        hydrateRef.current = null
      })
    }
    return hydrateRef.current
  }

  useEffect(() => {
    hydrateRef.current = null
    if (!enabled) return
    void ensureSession().catch(cause => {
      toast.error(sendErrorMessage(cause))
    })
  }, [client, enabled])

  useEffect(() => {
    if (!session?.id || !enabled) return
    return registerTranscriptSseHandler(session.id, (event: AgentEvent) => {
      setChat(prev => reduceChatOnAgentEvent(prev, event))
    })
  }, [session?.id, enabled])

  const send = async (
    content: string,
    options?: { source?: 'voice' | 'text'; speakHint?: string }
  ) => {
    const text = content.trim()
    if (!text) return
    const outbound = options?.speakHint
      ? `${text}\n\n${options.speakHint}`
      : text
    let current: AgentSession
    try {
      current = await ensureSession()
    } catch (cause) {
      toast.error(sendErrorMessage(cause))
      return
    }
    setChat(prev => ({
      ...prev,
      messages: [
        ...prev.messages,
        {
          id: `local-${Date.now()}`,
          sessionId: current.id,
          role: 'user',
          content: outbound,
          createdAt: new Date().toISOString()
        }
      ],
      composer: '',
      runActive: true,
      liveDelta: ''
    }))
    try {
      await client.sendMessage(current.id, outbound)
    } catch (cause) {
      toast.error(sendErrorMessage(cause))
      setChat(prev => ({ ...prev, runActive: false }))
    }
  }

  const stop = async () => {
    const current = sessionRef.current
    if (!current) return
    await client.interrupt(current.id)
  }

  const reset = async () => {
    const current = sessionRef.current
    if (!current) return
    const next = await client.resetCapySession()
    sessionRef.current = next
    hydrateRef.current = Promise.resolve(next)
    setSession(next)
    setChat({ ...emptySessionChatState(), messagesLoaded: true })
  }

  return { session, setSession, chat, send, stop, reset, setChat }
}
