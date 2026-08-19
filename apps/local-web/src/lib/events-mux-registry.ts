import type { AgentEvent } from '@sandwalk/agent-ui-core'

type TranscriptHandler = (event: AgentEvent) => void
type LifecycleHandler = (event: {
  sequence: number
  type: string
  timestamp: number
  payload: Record<string, unknown>
}) => void

/**
 * Stack per session — split panels and the shell both call
 * `useSessionChatStream`. Last-writer-wins Map.delete on unfocus dropped the
 * unfocused panel's handler, so mux unsubscribed and tokens never arrived
 * until that panel was focused again.
 */
const transcriptHandlers = new Map<string, TranscriptHandler[]>()
const pendingBySession = new Map<string, AgentEvent[]>()
const registryListeners = new Set<() => void>()
let lifecycleHandler: LifecycleHandler | null = null

const MAX_PENDING_EVENTS = 500

function flushPending(sessionId: string, handler: TranscriptHandler) {
  const queued = pendingBySession.get(sessionId)
  if (!queued?.length) return
  pendingBySession.delete(sessionId)
  for (const event of queued) handler(event)
}

function emitRegistry() {
  for (const listener of registryListeners) listener()
}

export function registerTranscriptSseHandler(
  sessionId: string,
  handler: TranscriptHandler
): () => void {
  const stack = transcriptHandlers.get(sessionId) ?? []
  stack.push(handler)
  transcriptHandlers.set(sessionId, stack)
  flushPending(sessionId, handler)
  emitRegistry()
  return () => {
    const current = transcriptHandlers.get(sessionId)
    if (!current) return
    const index = current.lastIndexOf(handler)
    if (index >= 0) current.splice(index, 1)
    if (current.length === 0) transcriptHandlers.delete(sessionId)
    emitRegistry()
  }
}

export function setLifecycleSseHandler(handler: LifecycleHandler | null) {
  lifecycleHandler = handler
}

export function subscribedTranscriptSessionIds(): string[] {
  return [...transcriptHandlers.keys()].sort()
}

export function subscribeTranscriptRegistry(listener: () => void): () => void {
  registryListeners.add(listener)
  return () => {
    registryListeners.delete(listener)
  }
}

export function dispatchTranscriptSse(sessionId: string, event: AgentEvent) {
  const stack = transcriptHandlers.get(sessionId)
  const handler = stack?.[stack.length - 1]
  if (handler) {
    handler(event)
    return
  }
  const queued = pendingBySession.get(sessionId) ?? []
  queued.push(event)
  if (queued.length > MAX_PENDING_EVENTS) {
    queued.splice(0, queued.length - MAX_PENDING_EVENTS)
  }
  pendingBySession.set(sessionId, queued)
}

export function dispatchLifecycleSse(event: {
  sequence: number
  type: string
  timestamp: number
  payload: Record<string, unknown>
}) {
  lifecycleHandler?.(event)
}
