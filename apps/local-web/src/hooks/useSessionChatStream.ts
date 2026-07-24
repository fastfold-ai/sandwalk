import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentEvent,
  AgentSession,
  BackendHealth
} from '@sandwalk/agent-ui-core'
import { type Dispatch, type MutableRefObject, type SetStateAction,useEffect, useRef } from 'react'

import { toolsFromEvents } from '@/components/agents/transcript'
import { notifyApprovalRequired } from '@/lib/browser-notifications'
import { reduceChatOnAgentEvent } from '@/lib/chat-actions'
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
  loadSessionsRef: MutableRefObject<(() => Promise<void>) | null>
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

  useEffect(() => {
    if (!health || !sessionId) return
    if (chatBySessionIdRef.current[sessionId]?.messagesLoaded) return

    // Empty/new sessions: show the empty composer immediately, hydrate in background.
    const meta = sessions.find(item => item.id === sessionId)
    if (meta && !meta.lastMessageAt && meta.status === 'idle') {
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
        }
      })
    return () => controller.abort()
    // Intentionally omit `sessions` — only re-hydrate when the active session changes.
  }, [client, health, patchChat, sessionId])

  useEffect(() => {
    if (!health) {
      for (const controller of streamControllersRef.current.values()) {
        controller.abort()
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
      }
    }

    for (const id of wanted) {
      if (streamControllersRef.current.has(id)) continue
      const controller = new AbortController()
      streamControllersRef.current.set(id, controller)

      void client
        .streamEvents(id, {
          signal: controller.signal,
          onEvent: (event: AgentEvent) => {
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
              setSessions(current =>
                current.map(item =>
                  item.id === id ? { ...item, status: nextStatus } : item
                )
              )
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
