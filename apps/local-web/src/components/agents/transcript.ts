import type { AgentEvent, AgentMessage, AgentTodo } from '@sandwalk/agent-ui-core'

import type { TranscriptTool } from './ToolCard'
import { formatToolExecutionTime } from './ToolCard'

export function splitAssistantThought(content: string): {
  thought: string | null
  answer: string
} {
  const raw = content.trim()
  if (!raw) return { thought: null, answer: content }
  const sections = raw.split(/\n\s*\n/)
  if (sections.length < 2) return { thought: null, answer: raw }
  const first = sections[0]?.trim() ?? ''
  const hasThoughtPrefix =
    /^(i['’]ll|i will|let me|first|to start|starting|i am going to|i'm going to|we['’]ll|let's|lets)\b/i.test(
      first
    )
  if (!hasThoughtPrefix) return { thought: null, answer: raw }
  const remainder = sections.slice(1).join('\n\n').trim()
  return { thought: first, answer: remainder || raw }
}

export type TranscriptEntry =
  | { kind: 'message'; message: AgentMessage; content: string }
  | { kind: 'thought'; message: AgentMessage; thought: string }
  | { kind: 'tool'; tool: TranscriptTool }
  | { kind: 'todos'; messageId: string; todos: AgentTodo[] }

export function buildConversationTimeline({
  messages,
  tools,
  todosByRunId,
  runIdByMessageId,
  activeRunId = null
}: {
  messages: AgentMessage[]
  tools: TranscriptTool[]
  todosByRunId: Record<string, AgentTodo[]>
  runIdByMessageId: Record<string, string>
  activeRunId?: string | null
}): TranscriptEntry[] {
  const timeline: TranscriptEntry[] = []
  const usedToolIds = new Set<string>()

  for (const message of messages) {
    if (message.role === 'user' || message.role === 'system') {
      timeline.push({ kind: 'message', message, content: message.content })
      continue
    }

    const runId = runIdByMessageId[message.id] || null
    const turnTools = tools.filter(tool => {
      if (tool.messageId === message.id) return true
      if (runId && tool.runId === runId) return true
      return false
    })
    turnTools.forEach(tool => usedToolIds.add(tool.id))

    const split = splitAssistantThought(message.content)
    if (split.thought) {
      timeline.push({
        kind: 'thought',
        message,
        thought: split.thought
      })
    }

    for (const tool of turnTools) {
      timeline.push({ kind: 'tool', tool })
    }

    const answer = split.thought ? split.answer : message.content
    if (answer.trim() || turnTools.length === 0) {
      timeline.push({
        kind: 'message',
        message,
        content: answer
      })
    }

    const todos = runId ? todosByRunId[runId] : undefined
    if (todos && todos.length > 0) {
      timeline.push({
        kind: 'todos',
        messageId: message.id,
        todos
      })
    }
  }

  const orphanTools = tools.filter(tool => {
    if (usedToolIds.has(tool.id)) return false
    if (activeRunId && tool.runId === activeRunId) return false
    return true
  })
  for (const tool of orphanTools) {
    timeline.push({ kind: 'tool', tool })
  }

  return timeline
}

export function thoughtDurationForTools(tools: TranscriptTool[]) {
  if (tools.length === 0) return null
  const startedAt = [...tools]
    .map(tool => tool.startedAt)
    .sort((a, b) => Date.parse(a) - Date.parse(b))[0]
  const endedAt = [...tools]
    .map(tool => tool.endedAt || tool.startedAt)
    .sort((a, b) => Date.parse(a) - Date.parse(b))
    .at(-1)
  return formatToolExecutionTime(startedAt, endedAt)
}

export const TOOL_RUN_VISIBLE_COUNT = 1

const SECRET_KEY =
  /(api[_-]?key|token|password|secret|authorization|bearer|credential)/i

function redactSecrets(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redactSecrets)
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {}
    for (const [key, nested] of Object.entries(
      value as Record<string, unknown>
    )) {
      out[key] = SECRET_KEY.test(key) ? '[redacted]' : redactSecrets(nested)
    }
    return out
  }
  if (typeof value === 'string' && value.length > 24 && SECRET_KEY.test(value)) {
    return '[redacted]'
  }
  return value
}

function formatPayloadBlock(value: unknown): string {
  if (value == null) return ''
  const safe = redactSecrets(value)
  if (typeof safe === 'string') return safe
  try {
    return JSON.stringify(safe, null, 2)
  } catch {
    return String(safe)
  }
}

function fence(language: string, body: string): string {
  const safe = body.replace(/\n```/g, '\n``\u200b`')
  return `\`\`\`${language}\n${safe}\n\`\`\``
}

export function toolsFromEvents(events: AgentEvent[]): {
  tools: TranscriptTool[]
  todosByRunId: Record<string, AgentTodo[]>
  runIdByMessageId: Record<string, string>
} {
  const toolsById = new Map<string, TranscriptTool>()
  const todosByRunId: Record<string, AgentTodo[]> = {}
  const runIdByMessageId: Record<string, string> = {}

  for (const event of events) {
    if (event.type === 'run.started' && event.runId && event.payload.messageId) {
      runIdByMessageId[event.payload.messageId] = event.runId
    }
    if (
      event.type === 'assistant.message' &&
      event.runId &&
      event.payload.message?.id
    ) {
      runIdByMessageId[event.payload.message.id] = event.runId
    }
    if (event.type === 'tool.started') {
      const id = event.payload.toolCallId || event.id
      toolsById.set(id, {
        id,
        runId: event.runId,
        messageId: null,
        name: event.payload.name,
        status: 'pending',
        args: event.payload.arguments,
        startedAt: event.timestamp
      })
    } else if (event.type === 'tool.completed') {
      const id = event.payload.toolCallId || event.id
      const existing = toolsById.get(id)
      toolsById.set(id, {
        id,
        runId: existing?.runId ?? event.runId,
        messageId: existing?.messageId ?? null,
        name: event.payload.name || existing?.name || 'tool',
        status: event.payload.isError ? 'error' : 'completed',
        args: existing?.args,
        result: event.payload.output,
        startedAt: existing?.startedAt || event.timestamp,
        endedAt: event.timestamp,
        durationSeconds: event.payload.durationSeconds
      })
    } else if (event.type === 'todos.updated' && event.runId) {
      todosByRunId[event.runId] = event.payload.todos
    }
  }

  return {
    tools: [...toolsById.values()],
    todosByRunId,
    runIdByMessageId
  }
}

function formatToolMarkdown(tool: TranscriptTool): string {
  const timing =
    formatToolExecutionTime(
      tool.startedAt,
      tool.endedAt,
      tool.durationSeconds
    ) || null
  const meta = [tool.status, timing].filter(Boolean).join(', ')
  const lines = [`#### \`${tool.name}\`${meta ? ` (${meta})` : ''}`]
  const argsText = formatPayloadBlock(tool.args)
  if (argsText.trim()) {
    lines.push('', '**Arguments**', '', fence('json', argsText))
  }
  const resultText = formatPayloadBlock(tool.result)
  if (resultText.trim()) {
    lines.push('', '**Output**', '', fence('json', resultText))
  }
  return lines.join('\n')
}

/** Build a markdown export that includes full tool arguments/outputs. */
export function formatSessionExportMarkdown({
  title,
  messages,
  events
}: {
  title?: string
  messages: AgentMessage[]
  events: AgentEvent[]
}): string {
  const { tools, todosByRunId, runIdByMessageId } = toolsFromEvents(events)
  const timeline = buildConversationTimeline({
    messages,
    tools,
    todosByRunId,
    runIdByMessageId
  })

  const blocks: string[] = []
  if (title?.trim()) {
    blocks.push(`# ${title.trim()}`, '')
  }

  let current: string[] = []
  const flush = () => {
    if (current.length === 0) return
    blocks.push(current.join('\n\n'))
    current = []
  }

  for (const entry of timeline) {
    if (entry.kind === 'message') {
      const role =
        entry.message.role === 'assistant'
          ? 'sandwalk'
          : entry.message.role === 'system'
            ? 'system'
            : 'user'
      if (entry.message.role !== 'assistant' || current.length === 0) {
        flush()
        current.push(`## ${role}`, entry.content.trim() || '_(empty)_')
      } else {
        current.push('### Response', entry.content.trim() || '_(empty)_')
      }
      continue
    }

    if (entry.kind === 'thought') {
      if (current.length === 0) current.push('## sandwalk')
      current.push('### Thought', entry.thought.trim())
      continue
    }

    if (entry.kind === 'tool') {
      if (current.length === 0) current.push('## sandwalk')
      if (!current.some(line => line === '### Tools')) {
        current.push('### Tools')
      }
      current.push(formatToolMarkdown(entry.tool))
      continue
    }

    if (entry.kind === 'todos') {
      if (current.length === 0) current.push('## sandwalk')
      const items = entry.todos
        .map(
          todo =>
            `- [${todo.status === 'completed' ? 'x' : ' '}] ${todo.content}`
        )
        .join('\n')
      current.push('### Todos', items)
    }
  }
  flush()

  return `${blocks.join('\n\n---\n\n')}\n`
}
