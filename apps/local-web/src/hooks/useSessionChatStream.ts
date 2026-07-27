import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentEvent,
  AgentSession,
  BackendHealth
} from '@sandwalk/agent-ui-core'
import { type Dispatch, type MutableRefObject, type SetStateAction,useEffect, useRef } from 'react'

import { toolsFromEvents } from '@/components/agents/transcript'
import {
  notifyApprovalRequired,
  notifyRunCompleted
} from '@/lib/browser-notifications'
import { reduceChatOnAgentEvent } from '@/lib/chat-actions'
import { markSessionAttention } from '@/lib/session-attention'
import type { SessionChatState } from '@/lib/sessions'

type UseSessionChatStreamArgs = {
  client: LocalAgentClient
  health: BackendHealth | null
  sessionId: string | null
  sessionIdRef: MutableRefObject<string | null>
  sessions: AgentSession[]
  runningSessionIdsKey: string
  chatBySessionIdRef: MutableRefObject<Record<string, SessionChatState>>
  patchChat: (
    id: string,
    patch:
      | Partial<SessionChatState>
      | ((prev: SessionChatState) => SessionChatState)
  ) => void
  setSessions: Dispatch<SetStateAction<AgentSession[]>>
  setWorkspaceVersion: Dispatch<SetStateAction<number>>
  setError: Dispatch<SetStateAction<string | null>>
  loadSessionsRef: MutableRefObject<
    ((options?: { force?: boolean }) => Promise<void>) | null
  >
  loadSkillsRef: MutableRefObject<(() => Promise<void>) | null>
}

function skillsMutatedFromToolEvent(event: AgentEvent): boolean {
  if (event.type !== 'tool.completed') return false
  const name = event.payload.name
  if (name !== 'skills.manage' && name !== 'skills_manage') return false
  if (event.payload.isError) return false
  const output = event.payload.output
  if (!output || typeof output !== 'object') return false
  const record = output as Record<string, unknown>
  return record.skills_updated === true
}

/** Flush cadence for streamed text deltas (~30fps keeps markdown parse cheap). */
const DELTA_FLUSH_MS = 33

export function useSessionChatStream({
  client,
  health,
  sessionId,
  sessionIdRef,
  sessions,
  runningSessionIdsKey,
  chatBySessionIdRef,
  patchChat,
  setSessions,
  setWorkspaceVersion,
  setError,
  loadSessionsRef,
  loadSkillsRef
}: UseSessionChatStreamArgs) {
  const streamControllersRef = useRef<Map<string, AbortController>>(new Map())

  // Perf probe (visible in devtools): time from last delta to run.completed
  // as *received* by JS — splits webview transport lag from render lag.
  const lastDeltaAtRef = useRef<Map<string, number>>(new Map())

  // Coalesce assistant.delta events: one React state update per flush window
  // instead of one per token. Buffers/timers live in refs so late timer
  // callbacks never see stale closures.
  const deltaBuffersRef = useRef<Map<string, string>>(new Map())
  const deltaTimersRef = useRef<Map<string, number>>(new Map())
  const flushDeltaRef = useRef<(id: string) => void>(() => {})
  flushDeltaRef.current = (id: string) => {
    const timer = deltaTimersRef.current.get(id)
    if (timer !== undefined) {
      window.clearTimeout(timer)
      deltaTimersRef.current.delete(id)
    }
    const text = deltaBuffersRef.current.get(id)
    if (!text) return
    deltaBuffersRef.current.delete(id)
    // Mirrors reduceChatOnAgentEvent's assistant.delta branch.
    patchChat(id, prev => ({ ...prev, liveDelta: prev.liveDelta + text }))
  }
  const queueDelta = (id: string, delta: string) => {
    deltaBuffersRef.current.set(
      id,
      (deltaBuffersRef.current.get(id) || '') + delta
    )
    if (!deltaTimersRef.current.has(id)) {
      deltaTimersRef.current.set(
        id,
        window.setTimeout(() => flushDeltaRef.current(id), DELTA_FLUSH_MS)
      )
    }
  }
  const dropDeltaBuffer = (id: string) => {
    const timer = deltaTimersRef.current.get(id)
    if (timer !== undefined) window.clearTimeout(timer)
    deltaTimersRef.current.delete(id)
    deltaBuffersRef.current.delete(id)
  }

  useEffect(() => {
    if (!health || !sessionId) return
    if (chatBySessionIdRef.current[sessionId]?.messagesLoaded) return

    // Empty/new sessions: show the empty composer immediately, hydrate in background.
    // Menubar "New Agent" navigates here before loadSessions includes the row —
    // treat a missing meta the same as a fresh idle session so we don't sit on
    // a blank main pane waiting for the list poll.
    const meta = sessions.find(item => item.id === sessionId)
    const looksEmpty =
      !meta || (!meta.lastMessageAt && meta.status === 'idle')
    if (looksEmpty) {
      patchChat(sessionId, prev =>
        prev.messagesLoaded
          ? prev
          : { ...prev, messages: [], messagesLoaded: true }
      )
    }

    const controller = new AbortController()
    void Promise.all([
      client.listMessages(sessionId, controller.signal),
      client.listEventHistory(sessionId, controller.signal).catch(() => [])
    ])
      .then(([history, events]) => {
        const derived = toolsFromEvents(events)
        patchChat(sessionId, prev => ({
          ...prev,
          messages: history,
          tools: derived.tools,
          todosByRunId: derived.todosByRunId,
          plansByRunId: derived.plansByRunId,
          runIdByMessageId: {
            ...prev.runIdByMessageId,
            ...derived.runIdByMessageId
          },
          usageByRunId: {
            ...prev.usageByRunId,
            ...derived.usageByRunId
          },
          tokenUsage:
            derived.tokenUsage.inputTokens > 0 ||
            derived.tokenUsage.outputTokens > 0
              ? derived.tokenUsage
              : prev.tokenUsage,
          messagesLoaded: true
        }))
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to load messages'
          )
          patchChat(sessionId, prev =>
            prev.messagesLoaded ? prev : { ...prev, messagesLoaded: true }
          )
        }
      })
    return () => controller.abort()
    // Intentionally omit `sessions` — only re-hydrate when the active session changes.
  }, [client, health, patchChat, sessionId])

  // Cursor per session so intentional stream restarts (and EventSource
  // reconnects that lose Last-Event-ID) don't replay the entire history —
  // that spam-logged run.completed and could leave the UI looking stuck.
  const afterSequenceRef = useRef<Map<string, number>>(new Map())

  useEffect(() => {
    if (!health) {
      for (const [id, controller] of streamControllersRef.current) {
        controller.abort()
        dropDeltaBuffer(id)
      }
      streamControllersRef.current.clear()
      return
    }

    // Only stream the active session + any currently running sessions.
    // An SSE per open tab exhausts the browser's ~6 HTTP/1.1 connections/host,
    // which leaves file content fetches stuck in (pending).
    const wanted = new Set<string>()
    if (sessionId) wanted.add(sessionId)
    for (const id of runningSessionIdsKey.split(',').filter(Boolean)) {
      wanted.add(id)
    }

    for (const [id, controller] of [...streamControllersRef.current]) {
      if (!wanted.has(id)) {
        controller.abort()
        streamControllersRef.current.delete(id)
        dropDeltaBuffer(id)
      }
    }

    for (const id of wanted) {
      if (streamControllersRef.current.has(id)) continue
      const controller = new AbortController()
      streamControllersRef.current.set(id, controller)
      const afterSequence = afterSequenceRef.current.get(id) || 0

      void client
        .streamEvents(id, {
          afterSequence,
          signal: controller.signal,
          onEvent: (event: AgentEvent) => {
            if (typeof event.sequence === 'number' && event.sequence > 0) {
              const prev = afterSequenceRef.current.get(id) || 0
              if (event.sequence > prev) {
                afterSequenceRef.current.set(id, event.sequence)
              }
            }
            if (event.type === 'assistant.delta') {
              lastDeltaAtRef.current.set(id, performance.now())
              queueDelta(id, event.payload.delta)
              return
            }
            if (
              event.type === 'run.completed' ||
              event.type === 'assistant.message'
            ) {
              const lastDelta = lastDeltaAtRef.current.get(id)
              if (lastDelta !== undefined) {
                console.debug(
                  `[perf-ui] ${event.type} received ${(
                    performance.now() - lastDelta
                  ).toFixed(0)}ms after last delta`
                )
              }
            }
            // Any other event flushes buffered deltas first to keep ordering
            // (e.g. run.completed clears liveDelta after the last token).
            flushDeltaRef.current(id)
            patchChat(id, prev => reduceChatOnAgentEvent(prev, event))

            if (skillsMutatedFromToolEvent(event)) {
              void loadSkillsRef.current?.()
            }

            if (event.type === 'run.started') {
              setSessions(current =>
                current.map(item =>
                  item.id === id
                    ? { ...item, status: 'running' as const }
                    : item
                )
              )
              void client.listMessages(id).then(history => {
                patchChat(id, prev => ({
                  ...prev,
                  messages: history,
                  messagesLoaded: true
                }))
              })
            } else if (event.type === 'run.awaiting_approval') {
              setSessions(current => {
                const next = current.map(item =>
                  item.id === id
                    ? { ...item, status: 'awaiting_approval' as const }
                    : item
                )
                const session = next.find(item => item.id === id)
                const first = event.payload.actionRequests?.[0]
                // Dock badge when the user isn't looking at this session.
                if (
                  sessionIdRef.current !== id ||
                  (typeof document !== 'undefined' &&
                    (document.hidden || !document.hasFocus()))
                ) {
                  markSessionAttention(id)
                }
                notifyApprovalRequired({
                  sessionId: id,
                  sessionTitle: session?.title,
                  toolName: first?.name
                })
                return next
              })
            } else if (event.type === 'run.approval_resolved') {
              setSessions(current =>
                current.map(item =>
                  item.id === id
                    ? { ...item, status: 'running' as const }
                    : item
                )
              )
            } else if (event.type === 'session.updated') {
              void loadSessionsRef.current?.()
            } else if (
              event.type === 'run.completed' ||
              event.type === 'run.failed' ||
              event.type === 'run.interrupted'
            ) {
              const nextStatus =
                event.type === 'run.failed'
                  ? ('error' as const)
                  : event.type === 'run.interrupted'
                  ? ('interrupted' as const)
                  : ('idle' as const)
              setSessions(current => {
                const next = current.map(item =>
                  item.id === id ? { ...item, status: nextStatus } : item
                )
                if (
                  event.type === 'run.completed' ||
                  event.type === 'run.failed'
                ) {
                  const session = next.find(item => item.id === id)
                  if (
                    sessionIdRef.current !== id ||
                    (typeof document !== 'undefined' &&
                      (document.hidden || !document.hasFocus()))
                  ) {
                    markSessionAttention(id)
                  }
                  notifyRunCompleted({
                    sessionId: id,
                    sessionTitle: session?.title,
                    ok: event.type === 'run.completed'
                  })
                }
                return next
              })
              if (event.type === 'run.completed') {
                setWorkspaceVersion(current => current + 1)
                void loadSkillsRef.current?.()
              }
              void client.listMessages(id).then(history => {
                patchChat(id, prev => ({
                  ...prev,
                  messages: history,
                  messagesLoaded: true
                }))
              })
              void loadSessionsRef.current?.()
            }
          }
        })
        .catch((cause: unknown) => {
          if (!controller.signal.aborted && sessionIdRef.current === id) {
            setError(
              cause instanceof Error
                ? cause.message
                : 'Event stream disconnected'
            )
          }
        })
        .finally(() => {
          if (streamControllersRef.current.get(id) === controller) {
            streamControllersRef.current.delete(id)
          }
        })
    }
  }, [client, health, patchChat, runningSessionIdsKey, sessionId])
}
