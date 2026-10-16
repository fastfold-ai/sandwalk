import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useSessionChatSlice } from '@/hooks/chat-store'
import { useChatStore } from '@/hooks/chat-store-context'
import { normalizeSessionChatState } from '@/lib/chat-actions'

/**
 * Hook por-sesión que expone el `chatBySessionId` global (vía el
 * `ChatStoreProvider`) más los derivados del sessionId dado y los refs
 * que sí son locales a cada mount (composer live ref, queue refs,
 * editingQueuedId).
 *
 * Split view: N mounts consumen el mismo store global — ven el mismo
 * `chatBySessionId`, se benefician del prefetch cruzado y el stream SSE
 * que llegue por cualquiera actualiza la vista de todos. Los refs locales
 * (composer live, pending immediate send, draining queue) se mantienen
 * por mount porque son mecanismos de la vista de un panel, no del chat.
 */

export function useSessionChatState(sessionId: string | null) {
  const store = useChatStore()
  const { setChatBySessionId, chatBySessionIdRef, patchChat } = store

  // Reactive read of THIS session only — other panes' tokens do not
  // re-render this mount.
  const slice = useSessionChatSlice(sessionId)
  const chat = useMemo(() => normalizeSessionChatState(slice), [slice])
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
    liveStatus,
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
    liveStatus,
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
