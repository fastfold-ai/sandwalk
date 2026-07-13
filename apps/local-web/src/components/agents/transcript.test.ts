import type { AgentEvent, AgentMessage, AgentTodo } from '@sandwalk/agent-ui-core'
import { describe, expect, it } from 'vitest'

import type { TranscriptTool } from './ToolCard'
import {
  TOOL_RUN_VISIBLE_COUNT,
  buildConversationTimeline,
  formatSessionExportMarkdown,
  splitAssistantThought,
  thoughtDurationForTools,
  toolsFromEvents
} from './transcript'

function msg(
  overrides: Partial<AgentMessage> & Pick<AgentMessage, 'id' | 'role' | 'content'>
): AgentMessage {
  return {
    sessionId: 's1',
    createdAt: '2026-07-13T12:00:00.000Z',
    ...overrides
  }
}

function tool(overrides: Partial<TranscriptTool> & Pick<TranscriptTool, 'id'>): TranscriptTool {
  return {
    runId: 'run-1',
    messageId: null,
    name: 'search',
    status: 'completed',
    startedAt: '2026-07-13T12:00:00.000Z',
    endedAt: '2026-07-13T12:00:05.000Z',
    ...overrides
  }
}

function envelope<TType extends AgentEvent['type']>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>['payload'],
  overrides: Partial<Omit<AgentEvent, 'type' | 'payload'>> = {}
): AgentEvent {
  return {
    schemaVersion: 1,
    id: overrides.id ?? `${type}-1`,
    sessionId: 's1',
    runId: overrides.runId ?? 'run-1',
    sequence: overrides.sequence ?? 1,
    timestamp: overrides.timestamp ?? '2026-07-13T12:00:00.000Z',
    type,
    payload
  } as AgentEvent
}

describe('splitAssistantThought', () => {
  it('returns null thought for empty or single-paragraph content', () => {
    expect(splitAssistantThought('')).toEqual({ thought: null, answer: '' })
    expect(splitAssistantThought('  Just an answer.  ')).toEqual({
      thought: null,
      answer: 'Just an answer.'
    })
  })

  it('splits thought prefixes from the remainder', () => {
    const content = "I'll look this up.\n\nHere is the answer."
    expect(splitAssistantThought(content)).toEqual({
      thought: "I'll look this up.",
      answer: 'Here is the answer.'
    })
  })

  it('does not split when first paragraph lacks a thought prefix', () => {
    const content = 'Results look good.\n\nMore detail.'
    expect(splitAssistantThought(content)).toEqual({
      thought: null,
      answer: content
    })
  })

  it('accepts common thought prefixes', () => {
    expect(
      splitAssistantThought("First I'll gather context.\n\nAnswer body.")
        .thought
    ).toBe("First I'll gather context.")
    expect(
      splitAssistantThought("To start, open the file.\n\nDone.").thought
    ).toBe('To start, open the file.')
  })
})

describe('buildConversationTimeline', () => {
  it('emits user/system messages as-is', () => {
    const messages = [
      msg({ id: 'u1', role: 'user', content: 'Hi' }),
      msg({ id: 'sys', role: 'system', content: 'note' })
    ]
    const timeline = buildConversationTimeline({
      messages,
      tools: [],
      todosByRunId: {},
      runIdByMessageId: {}
    })
    expect(timeline).toEqual([
      { kind: 'message', message: messages[0], content: 'Hi' },
      { kind: 'message', message: messages[1], content: 'note' }
    ])
  })

  it('splits thoughts, attaches tools by message/run, and appends todos', () => {
    const assistant = msg({
      id: 'a1',
      role: 'assistant',
      content: "I'll search.\n\nFound it."
    })
    const tools = [
      tool({ id: 't1', messageId: 'a1', name: 'web' }),
      tool({ id: 't2', runId: 'run-1', messageId: null, name: 'db' })
    ]
    const todos: AgentTodo[] = [
      { id: 'todo-1', content: 'Review', status: 'pending' }
    ]
    const timeline = buildConversationTimeline({
      messages: [assistant],
      tools,
      todosByRunId: { 'run-1': todos },
      runIdByMessageId: { a1: 'run-1' }
    })

    expect(timeline.map(e => e.kind)).toEqual([
      'thought',
      'tool',
      'tool',
      'message',
      'todos'
    ])
    expect(timeline[0]).toMatchObject({
      kind: 'thought',
      thought: "I'll search."
    })
    expect(timeline[3]).toMatchObject({
      kind: 'message',
      content: 'Found it.'
    })
    expect(timeline[4]).toMatchObject({
      kind: 'todos',
      messageId: 'a1',
      todos
    })
  })

  it('skips empty assistant answer when tools exist', () => {
    const assistant = msg({ id: 'a1', role: 'assistant', content: '   ' })
    const tools = [tool({ id: 't1', messageId: 'a1' })]
    const timeline = buildConversationTimeline({
      messages: [assistant],
      tools,
      todosByRunId: {},
      runIdByMessageId: {}
    })
    expect(timeline.map(e => e.kind)).toEqual(['tool'])
  })

  it('keeps empty assistant message when there are no tools', () => {
    const assistant = msg({ id: 'a1', role: 'assistant', content: '   ' })
    const timeline = buildConversationTimeline({
      messages: [assistant],
      tools: [],
      todosByRunId: {},
      runIdByMessageId: {}
    })
    expect(timeline).toHaveLength(1)
    expect(timeline[0]?.kind).toBe('message')
  })

  it('appends orphan tools except those on the active run', () => {
    const tools = [
      tool({ id: 'orphan', runId: 'old-run', messageId: null }),
      tool({ id: 'active', runId: 'active-run', messageId: null })
    ]
    const timeline = buildConversationTimeline({
      messages: [],
      tools,
      todosByRunId: {},
      runIdByMessageId: {},
      activeRunId: 'active-run'
    })
    expect(timeline).toEqual([{ kind: 'tool', tool: tools[0] }])
  })
})

describe('thoughtDurationForTools', () => {
  it('returns null for empty tools', () => {
    expect(thoughtDurationForTools([])).toBeNull()
  })

  it('uses earliest start and latest end', () => {
    const duration = thoughtDurationForTools([
      tool({
        id: 't1',
        startedAt: '2026-07-13T12:00:00.000Z',
        endedAt: '2026-07-13T12:00:02.000Z'
      }),
      tool({
        id: 't2',
        startedAt: '2026-07-13T12:00:01.000Z',
        endedAt: '2026-07-13T12:00:10.000Z'
      })
    ])
    expect(duration).toBe('10s')
  })
})

describe('toolsFromEvents', () => {
  it('tracks run mappings, tools, and todos from events', () => {
    const events: AgentEvent[] = [
      envelope('run.started', { messageId: 'u1' }),
      envelope('tool.started', {
        name: 'search',
        arguments: { q: 'kinase' },
        toolCallId: 'tc1'
      }),
      envelope(
        'tool.completed',
        {
          name: 'search',
          output: { hits: 1 },
          toolCallId: 'tc1',
          isError: false,
          durationSeconds: 1.2
        },
        { timestamp: '2026-07-13T12:00:02.000Z' }
      ),
      envelope('assistant.message', {
        message: msg({ id: 'a1', role: 'assistant', content: 'done' })
      }),
      envelope('todos.updated', {
        todos: [{ id: 't1', content: 'Next', status: 'completed' }]
      }),
      envelope(
        'tool.completed',
        {
          name: 'orphan',
          output: 'err',
          toolCallId: 'tc2',
          isError: true,
          durationSeconds: 0.5
        },
        { id: 'tool.completed-2' }
      )
    ]

    const result = toolsFromEvents(events)
    expect(result.runIdByMessageId).toEqual({ u1: 'run-1', a1: 'run-1' })
    expect(result.todosByRunId['run-1']?.[0]?.content).toBe('Next')
    expect(result.tools).toHaveLength(2)
    expect(result.tools.find(t => t.id === 'tc1')).toMatchObject({
      status: 'completed',
      args: { q: 'kinase' },
      result: { hits: 1 }
    })
    expect(result.tools.find(t => t.id === 'tc2')).toMatchObject({
      status: 'error',
      name: 'orphan'
    })
  })
})

describe('formatSessionExportMarkdown', () => {
  it('exports titled conversation with tools, thoughts, and todos', () => {
    const messages = [
      msg({ id: 'u1', role: 'user', content: 'Run search' }),
      msg({
        id: 'a1',
        role: 'assistant',
        content: "I'll search.\n\nHere are results."
      })
    ]
    const events: AgentEvent[] = [
      envelope('run.started', { messageId: 'u1' }),
      envelope('assistant.message', { message: messages[1]! }),
      envelope('tool.started', {
        name: 'search',
        arguments: { api_key: 'super-secret-value-12345', q: 'x' },
        toolCallId: 'tc1'
      }),
      envelope(
        'tool.completed',
        {
          name: 'search',
          output: { token: 'abcdefghijklmnopqrstuvwxyz' },
          toolCallId: 'tc1',
          isError: false,
          durationSeconds: 2
        },
        { timestamp: '2026-07-13T12:00:02.000Z' }
      ),
      envelope('todos.updated', {
        todos: [
          { id: 'td1', content: 'Done item', status: 'completed' },
          { id: 'td2', content: 'Open item', status: 'pending' }
        ]
      })
    ]

    const md = formatSessionExportMarkdown({
      title: ' Session One ',
      messages,
      events
    })

    expect(md).toContain('# Session One')
    expect(md).toContain('## user')
    expect(md).toContain('Run search')
    expect(md).toContain('### Thought')
    expect(md).toContain("I'll search.")
    expect(md).toContain('### Tools')
    expect(md).toContain('`search`')
    expect(md).toContain('[redacted]')
    expect(md).toContain('### Response')
    expect(md).toContain('Here are results.')
    expect(md).toContain('### Todos')
    expect(md).toContain('- [x] Done item')
    expect(md).toContain('- [ ] Open item')
  })

  it('handles system messages and empty content', () => {
    const md = formatSessionExportMarkdown({
      messages: [
        msg({ id: 'sys', role: 'system', content: '' }),
        msg({ id: 'u1', role: 'user', content: 'hello' }),
        msg({ id: 'a1', role: 'assistant', content: 'plain answer' })
      ],
      events: []
    })
    expect(md).toContain('## system')
    expect(md).toContain('_(empty)_')
    expect(md).toContain('## user')
    expect(md).toContain('### Response')
    expect(md).toContain('plain answer')
  })

  it('escapes nested fences in tool payloads', () => {
    const messages = [msg({ id: 'a1', role: 'assistant', content: 'ok' })]
    const events: AgentEvent[] = [
      envelope('tool.started', {
        name: 'echo',
        arguments: 'line\n```\ncode',
        toolCallId: 'tc1'
      }),
      envelope('tool.completed', {
        name: 'echo',
        output: null,
        toolCallId: 'tc1',
        isError: false,
        durationSeconds: 0.1
      })
    ]
    const md = formatSessionExportMarkdown({ messages, events })
    expect(md).toContain('### Tools')
    expect(md).toContain('``\u200b`')
  })
})

describe('TOOL_RUN_VISIBLE_COUNT', () => {
  it('exports the visible tool run count constant', () => {
    expect(TOOL_RUN_VISIBLE_COUNT).toBe(1)
  })
})
