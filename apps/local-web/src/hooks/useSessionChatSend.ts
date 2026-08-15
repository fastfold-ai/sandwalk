import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession } from '@sandwalk/agent-ui-core'
import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useCallback,
  useEffect,
  useRef
} from 'react'

import { buildSendContent, finalizePendingTools } from '@/lib/chat-actions'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import { isSessionBusyError } from '@/lib/session-busy'
import type { SessionChatState } from '@/lib/sessions'

/**
 * Retries `client.sendMessage` on `409 SessionBusyError` with short
 * backoff. Motivation: the backend's `_active_runs[sessionId]` entry is
 * cleared by an asyncio done_callback that runs slightly after the SSE
 * `run.completed` event reaches the UI. If the user hits send in that
 * ~100ms window, the backend still sees a "busy" task and rejects.
 * Retrying twice (300 ms + 600 ms) covers that gap without touching the
 * run lifecycle. If it still fails after the retries, the original 409
 * bubbles up as a real error.
 */
async function sendMessageWithBusyRetry(
  client: LocalAgentClient,
  sessionId: string,
  content: string
): Promise<void> {
  const delaysMs = [300, 600]
  for (let attempt = 0; ; attempt += 1) {
    try {
      await client.sendMessage(sessionId, content)
      return
    } catch (cause) {
      const isBusy =
        cause instanceof Error && / 409:/.test(cause.message)
      if (!isBusy || attempt >= delaysMs.length) throw cause
      await new Promise(resolve => window.setTimeout(resolve, delaysMs[attempt]))
    }
  }
}

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
  const runActiveRef = useRef(runActive)
  runActiveRef.current = runActive
  const sendingRef = useRef(new Set<string>())

  const queueFollowUp = (id: string, text: string) => {
    patchChat(id, prev => ({
      ...prev,
      runActive: true,
      queuedMessages: prev.queuedMessages.some(item => item.text === text)
        ? prev.queuedMessages
        : [...prev.queuedMessages, { id: crypto.randomUUID(), text }]
    }))
  }

  const sendMessage = async (composerOverride?: string) => {
    const composerText = composerOverride ?? composerLiveRef.current ?? composer
    const content = buildSendContent({
      composerText,
      composerSkills,
      composerFiles
    })
    if (!content) return
    const existingId =
      sessionId && !isDraftAgentSessionId(sessionId) ? sessionId : null
    if (
      runActiveRef.current ||
      (existingId && sendingRef.current.has(existingId))
    ) {
      if (existingId) {
        queueFollowUp(existingId, composerText)
        composerLiveRef.current = ''
        patchChat(existingId, {
          composer: '',
          composerSkills: [],
          composerFiles: []
        })
      }
      return
    }
    if (existingId) sendingRef.current.add(existingId)
    const targetSessionId = await ensureAgentSession()
    if (!targetSessionId || isDraftAgentSessionId(targetSessionId)) {
      if (existingId) sendingRef.current.delete(existingId)
      return
    }
    if (existingId && existingId !== targetSessionId) {
      sendingRef.current.delete(existingId)
    }
    if (
      sendingRef.current.has(targetSessionId) &&
      existingId !== targetSessionId
    ) {
      queueFollowUp(targetSessionId, composerText)
      composerLiveRef.current = ''
      patchChat(targetSessionId, {
        composer: '',
        composerSkills: [],
        composerFiles: []
      })
      return
    }
    sendingRef.current.add(targetSessionId)
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
      // Retry on 409 SessionBusyError: when the user hits send right
      // after a previous run completed, there's a small window where
      // the SSE `run.completed` reached the UI (runActive is false in
      // the sidebar) but the backend's asyncio.Task hasn't yet run its
      // done_callback that clears `_active_runs[sessionId]`. Retries
      // with short backoff cover that gap without changing anything
      // about the run lifecycle.
      await sendMessageWithBusyRetry(client, targetSessionId, content)
      const history = await client.listMessages(targetSessionId)
      patchChat(targetSessionId, prev => ({
        ...prev,
        messages: history,
        messagesLoaded: true,
        runActive: true
      }))
    } catch (cause) {
      const message =
        cause instanceof Error ? cause.message : 'Unable to send message'
      if (isSessionBusyError(message)) {
        queueFollowUp(targetSessionId, previousComposer)
        setSessions(current =>
          current.map(item =>
            item.id === targetSessionId
              ? { ...item, status: 'running' as const }
              : item
          )
        )
        return
      }
      composerLiveRef.current = previousComposer
      patchChat(targetSessionId, {
        composer: previousComposer,
        composerSkills: previousSkills,
        composerFiles: previousFiles,
        runActive: false
      })
      setError(message)
    } finally {
      sendingRef.current.delete(targetSessionId)
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

    if (
      (runActiveRef.current || sendingRef.current.has(sessionId)) &&
      !isDraftAgentSessionId(sessionId)
    ) {
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
