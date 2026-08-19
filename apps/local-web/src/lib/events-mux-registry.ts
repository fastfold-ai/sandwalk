import type { AgentEvent } from '@sandwalk/agent-ui-core'

type TranscriptHandler = (event: AgentEvent) => void
type LifecycleHandler = (event: {
  sequence: number
  type: string
  timestamp: number
  payload: Record<string, unknown>
}) => void

const transcriptHandlers = new Map<string, TranscriptHandler>()
const registryListeners = new Set<() => void>()
let lifecycleHandler: LifecycleHandler | null = null

function emitRegistry() {
  for (const listener of registryListeners) listener()
}

export function registerTranscriptSseHandler(
  sessionId: string,
  handler: TranscriptHandler
): () => void {
  transcriptHandlers.set(sessionId, handler)
  emitRegistry()
  return () => {
    if (transcriptHandlers.get(sessionId) === handler) {
      transcriptHandlers.delete(sessionId)
      emitRegistry()
    }
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
  transcriptHandlers.get(sessionId)?.(event)
}

export function dispatchLifecycleSse(event: {
  sequence: number
  type: string
  timestamp: number
  payload: Record<string, unknown>
}) {
  lifecycleHandler?.(event)
}
