import { useRef } from 'react'

import type { SessionChatState } from '@/lib/sessions'

/**
 * Per-session activity flags the sidebar and tab strip actually render
 * (spinner / approval badge). Derived from the full chat store so those
 * components no longer depend on `chatBySessionId`, whose identity
 * changes on every streamed token of any chat.
 */
export type SessionActivity = {
  runActive: boolean
  pendingApproval: boolean
}

export type SessionActivityMap = Readonly<Record<string, SessionActivity>>

const EMPTY: SessionActivityMap = Object.freeze({})

/**
 * Build the activity map, returning `prev` when nothing observable
 * changed so consumers keep a stable reference.
 */
export function deriveSessionActivity(
  chatBySessionId: Record<string, SessionChatState | undefined>,
  prev: SessionActivityMap = EMPTY
): SessionActivityMap {
  const next: Record<string, SessionActivity> = {}
  let count = 0
  for (const [id, chat] of Object.entries(chatBySessionId)) {
    if (!chat) continue
    const runActive = Boolean(chat.runActive)
    const pendingApproval = Boolean(chat.pendingApproval)
    if (!runActive && !pendingApproval) continue
    next[id] = { runActive, pendingApproval }
    count += 1
  }
  if (count === 0) return EMPTY
  const prevKeys = Object.keys(prev)
  if (prevKeys.length === count) {
    let same = true
    for (const key of prevKeys) {
      const a = prev[key]
      const b = next[key]
      if (
        !b ||
        a.runActive !== b.runActive ||
        a.pendingApproval !== b.pendingApproval
      ) {
        same = false
        break
      }
    }
    if (same) return prev
  }
  return next
}

/** React hook wrapper: stable reference until a flag actually flips. */
export function useSessionActivity(
  chatBySessionId: Record<string, SessionChatState | undefined>
): SessionActivityMap {
  const ref = useRef<SessionActivityMap>(EMPTY)
  ref.current = deriveSessionActivity(chatBySessionId, ref.current)
  return ref.current
}
