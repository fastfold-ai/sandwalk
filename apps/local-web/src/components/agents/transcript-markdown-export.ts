import type { AgentEvent, AgentMessage } from '@sandwalk/agent-ui-core'

import type { TranscriptTool } from './ToolCard'
import { formatToolExecutionTime } from './ToolCard'
import { buildConversationTimeline, toolsFromEvents } from './transcript'

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
  const { tools, todosByRunId, plansByRunId, runIdByMessageId } =
    toolsFromEvents(events)
  const timeline = buildConversationTimeline({
    messages,
    tools,
    todosByRunId,
    plansByRunId,
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
