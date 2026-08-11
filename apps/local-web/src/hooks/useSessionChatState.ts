import { useCallback, useEffect, useRef, useState } from 'react'

import {
  applyChatPatch,
  normalizeSessionChatState
} from '@/lib/chat-actions'
import { emptySessionChatState, type SessionChatState } from '@/lib/sessions'

export function useSessionChatState(sessionId: string | null) {
  const [chatBySessionId, setChatBySessionId] = useState<
    Record<string, SessionChatState>
  >({})

  const chat = normalizeSessionChatState(
    sessionId
      ? chatBySessionId[sessionId] ?? emptySessionChatState()
      : emptySessionChatState()
  )
  const {
    messages,
    tools,
    todosByRunId,
    plansByRunId,
    runIdByMessageId,
    usageByRunId,
    tokenUsage,
    activeRunId,
    runActive,
    liveDelta,
    composer,
    composerSkills,
    composerFiles,
    queuedMessages,
    expandedToolRunKeys,
    messagesLoaded,
    activeBuildPlan,
    builtPlanPaths,
    pendingApproval,
    approvalSubmitting
  } = chat

  const composerLiveRef = useRef(composer)
  useEffect(() => {
    composerLiveRef.current = composer
  }, [composer, sessionId])

  const [editingQueuedId, setEditingQueuedId] = useState<string | null>(null)
  const pendingImmediateSendRef = useRef<{
    sessionId: string
    text: string
  } | null>(null)
  const drainingQueueRef = useRef(false)

  useEffect(() => {
    setEditingQueuedId(null)
  }, [sessionId])

  const patchChat = useCallback(
    (
      id: string,
      patch:
        | Partial<SessionChatState>
        | ((prev: SessionChatState) => SessionChatState)
    ) => {
      setChatBySessionId(current => {
        const prev = current[id] ?? emptySessionChatState()
        const next = applyChatPatch(prev, patch)
        if (next === prev) return current
        return { ...current, [id]: next }
      })
    },
    []
  )

  const chatBySessionIdRef = useRef(chatBySessionId)
  chatBySessionIdRef.current = chatBySessionId

  const setComposer = useCallback(
    (value: string | ((current: string) => string)) => {
      if (!sessionId) return
      patchChat(sessionId, prev => {
        const next =
          typeof value === 'function'
            ? value(composerLiveRef.current)
            : value
        composerLiveRef.current = next
        return {
          ...prev,
          composer: next
        }
      })
    },
    [patchChat, sessionId]
  )

  const setComposerSkills = useCallback(
    (value: string[] | ((current: string[]) => string[])) => {
      if (!sessionId) return
      patchChat(sessionId, prev => ({
        ...prev,
        composerSkills:
          typeof value === 'function' ? value(prev.composerSkills) : value
      }))
    },
    [patchChat, sessionId]
  )

  const setComposerFiles = useCallback(
    (value: string[] | ((current: string[]) => string[])) => {
      if (!sessionId) return
      patchChat(sessionId, prev => ({
        ...prev,
        composerFiles:
          typeof value === 'function' ? value(prev.composerFiles) : value
      }))
    },
    [patchChat, sessionId]
  )

  return {
    chatBySessionId,
    setChatBySessionId,
    chatBySessionIdRef,
    patchChat,
    chat,
    messages,
    tools,
    todosByRunId,
    plansByRunId,
    runIdByMessageId,
    usageByRunId,
    tokenUsage,
    activeRunId,
    runActive,
    liveDelta,
    composer,
    composerSkills,
    composerFiles,
    queuedMessages,
    expandedToolRunKeys,
    messagesLoaded,
    activeBuildPlan,
    builtPlanPaths,
    pendingApproval,
    approvalSubmitting,
    setComposer,
    setComposerSkills,
    setComposerFiles,
    composerLiveRef,
    editingQueuedId,
    setEditingQueuedId,
    pendingImmediateSendRef,
    drainingQueueRef
  }
}
