import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession } from '@sandwalk/agent-ui-core'
import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useCallback,
  useEffect} from 'react'

import { buildSendContent, finalizePendingTools } from '@/lib/chat-actions'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import type { SessionChatState } from '@/lib/sessions'

type UseSessionChatSendArgs = {
  client: LocalAgentClient
  sessionId: string | null
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
  ensureAgentSession: (
    projectId?: string | null,
    options?: { navigate?: boolean }
  ) => Promise<string | null>
  /**
   * Populated by `usePerSessionChatState` / `useAppSessionLayer` after
   * `useChatScroll` runs (declaration-order forces this indirection). We
   * call it right after the optimistic composer clear so the user's own
   * message and the incoming stream stay in view — the auto-scroll
   * ResizeObserver alone doesn't fire soon enough on a freshly-mounted
   * split panel that lost `stickToBottom`.
   */
  scrollChatToBottomRef?: MutableRefObject<(() => void) | null>
}

export function useSessionChatSend({
  client,
  sessionId,
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
  ensureAgentSession,
  scrollChatToBottomRef
}: UseSessionChatSendArgs) {
  const sendMessage = async (composerOverride?: string) => {
    const composerText = composerOverride ?? composerLiveRef.current ?? composer
    const content = buildSendContent({
      composerText,
      composerSkills,
      composerFiles
    })
    if (!content || runActive) return
    const targetSessionId = await ensureAgentSession()
    if (!targetSessionId || isDraftAgentSessionId(targetSessionId)) return
    const previousComposer = composerText
    const previousSkills = composerSkills
    const previousFiles = composerFiles
    composerLiveRef.current = ''
    // Optimistic: dock the composer immediately so draft → chat does not wait
    // on the network round-trip before the layout animates.
    patchChat(targetSessionId, {
      composer: '',
      composerSkills: [],
      composerFiles: [],
      runActive: true,
      messagesLoaded: true
    })
    // Pin the transcript to the bottom on the next frame — the user's own
    // message pushes the content past the fold, and if `stickToBottom` was
    // false (common after split-mount when layout wasn't stable) the
    // upcoming SSE deltas won't scroll on their own. Ref-based so send
    // hook can be declared before scroll hook without a circular dep.
    if (scrollChatToBottomRef?.current) {
      const scroll = scrollChatToBottomRef.current
      window.requestAnimationFrame(() => scroll())
    }
    setSessions(current =>
      current.map(item =>
        item.id === targetSessionId
          ? { ...item, status: 'running' as const }
          : item
      )
    )
    setError(null)
    try {
      await client.sendMessage(targetSessionId, content)
      const history = await client.listMessages(targetSessionId)
      patchChat(targetSessionId, prev => ({
        ...prev,
        messages: history,
        messagesLoaded: true,
        runActive: true
      }))
    } catch (cause) {
      composerLiveRef.current = previousComposer
      patchChat(targetSessionId, {
        composer: previousComposer,
        composerSkills: previousSkills,
        composerFiles: previousFiles,
        runActive: false
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
    const trimmed = text.trim()
    if (!trimmed) return
    if (!sessionId) return

    if (editingQueuedId && !isDraftAgentSessionId(sessionId)) {
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

    if (runActive && !isDraftAgentSessionId(sessionId)) {
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
    // Clearing runActive also tells the stream hook to ignore zombie deltas
    // from a worker that has not exited yet.
    patchChat(sessionId, prev => ({
      ...prev,
      runActive: false,
      activeRunId: null,
      liveDelta: '',
      pendingApproval: null,
      approvalSubmitting: false,
      activeBuildPlan: null,
      tools: finalizePendingTools(prev.tools, {
        runId: prev.activeRunId,
        reason: 'Interrupted'
      })
    }))
    setSessions(current =>
      current.map(item =>
        item.id === sessionId &&
        (item.status === 'running' || item.status === 'awaiting_approval')
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
