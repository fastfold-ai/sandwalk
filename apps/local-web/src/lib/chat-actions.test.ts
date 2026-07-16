import type { AgentEvent } from '@sandwalk/agent-ui-core'
import { describe, expect, it } from 'vitest'

import {
  applyChatPatch,
  buildSendContent,
  normalizeSessionChatState,
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

  it('stores plan.created cards by run id', () => {
    const prev = emptySessionChatState()
    const next = reduceChatOnAgentEvent(
      prev,
      event('plan.created', {
        path: 'plans/demo.md',
        title: 'Demo',
        summary: 'Overview'
      })
    )
    expect(next.plansByRunId['run-1']).toEqual([
      { path: 'plans/demo.md', title: 'Demo', summary: 'Overview' }
    ])
  })

  it('accepts plan.created when plansByRunId was missing on prev state', () => {
    const prev = {
      ...emptySessionChatState(),
      plansByRunId: undefined as unknown as Record<string, never>
    }
    const next = reduceChatOnAgentEvent(
      prev,
      event('plan.created', {
        path: 'plans/demo.md',
        title: 'Demo',
        summary: 'Overview'
      })
    )
    expect(next.plansByRunId['run-1']).toHaveLength(1)
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

    const errored = reduceChatOnAgentEvent(
      prev,
      event('tool.completed', {
        name: 'search',
        output: { error: 'boom' },
        toolCallId: 'tool-1',
        isError: true,
        durationSeconds: 0.1
      })
    )
    expect(errored.tools[0]?.status).toBe('error')
  })

  it('handles run.started, usage, assistant.message, and terminal events', () => {
    let state = emptySessionChatState()
    state = reduceChatOnAgentEvent(state, event('run.started', { messageId: 'u1' }))
    expect(state).toMatchObject({
      runActive: true,
      activeRunId: 'run-1',
      liveDelta: ''
    })

    state = reduceChatOnAgentEvent(
      state,
      event('run.usage', {
        inputTokens: 10,
        outputTokens: 4
      } as never)
    )
    expect(state.tokenUsage).toEqual({ inputTokens: 10, outputTokens: 4 })
    expect(state.usageByRunId['run-1']).toEqual({
      inputTokens: 10,
      outputTokens: 4
    })

    state = reduceChatOnAgentEvent(
      state,
      event(
        'run.usage',
        { input_tokens: 1, output_tokens: 2 } as never,
        { runId: null }
      )
    )
    expect(state.tokenUsage).toEqual({ inputTokens: 1, outputTokens: 2 })
    expect(state.usageByRunId['run-1']).toEqual({
      inputTokens: 10,
      outputTokens: 4
    })

    state = {
      ...state,
      tools: [
        {
          id: 't1',
          runId: 'run-1',
          messageId: null,
          name: 'search',
          status: 'completed' as const,
          startedAt: '2026-07-15T12:00:00.000Z'
        }
      ]
    }
    const message = {
      id: 'a1',
      sessionId: 's1',
      role: 'assistant' as const,
      content: 'Done',
      createdAt: '2026-07-15T12:00:01.000Z'
    }
    state = reduceChatOnAgentEvent(
      state,
      event('assistant.message', { message })
    )
    expect(state.messages).toHaveLength(1)
    expect(state.runIdByMessageId.a1).toBe('run-1')
    expect(state.tools[0]?.messageId).toBe('a1')

    const again = reduceChatOnAgentEvent(
      state,
      event('assistant.message', { message })
    )
    expect(again.messages).toHaveLength(1)

    const noRun = reduceChatOnAgentEvent(
      emptySessionChatState(),
      event('assistant.message', { message }, { runId: null })
    )
    expect(noRun.messages).toHaveLength(1)
    expect(noRun.runIdByMessageId).toEqual({})
  })

  it('ignores todos/plan updates without runId and unknown events', () => {
    const prev = emptySessionChatState()
    expect(
      reduceChatOnAgentEvent(
        prev,
        event('todos.updated', { todos: [] }, { runId: null })
      )
    ).toBe(prev)
    expect(
      reduceChatOnAgentEvent(
        prev,
        event(
          'plan.created',
          { path: 'plans/x.md', title: 'X', summary: '' },
          { runId: null }
        )
      )
    ).toBe(prev)
    expect(
      reduceChatOnAgentEvent(prev, event('session.updated', {} as never))
    ).toBe(prev)
  })

  it('clears activeBuildPlan on run.interrupted', () => {
    const prev = {
      ...emptySessionChatState(),
      runActive: true,
      activeBuildPlan: {
        path: 'plans/demo.md',
        title: 'Demo',
        summary: ''
      }
    }
    const next = reduceChatOnAgentEvent(
      prev,
      event('run.interrupted', { reason: 'stopped' } as never)
    )
    expect(next.runActive).toBe(false)
    expect(next.activeBuildPlan).toBeNull()
  })
})

describe('normalizeSessionChatState / applyChatPatch', () => {
  it('fills missing fields and applies object or function patches', () => {
    const normalized = normalizeSessionChatState({
      runActive: true
    } as never)
    expect(normalized.plansByRunId).toEqual({})
    expect(normalized.builtPlanPaths).toEqual([])
    expect(normalized.runActive).toBe(true)

    const viaObject = applyChatPatch(emptySessionChatState(), {
      liveDelta: 'x'
    })
    expect(viaObject.liveDelta).toBe('x')
    expect(viaObject.plansByRunId).toEqual({})

    const viaFn = applyChatPatch(emptySessionChatState(), prev => ({
      ...prev,
      runActive: true
    }))
    expect(viaFn.runActive).toBe(true)
  })
})
