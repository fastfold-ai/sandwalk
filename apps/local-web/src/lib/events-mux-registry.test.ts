import { describe, expect, it, vi } from 'vitest'

import type { AgentEvent } from '@sandwalk/agent-ui-core'

import {
  dispatchTranscriptSse,
  registerTranscriptSseHandler,
  subscribedTranscriptSessionIds
} from './events-mux-registry'

function delta(text: string): AgentEvent {
  return {
    type: 'assistant.delta',
    payload: { delta: text }
  } as AgentEvent
}

describe('events-mux-registry', () => {
  it('keeps a split-panel subscription when the shell unsubscribes on blur', () => {
    const panel = vi.fn()
    const shell = vi.fn()
    const unsubPanel = registerTranscriptSseHandler('chat-a', panel)
    const unsubShell = registerTranscriptSseHandler('chat-a', shell)

    dispatchTranscriptSse('chat-a', delta('from-shell'))
    expect(shell).toHaveBeenCalledTimes(1)
    expect(panel).not.toHaveBeenCalled()

    unsubShell()
    expect(subscribedTranscriptSessionIds()).toEqual(['chat-a'])

    dispatchTranscriptSse('chat-a', delta('from-panel'))
    expect(panel).toHaveBeenCalledTimes(1)
    expect(shell).toHaveBeenCalledTimes(1)

    unsubPanel()
    expect(subscribedTranscriptSessionIds()).toEqual([])
  })

  it('replays frames that arrived before a panel subscribed', () => {
    const panel = vi.fn()
    dispatchTranscriptSse('chat-b', delta('early'))
    const unsub = registerTranscriptSseHandler('chat-b', panel)
    expect(panel).toHaveBeenCalledTimes(1)
    unsub()
  })
})
