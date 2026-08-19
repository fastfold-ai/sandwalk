import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentEvent,
  AgentSession,
  BackendHealth
} from '@sandwalk/agent-ui-core'
import { isSessionGroupId } from '@sandwalk/agent-ui-core'
import { type Dispatch, type MutableRefObject, type SetStateAction,useEffect, useRef } from 'react'

import { toolsFromEvents } from '@/components/agents/transcript'
import {
  notifyApprovalRequired,
  notifyRunCompleted
} from '@/lib/browser-notifications'
import { reduceChatOnAgentEvent } from '@/lib/chat-actions'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import { registerTranscriptSseHandler } from '@/lib/events-mux-registry'
import { markSessionAttention } from '@/lib/session-attention'
import type { SessionChatState } from '@/lib/sessions'

type UseSessionChatStreamArgs = {
  client: LocalAgentClient
  health: BackendHealth | null
  sessionId: string | null
  sessionIdRef: MutableRefObject<string | null>
  sessions: AgentSession[]
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
    ((options?: {
      force?: boolean
      projectId?: string | null
    }) => Promise<void>) | null
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
  chatBySessionIdRef,
  patchChat,
  setSessions,
  setWorkspaceVersion,
  setError,
  loadSessionsRef,
  loadSkillsRef
}: UseSessionChatStreamArgs) {
  const streamControllersRef = useRef<Map<string, AbortController>>(new Map())
  // Grace period before an inactive stream is aborted. Prevents SSE churn on
  // rapid tab switching — if the user comes back within STREAM_GRACE_MS, we
  // reuse the still-open EventSource instead of tearing down + reconnecting
  // (which drops the SSE cursor + rehydrates events from cache = latency).
  const streamCloseTimersRef = useRef<Map<string, number>>(new Map())
  const STREAM_GRACE_MS = 300

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
    // Draft /agents/new has no API session yet.
    if (isDraftAgentSessionId(sessionId)) {
      patchChat(sessionId, prev =>
        prev.messagesLoaded
          ? prev
          : { ...prev, messages: [], messagesLoaded: true }
      )
      return
    }
    // Group ids arrive here only via defensive paths (App shell passes
    // `effectiveSessionId` which resolves to the group's activeChatId).
    // Skip anyway so we never issue a 404 GET /sessions/grp_*/messages.
    if (isSessionGroupId(sessionId)) return
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
  const handleEventRef = useRef<(id: string, event: AgentEvent) => void>(
    () => {}
  )
  handleEventRef.current = (id: string, event: AgentEvent) => {
            if (typeof event.sequence === 'number' && event.sequence > 0) {
              const prev = afterSequenceRef.current.get(id) || 0
              if (event.sequence > prev) {
                afterSequenceRef.current.set(id, event.sequence)
              }
            }
            // After Stop the UI clears runActive immediately, but a zombie
            // worker can keep emitting. Drop live stream/tool noise so the
            // transcript does not jump back into a running state.
            const chat = chatBySessionIdRef.current[id]
            const zombieLiveEvent =
              !chat?.runActive &&
              (event.type === 'assistant.delta' ||
                event.type === 'tool.started' ||
                event.type === 'tool.completed' ||
                event.type === 'todos.updated' ||
                event.type === 'plan.created' ||
                event.type === 'run.progress' ||
                event.type === 'run.usage')
            if (zombieLiveEvent) {
              dropDeltaBuffer(id)
              return
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
              // Compact (and similar) rewrites history — refresh the transcript.
              void client.listMessages(id).then(history => {
                patchChat(id, prev => ({
                  ...prev,
                  messages: history,
                  messagesLoaded: true
                }))
              })
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

  useEffect(() => {
    if (!health) {
      for (const timer of streamCloseTimersRef.current.values()) {
        window.clearTimeout(timer)
      }
      streamCloseTimersRef.current.clear()
      for (const [id, controller] of streamControllersRef.current) {
        controller.abort()
        dropDeltaBuffer(id)
      }
      streamControllersRef.current.clear()
      return
    }

    // One mux connection covers every mounted split pane (not just the
    // focused chat). Sidebar-only sessions stay on the registry.
    const wanted = new Set<string>()
    if (
      sessionId &&
      !isDraftAgentSessionId(sessionId) &&
      !isSessionGroupId(sessionId)
    ) {
      wanted.add(sessionId)
    }

    if (health.capabilities?.eventMux) {
      for (const timer of streamCloseTimersRef.current.values()) {
        window.clearTimeout(timer)
      }
      streamCloseTimersRef.current.clear()
      for (const [id, controller] of streamControllersRef.current) {
        controller.abort()
        dropDeltaBuffer(id)
      }
      streamControllersRef.current.clear()
      // Each split pane registers its own chat id. The shell skips this
      // hook in split view so focus changes cannot unbind a pane.
      const unsubs = [...wanted].map(id =>
        registerTranscriptSseHandler(id, event =>
          handleEventRef.current(id, event)
        )
      )
      return () => {
        for (const unsub of unsubs) unsub()
      }
    }

    for (const [id, controller] of [...streamControllersRef.current]) {
      if (!wanted.has(id)) {
        // Schedule delayed abort — a fast tab switch back to this session
        // reuses the stream. See STREAM_GRACE_MS above.
        if (!streamCloseTimersRef.current.has(id)) {
          const timer = window.setTimeout(() => {
            streamCloseTimersRef.current.delete(id)
            controller.abort()
            streamControllersRef.current.delete(id)
            dropDeltaBuffer(id)
          }, STREAM_GRACE_MS)
          streamCloseTimersRef.current.set(id, timer)
        }
      }
    }

    for (const id of wanted) {
      // Cancel any pending delayed-abort for this session — we still want it.
      const pending = streamCloseTimersRef.current.get(id)
      if (pending !== undefined) {
        window.clearTimeout(pending)
        streamCloseTimersRef.current.delete(id)
      }
      if (streamControllersRef.current.has(id)) continue
      const controller = new AbortController()
      streamControllersRef.current.set(id, controller)
      const afterSequence = afterSequenceRef.current.get(id) || 0

      void client
        .streamEvents(id, {
          afterSequence,
          signal: controller.signal,
          onEvent: (event: AgentEvent) => {
            handleEventRef.current(id, event)
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
  }, [client, health, patchChat, sessionId])
}
