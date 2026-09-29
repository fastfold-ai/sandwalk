import type { Dispatch, MutableRefObject, ReactNode, SetStateAction } from 'react'
import { useMemo } from 'react'

import {
  type ChatBySessionId,
  chatBySessionIdRef,
  useChatStoreZ
} from '@/hooks/chat-store'
import { normalizeSessionChatState } from '@/lib/chat-actions'
import { emptySessionChatState, type SessionChatState } from '@/lib/sessions'

/**
 * Store global del chat por sesión, consumido por todos los mounts vía
 * `useChatStore` — importante para split view: N `SessionChatMount`
 * comparten historial, prefetch cruzado y el stream SSE.
 *
 * The state itself lives in the Zustand store (`chat-store.ts`). This hook
 * hands out the *stable* actions and a ref-shaped reader without
 * subscribing to the map, so callers do not re-render on every token. For
 * reactive reads use `useSessionChatSlice(sessionId)` (one pane) or
 * `useChatActivity()` (shell-level flags).
 */

type ChatStore = {
  setChatBySessionId: Dispatch<SetStateAction<ChatBySessionId>>
  chatBySessionIdRef: MutableRefObject<ChatBySessionId>
  patchChat: (
    id: string,
    patch:
      | Partial<SessionChatState>
      | ((prev: SessionChatState) => SessionChatState)
  ) => void
  /** Normalized snapshot for a session id — non-reactive (reads the store). */
  selectChat: (sessionId: string | null) => SessionChatState
}

/** Kept for call-site compatibility; the store is module-global now. */
export function ChatStoreProvider({ children }: { children: ReactNode }) {
  return children
}

export function useChatStore(): ChatStore {
  const setChatBySessionId = useChatStoreZ(state => state.setChatBySessionId)
  const patchChat = useChatStoreZ(state => state.patchChat)
  return useMemo<ChatStore>(
    () => ({
      setChatBySessionId,
      chatBySessionIdRef,
      patchChat,
      selectChat: (sessionId: string | null) =>
        normalizeSessionChatState(
          sessionId
            ? useChatStoreZ.getState().chatBySessionId[sessionId] ??
                emptySessionChatState()
            : emptySessionChatState()
        )
    }),
    [patchChat, setChatBySessionId]
  )
}
