import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import { create } from 'zustand'

import { applyChatPatch } from '@/lib/chat-actions'
import { emptySessionChatState, type SessionChatState } from '@/lib/sessions'

/**
 * Global per-session chat state (messages, composer, run flags…).
 *
 * Lived in a root `useState` before: every streamed token re-rendered `App`
 * and the whole tree under it, N× in a split. As a Zustand store each pane
 * subscribes to its own session (`useSessionChatSlice`) and the shell to a
 * tiny derived map, so a token repaints one pane.
 */
export type ChatBySessionId = Record<string, SessionChatState>

type ChatStoreState = {
  chatBySessionId: ChatBySessionId
  setChatBySessionId: Dispatch<SetStateAction<ChatBySessionId>>
  patchChat: (
    id: string,
    patch: Partial<SessionChatState> | ((prev: SessionChatState) => SessionChatState)
  ) => void
}

export const useChatStoreZ = create<ChatStoreState>()(set => ({
  chatBySessionId: {},
  setChatBySessionId: updater =>
    set(state => {
      const next =
        typeof updater === 'function' ? updater(state.chatBySessionId) : updater
      return next === state.chatBySessionId ? state : { chatBySessionId: next }
    }),
  patchChat: (id, patch) =>
    set(state => {
      const prev = state.chatBySessionId[id] ?? emptySessionChatState()
      const next = applyChatPatch(prev, patch)
      if (next === prev) return state
      return { chatBySessionId: { ...state.chatBySessionId, [id]: next } }
    })
}))

/**
 * Ref-shaped view of the live map for imperative readers (stream handlers,
 * send queue). Reads always see the latest state; never subscribes.
 */
export const chatBySessionIdRef: MutableRefObject<ChatBySessionId> = {
  get current() {
    return useChatStoreZ.getState().chatBySessionId
  },
  set current(next: ChatBySessionId) {
    useChatStoreZ.getState().setChatBySessionId(next)
  }
}

const EMPTY_CHAT = emptySessionChatState()

/** Subscribe to one session's raw state only (stable empty object when absent). */
export function useSessionChatSlice(sessionId: string | null): SessionChatState {
  return useChatStoreZ(state =>
    sessionId ? state.chatBySessionId[sessionId] ?? EMPTY_CHAT : EMPTY_CHAT
  )
}

/** Reset — tests only. */
export function resetChatStoreForTests(): void {
  useChatStoreZ.setState({ chatBySessionId: {} })
}
