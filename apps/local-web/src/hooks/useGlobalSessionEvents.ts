/**
 * Single SSE subscription to the backend's global session-lifecycle
 * channel. Applies patches directly to `sessions` and drives OS-level
 * attention (Dock badge + notifications).
 *
 * Replaces the previous approach where `useAppSessionLayer` inferred
 * status transitions by diffing snapshots from a 2s poll. That inference
 * fired false positives whenever two independent fetches (loadSessions +
 * loadForeignSessions) surfaced overlapping-but-stale views of the same
 * chat, causing already-read chats to re-mark as "unread".
 *
 * Coordination with the per-session token SSE (useSessionChatStream):
 * that stream is authoritative for the ACTIVE chat's transcript deltas
 * and also updates its status locally. The global stream covers every
 * OTHER chat. To avoid double-notifying, we skip attention marks for
 * events whose `sessionId` matches the current `sessionIdRef` — that
 * chat's dedicated stream already handles it.
 */

import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  BackendHealth
} from '@sandwalk/agent-ui-core'
import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useEffect
} from 'react'

import {
  notifyApprovalRequired,
  notifyRunCompleted
} from '@/lib/browser-notifications'
import { markSessionAttention } from '@/lib/session-attention'

type UseGlobalSessionEventsArgs = {
  client: LocalAgentClient
  health: BackendHealth | null
  /** Ref to the currently visible chat so we can skip its events (its own
   *  per-session SSE already handles them). */
  sessionIdRef: MutableRefObject<string | null>
  setSessions: Dispatch<SetStateAction<AgentSession[]>>
}

function extractSession(payload: Record<string, unknown>): AgentSession | null {
  const raw = payload.session
  if (!raw || typeof raw !== 'object') return null
  // Trust the backend's shape — it was serialized from the same
  // AgentSession model the client already consumes elsewhere.
  return raw as AgentSession
}

function isBenchSession(session: AgentSession | null): boolean {
  return session?.source === 'bench'
}

function extractSessionId(payload: Record<string, unknown>): string | null {
  const id = payload.sessionId
  return typeof id === 'string' ? id : null
}

export function useGlobalSessionEvents({
  client,
  health,
  sessionIdRef,
  setSessions
}: UseGlobalSessionEventsArgs) {
  useEffect(() => {
    if (!health) return
    const controller = new AbortController()
    void client
      .streamGlobalSessionEvents({
        signal: controller.signal,
        onEvent: event => {
          const payload = event.payload
          const sessionId = extractSessionId(payload)
          const isActiveChat =
            sessionId !== null && sessionIdRef.current === sessionId

          switch (event.type) {
            case 'session.created': {
              const session = extractSession(payload)
              if (!session || isBenchSession(session)) return
              setSessions(current =>
                current.some(s => s.id === session.id)
                  ? current
                  : [session, ...current]
              )
              return
            }
            case 'session.updated':
            case 'session.status_changed': {
              const session = extractSession(payload)
              if (!session || isBenchSession(session)) return
              setSessions(current => {
                let changed = false
                const next = current.map(s => {
                  if (s.id !== session.id) return s
                  if (
                    s.status === session.status &&
                    s.title === session.title &&
                    s.projectId === session.projectId &&
                    s.organizeLabel === session.organizeLabel &&
                    s.updatedAt === session.updatedAt &&
                    s.lastMessageAt === session.lastMessageAt
                  ) {
                    return s
                  }
                  changed = true
                  return session
                })
                if (!changed && !current.some(s => s.id === session.id)) {
                  // Not in cache yet — a foreign chat that just changed.
                  // Append so subsequent lookups resolve it.
                  return [session, ...current]
                }
                return changed ? next : current
              })
              return
            }
            case 'session.deleted': {
              if (!sessionId) return
              setSessions(current => {
                if (!current.some(s => s.id === sessionId)) return current
                return current.filter(s => s.id !== sessionId)
              })
              return
            }
            case 'run.awaiting_approval': {
              if (!sessionId || isActiveChat) return
              const session = extractSession(payload)
              if (isBenchSession(session)) return
              markSessionAttention(sessionId)
              notifyApprovalRequired({
                sessionId,
                sessionTitle: session?.title
              })
              return
            }
            case 'run.completed':
            case 'run.failed': {
              if (!sessionId || isActiveChat) return
              const session = extractSession(payload)
              if (isBenchSession(session)) return
              markSessionAttention(sessionId)
              notifyRunCompleted({
                sessionId,
                sessionTitle: session?.title,
                ok: event.type === 'run.completed'
              })
              return
            }
            // run.started / run.interrupted don't need attention; the
            // status_changed event already syncs the sidebar icon.
            default:
              return
          }
        }
      })
      .catch(() => {
        // Silent failure: safety poll in useAppBootstrapConnect (60s) is
        // the fallback if the global stream can't stay connected.
      })
    return () => controller.abort()
  }, [client, health, sessionIdRef, setSessions])
}
