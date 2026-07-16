import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession } from '@sandwalk/agent-ui-core'
import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useCallback,
  useEffect} from 'react'

import { buildSendContent } from '@/lib/chat-actions'
import type { SessionChatState } from '@/lib/sessions'

/** Soft warn: live SSE streams start crowding the browser's ~6 conn/host limit. */
const CONCURRENT_RUN_SOFT_LIMIT = 3
/** Hard confirm: starting another run is likely to stall files/chat. */
const CONCURRENT_RUN_HARD_LIMIT = 5

type UseSessionChatSendArgs = {
  client: LocalAgentClient
  sessionId: string | null
  sessions: AgentSession[]
  runActive: boolean
  composer: string
  composerSkills: string[]
  composerFiles: string[]
  composerLiveRef: MutableRefObject<string>
  queuedMessages: SessionChatState['queuedMessages']
  editingQueuedId: string | null
  setEditingQueuedId: Dispatch<SetStateAction<string | null>>
  pendingImmediateSendRef: MutableRefObject<{
    sessionId: string
    text: string
  } | null>
  drainingQueueRef: MutableRefObject<boolean>
  chatBySessionIdRef: MutableRefObject<Record<string, SessionChatState>>
  patchChat: (
    id: string,
    patch:
      | Partial<SessionChatState>
      | ((prev: SessionChatState) => SessionChatState)
  ) => void
  setSessions: Dispatch<SetStateAction<AgentSession[]>>
  setError: Dispatch<SetStateAction<string | null>>
  setConnectionLimitDismissed: Dispatch<SetStateAction<boolean>>
}

export function useSessionChatSend({
  client,
  sessionId,
  sessions,
  runActive,
  composer,
  composerSkills,
  composerFiles,
  composerLiveRef,
  queuedMessages,
  editingQueuedId,
  setEditingQueuedId,
  pendingImmediateSendRef,
  drainingQueueRef,
  chatBySessionIdRef,
  patchChat,
  setSessions,
  setError,
  setConnectionLimitDismissed
}: UseSessionChatSendArgs) {
  const sendMessage = async (composerOverride?: string) => {
    const composerText = composerOverride ?? composerLiveRef.current ?? composer
    const content = buildSendContent({
      composerText,
      composerSkills,
      composerFiles
    })
    if (!sessionId || !content || runActive) return
    const othersRunning = sessions.filter(
      item => item.status === 'running' && item.id !== sessionId
    ).length
    if (othersRunning + 1 >= CONCURRENT_RUN_HARD_LIMIT) {
      const proceed = window.confirm(
        `You already have ${othersRunning} agent${
          othersRunning === 1 ? '' : 's'
        } running. Browsers allow about 6 live connections to the local API, so files and chat can freeze with this many concurrent runs.\n\nStart another run anyway?`
      )
      if (!proceed) return
    } else if (othersRunning + 1 >= CONCURRENT_RUN_SOFT_LIMIT) {
      setConnectionLimitDismissed(false)
    }
    const targetSessionId = sessionId
    const previousComposer = composerText
    const previousSkills = composerSkills
    const previousFiles = composerFiles
    composerLiveRef.current = ''
    patchChat(targetSessionId, {
      composer: '',
      composerSkills: [],
      composerFiles: []
    })
    setError(null)
    try {
      await client.sendMessage(targetSessionId, content)
      patchChat(targetSessionId, prev => ({
        ...prev,
        runActive: true
      }))
      setSessions(current =>
        current.map(item =>
          item.id === targetSessionId
            ? { ...item, status: 'running' as const }
            : item
        )
      )
      const history = await client.listMessages(targetSessionId)
      patchChat(targetSessionId, prev => ({
        ...prev,
        messages: history,
        messagesLoaded: true
      }))
    } catch (cause) {
      composerLiveRef.current = previousComposer
      patchChat(targetSessionId, {
        composer: previousComposer,
        composerSkills: previousSkills,
        composerFiles: previousFiles
      })
      setError(
        cause instanceof Error ? cause.message : 'Unable to send message'
      )
    }
  }

  const clearComposerDraft = useCallback(
    (id: string) => {
      composerLiveRef.current = ''
      patchChat(id, {
        composer: '',
        composerSkills: [],
        composerFiles: []
      })
    },
    [patchChat]
  )

  const handleComposerSend = (text: string) => {
    if (!sessionId) return
    const trimmed = text.trim()
    if (!trimmed) return

    if (editingQueuedId) {
      patchChat(sessionId, prev => ({
        ...prev,
        queuedMessages: prev.queuedMessages.map(item =>
          item.id === editingQueuedId ? { ...item, text } : item
        )
      }))
      setEditingQueuedId(null)
      clearComposerDraft(sessionId)
      return
    }

    if (runActive) {
      patchChat(sessionId, prev => ({
        ...prev,
        queuedMessages: [
          ...prev.queuedMessages,
          { id: crypto.randomUUID(), text }
        ]
      }))
      clearComposerDraft(sessionId)
      return
    }

    void sendMessage(text)
  }

  const editQueuedMessage = (id: string) => {
    if (!sessionId) return
    const item = queuedMessages.find(message => message.id === id)
    if (!item) return
    setEditingQueuedId(id)
    composerLiveRef.current = item.text
    patchChat(sessionId, {
      composer: item.text,
      composerSkills: [],
      composerFiles: []
    })
  }

  const cancelEditQueuedMessage = () => {
    if (!sessionId) {
      setEditingQueuedId(null)
      return
    }
    setEditingQueuedId(null)
    clearComposerDraft(sessionId)
  }

  const removeQueuedMessage = (id: string) => {
    if (!sessionId) return
    if (editingQueuedId === id) {
      setEditingQueuedId(null)
      clearComposerDraft(sessionId)
    }
    patchChat(sessionId, prev => ({
      ...prev,
      queuedMessages: prev.queuedMessages.filter(item => item.id !== id)
    }))
  }

  const sendQueuedMessageNow = (id: string) => {
    if (!sessionId) return
    const item = queuedMessages.find(message => message.id === id)
    if (!item) return
    if (editingQueuedId === id) {
      setEditingQueuedId(null)
      clearComposerDraft(sessionId)
    }
    patchChat(sessionId, prev => ({
      ...prev,
      queuedMessages: prev.queuedMessages.filter(message => message.id !== id)
    }))
    if (runActive) {
      pendingImmediateSendRef.current = {
        sessionId,
        text: item.text
      }
      void client.interrupt(sessionId)
      return
    }
    void sendMessage(item.text)
  }

  useEffect(() => {
    if (!sessionId || runActive || drainingQueueRef.current) return

    const pending = pendingImmediateSendRef.current
    if (pending && pending.sessionId === sessionId) {
      pendingImmediateSendRef.current = null
      drainingQueueRef.current = true
      void sendMessage(pending.text).finally(() => {
        drainingQueueRef.current = false
      })
      return
    }

    const queued =
      chatBySessionIdRef.current[sessionId]?.queuedMessages ?? []
    if (queued.length === 0) return
    const next = queued[0]
    drainingQueueRef.current = true
    patchChat(sessionId, prev => ({
      ...prev,
      queuedMessages: prev.queuedMessages.filter(item => item.id !== next.id)
    }))
    void sendMessage(next.text).finally(() => {
      drainingQueueRef.current = false
    })
    // Drain when a run finishes or when the queue gains items while idle.
    // sendMessage intentionally omitted from deps (closes over session state).
  }, [runActive, sessionId, queuedMessages.length])

  const handleStop = useCallback(async () => {
    if (!sessionId) return
    // Optimistic clear — do not wait for SSE / live worker (orphaned runs).
    patchChat(sessionId, prev => ({
      ...prev,
      runActive: false,
      activeRunId: null,
      liveDelta: '',
      activeBuildPlan: null
    }))
    setSessions(current =>
      current.map(item =>
        item.id === sessionId && item.status === 'running'
          ? { ...item, status: 'interrupted' as const }
          : item
      )
    )
    try {
      await client.interrupt(sessionId)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to stop the agent'
      )
    }
  }, [client, patchChat, sessionId, setError, setSessions])

  return {
    handleComposerSend,
    handleStop,
    editQueuedMessage,
    cancelEditQueuedMessage,
    removeQueuedMessage,
    sendQueuedMessageNow
  }
}
