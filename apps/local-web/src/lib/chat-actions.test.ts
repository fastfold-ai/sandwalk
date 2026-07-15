import type { AgentEvent } from '@sandwalk/agent-ui-core'
import { describe, expect, it } from 'vitest'

import {
  buildSendContent,
  reduceChatOnAgentEvent
} from './chat-actions'
import { emptySessionChatState } from './sessions'

function event<TType extends AgentEvent['type']>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>['payload'],
  partial?: Partial<AgentEvent>
): AgentEvent {
  return {
    schemaVersion: 1,
    id: 'evt-1',
    sessionId: 'session-1',
    runId: 'run-1',
    sequence: 1,
    timestamp: '2026-07-15T12:00:00.000Z',
    type,
    payload,
    ...partial
  } as AgentEvent
}

describe('buildSendContent', () => {
  it('joins legacy chips with composer text', () => {
    const content = buildSendContent({
      composerText: 'analyze this',
      composerSkills: ['fold'],
      composerFiles: ['data.csv']
    })
    expect(content).toBe('/fold @data.csv analyze this')
  })

  it('skips legacy chips already embedded in composer tokens', () => {
    const content = buildSendContent({
      composerText: 'run ⟦/:fold⟧ on ⟦@:data.csv⟧',
      composerSkills: ['fold'],
      composerFiles: ['data.csv']
    })
    expect(content).toBe('run /fold on @data.csv')
  })
})

describe('reduceChatOnAgentEvent', () => {
  it('appends assistant deltas', () => {
    const prev = { ...emptySessionChatState(), liveDelta: 'Hello' }
    const next = reduceChatOnAgentEvent(
      prev,
      event('assistant.delta', { delta: ' world' })
    )
    expect(next.liveDelta).toBe('Hello world')
  })

  it('clears live state on run.completed and completes in-progress todos', () => {
    const prev = {
      ...emptySessionChatState(),
      runActive: true,
      activeRunId: 'run-1',
      liveDelta: 'streaming',
      todosByRunId: {
        'run-1': [
          {
            id: 'todo-1',
            content: 'Step one',
            status: 'in_progress' as const
          },
          {
            id: 'todo-2',
            content: 'Step two',
            status: 'pending' as const
          }
        ]
      }
    }
    const next = reduceChatOnAgentEvent(
      prev,
      event('run.completed', { messageId: 'msg-1' })
    )
    expect(next.runActive).toBe(false)
    expect(next.activeRunId).toBeNull()
    expect(next.liveDelta).toBe('')
    expect(next.todosByRunId['run-1']).toEqual([
      {
        id: 'todo-1',
        content: 'Step one',
        status: 'completed'
      },
      {
        id: 'todo-2',
        content: 'Step two',
        status: 'pending'
      }
    ])
  })

  it('adds tool.started entries and ignores duplicates', () => {
    const prev = {
      ...emptySessionChatState(),
      tools: [
        {
          id: 'tool-1',
          runId: 'run-1',
          messageId: null,
          name: 'search',
          status: 'pending' as const,
          args: {},
          startedAt: '2026-07-15T12:00:00.000Z'
        }
      ]
    }
    const duplicate = reduceChatOnAgentEvent(
      prev,
      event(
        'tool.started',
        { name: 'search', arguments: {}, toolCallId: 'tool-1' },
        { id: 'evt-dup' }
      )
    )
    expect(duplicate).toBe(prev)

    const next = reduceChatOnAgentEvent(
      prev,
      event(
        'tool.started',
        { name: 'read_file', arguments: { path: 'a.txt' }, toolCallId: 'tool-2' },
        { id: 'evt-new' }
      )
    )
    expect(next.tools).toHaveLength(2)
    expect(next.tools[1]).toMatchObject({
      id: 'tool-2',
      name: 'read_file',
      status: 'pending'
    })
  })

  it('marks tools completed or errored on tool.completed', () => {
    const prev = {
      ...emptySessionChatState(),
      tools: [
        {
          id: 'tool-1',
          runId: 'run-1',
          messageId: null,
          name: 'search',
          status: 'pending' as const,
          args: {},
          startedAt: '2026-07-15T12:00:00.000Z'
        }
      ]
    }
    const next = reduceChatOnAgentEvent(
      prev,
      event('tool.completed', {
        name: 'search',
        output: { hits: 1 },
        toolCallId: 'tool-1',
        isError: false,
        durationSeconds: 1.2
      })
    )
    expect(next.tools[0]).toMatchObject({
      status: 'completed',
      result: { hits: 1 },
      durationSeconds: 1.2
    })
  })
})
