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

type GlobalSessionEvent = {
  sequence: number
  type: string
  timestamp: number
  payload: Record<string, unknown>
}

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
  // Cheap runtime guard: the wire format could drift (backend rename,
  // schema migration, older client version). Verifying the two fields
  // the reducer downstream actually reads prevents propagating an
  // undefined-shaped object into `sessions` state and crashing renders.
  const candidate = raw as Record<string, unknown>
  if (
    typeof candidate.id !== 'string' ||
    typeof candidate.status !== 'string'
  ) {
    // eslint-disable-next-line no-console
    console.warn(
      '[useGlobalSessionEvents] dropping session payload with unexpected shape',
      candidate
    )
    return null
  }
  return candidate as unknown as AgentSession
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
    let cancelled = false
    let controller = new AbortController()
    // Exponential backoff between reconnect attempts. Bounded so a
    // permanently-down server doesn't spin, but low enough that a
    // transient blip (uvicorn restart, wifi flap) recovers fast.
    let reconnectDelayMs = 1000
    const RECONNECT_MAX_MS = 30_000
    let reconnectTimer: number | null = null

    const connect = () => {
      if (cancelled) return
      controller = new AbortController()
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
              if (!session) return
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
              if (!session) return
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
              markSessionAttention(sessionId)
              const session = extractSession(payload)
              notifyApprovalRequired({
                sessionId,
                sessionTitle: session?.title
              })
              return
            }
            case 'run.completed':
            case 'run.failed': {
              if (!sessionId || isActiveChat) return
              markSessionAttention(sessionId)
              const session = extractSession(payload)
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
        .then(() => {
          // Stream closed cleanly (server shutdown / graceful eof):
          // reconnect immediately in case the server came back up. The
          // safety poll in `useAppBootstrapConnect` (60s) reconciles
          // whatever we miss in the meantime.
          if (cancelled) return
          reconnectDelayMs = 1000
          reconnectTimer = window.setTimeout(connect, reconnectDelayMs)
        })
        .catch(cause => {
          if (cancelled) return
          // Surface in devtools so a broken channel isn't invisible.
          // eslint-disable-next-line no-console
          console.warn(
            '[useGlobalSessionEvents] stream disconnected, retrying:',
            cause instanceof Error ? cause.message : cause
          )
          reconnectTimer = window.setTimeout(connect, reconnectDelayMs)
          reconnectDelayMs = Math.min(reconnectDelayMs * 2, RECONNECT_MAX_MS)
        })
    }

    connect()

    return () => {
      cancelled = true
      controller.abort()
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }
  }, [client, health, sessionIdRef, setSessions])
}
