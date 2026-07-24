import type {
  AgentEvent,
  AgentMessage,
  AgentPlanCard,
  AgentTodo
} from '@sandwalk/agent-ui-core'

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
  | { kind: 'plan'; messageId: string; plan: AgentPlanCard }

export function buildConversationTimeline({
  messages,
  tools,
  todosByRunId,
  plansByRunId,
  runIdByMessageId,
  activeRunId: _activeRunId = null
}: {
  messages: AgentMessage[]
  tools: TranscriptTool[]
  todosByRunId?: Record<string, AgentTodo[]> | null
  plansByRunId?: Record<string, AgentPlanCard[]> | null
  runIdByMessageId?: Record<string, string> | null
  activeRunId?: string | null
}): TranscriptEntry[] {
  const timeline: TranscriptEntry[] = []
  const usedToolIds = new Set<string>()
  const todosMap = todosByRunId ?? {}
  const plansMap = plansByRunId ?? {}
  const runMap = runIdByMessageId ?? {}

  // Attach each plan path once on the first run that created it (last assistant
  // message of that run). Later runs that rewrite the same path (follow-ups /
  // Build) must not spawn another Created Plan card.
  const lastAssistantByRun = new Map<string, string>()
  const lastMessageByRun = new Map<string, string>()
  const planPathFirstRun = new Map<string, { plan: AgentPlanCard; runId: string }>()
  let unscopedToolSinkId: string | null = null
  for (const message of messages) {
    const runId = runMap[message.id]
    if (runId) lastMessageByRun.set(runId, message.id)
    if (message.role !== 'assistant') continue
    if (!unscopedToolSinkId) unscopedToolSinkId = message.id
    if (!runId) continue
    lastAssistantByRun.set(runId, message.id)
    for (const plan of plansMap[runId] || []) {
      if (!planPathFirstRun.has(plan.path)) {
        planPathFirstRun.set(plan.path, { plan, runId })
      }
    }
  }
  const planPathOwnerMessageId = new Map<string, string>()
  const planPathToCard = new Map<string, AgentPlanCard>()
  for (const [path, { plan, runId }] of planPathFirstRun) {
    const ownerMessageId = lastAssistantByRun.get(runId)
    if (!ownerMessageId) continue
    planPathOwnerMessageId.set(path, ownerMessageId)
    planPathToCard.set(path, plan)
  }

  const takeToolsForMessage = (messageId: string, runId: string | null) => {
    const turnTools = tools.filter(tool => {
      if (usedToolIds.has(tool.id)) return false
      if (tool.messageId === messageId) return true
      // Anchor historical tools on the last message of their run so interrupted
      // runs (no assistant reply) don't float as forever-orphans at the bottom.
      if (
        runId &&
        tool.runId === runId &&
        lastMessageByRun.get(runId) === messageId
      ) {
        return true
      }
      // Unscoped tools, or tools whose run has no messages left in history:
      // park on the first assistant so they never reappear under later turns.
      const strandedRun =
        Boolean(tool.runId) && !lastMessageByRun.has(String(tool.runId))
      if (
        !tool.messageId &&
        tool.status !== 'pending' &&
        messageId === unscopedToolSinkId &&
        (!tool.runId || strandedRun)
      ) {
        return true
      }
      return false
    })
    turnTools.forEach(tool => usedToolIds.add(tool.id))
    return turnTools
  }

  for (const message of messages) {
    if (message.role === 'user' || message.role === 'system') {
      timeline.push({ kind: 'message', message, content: message.content })
      const runId = runMap[message.id] || null
      if (runId && lastMessageByRun.get(runId) === message.id) {
        for (const tool of takeToolsForMessage(message.id, runId)) {
          timeline.push({ kind: 'tool', tool })
        }
      }
      continue
    }

    const runId = runMap[message.id] || null
    const turnTools = takeToolsForMessage(message.id, runId)

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

    for (const [path, ownerMessageId] of planPathOwnerMessageId) {
      if (ownerMessageId !== message.id) continue
      const plan = planPathToCard.get(path)
      if (!plan) continue
      timeline.push({
        kind: 'plan',
        messageId: message.id,
        plan
      })
    }

    if (
      runId &&
      lastAssistantByRun.get(runId) === message.id &&
      (todosMap[runId]?.length ?? 0) > 0
    ) {
      timeline.push({
        kind: 'todos',
        messageId: message.id,
        todos: todosMap[runId]!
      })
    }
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

export function toolsFromEvents(events: AgentEvent[]): {
  tools: TranscriptTool[]
  todosByRunId: Record<string, AgentTodo[]>
  plansByRunId: Record<string, AgentPlanCard[]>
  runIdByMessageId: Record<string, string>
  usageByRunId: Record<
    string,
    {
      inputTokens: number
      outputTokens: number
      tokensPerSecond?: number | null
      promptTokensPerSecond?: number | null
      promptEvalSeconds?: number | null
      generationSeconds?: number | null
      timeToFirstToken?: number | null
      estimated?: boolean
    }
  >
  tokenUsage: {
    inputTokens: number
    outputTokens: number
    tokensPerSecond?: number | null
    promptTokensPerSecond?: number | null
    promptEvalSeconds?: number | null
    generationSeconds?: number | null
    timeToFirstToken?: number | null
    estimated?: boolean
  }
} {
  const toolsById = new Map<string, TranscriptTool>()
  const todosByRunId: Record<string, AgentTodo[]> = {}
  const plansByRunId: Record<string, AgentPlanCard[]> = {}
  const runIdByMessageId: Record<string, string> = {}
  const usageByRunId: Record<
    string,
    {
      inputTokens: number
      outputTokens: number
      tokensPerSecond?: number | null
      promptTokensPerSecond?: number | null
      promptEvalSeconds?: number | null
      generationSeconds?: number | null
      timeToFirstToken?: number | null
      estimated?: boolean
    }
  > = {}
  let tokenUsage = {
    inputTokens: 0,
    outputTokens: 0,
    tokensPerSecond: null as number | null,
    promptTokensPerSecond: null as number | null,
    promptEvalSeconds: null as number | null,
    generationSeconds: null as number | null,
    timeToFirstToken: null as number | null,
    estimated: false
  }

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
    if (event.type === 'plan.created' && event.runId) {
      const existing = plansByRunId[event.runId] || []
      const next = {
        path: event.payload.path,
        title: event.payload.title,
        summary: event.payload.summary
      }
      plansByRunId[event.runId] = [
        ...existing.filter(plan => plan.path !== next.path),
        next
      ]
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
    } else if (
      event.type === 'run.completed' ||
      event.type === 'run.failed' ||
      event.type === 'run.interrupted'
    ) {
      const reason =
        event.type === 'run.interrupted'
          ? 'Interrupted'
          : event.type === 'run.failed'
            ? 'Run failed'
            : 'Run ended'
      for (const [id, tool] of toolsById) {
        if (tool.status !== 'pending') continue
        const sameRun = Boolean(event.runId && tool.runId === event.runId)
        const unscoped = tool.runId == null || tool.runId === ''
        if (event.runId && !sameRun && !unscoped) continue
        toolsById.set(id, {
          ...tool,
          status: 'error',
          result: { summary: reason },
          endedAt: event.timestamp
        })
      }
    } else if (event.type === 'todos.updated' && event.runId) {
      todosByRunId[event.runId] = event.payload.todos
    } else if (event.type === 'run.usage' && event.runId) {
      const payload = event.payload as Record<string, unknown>
      const optionalNumber = (value: unknown) => {
        if (value == null || value === '') return null
        const number = Number(value)
        return Number.isFinite(number) ? number : null
      }
      const nextUsage = {
        inputTokens: Number(payload.inputTokens ?? payload.input_tokens ?? 0),
        outputTokens: Number(
          payload.outputTokens ?? payload.output_tokens ?? 0
        ),
        tokensPerSecond: optionalNumber(
          payload.tokensPerSecond ?? payload.tokens_per_second
        ),
        promptTokensPerSecond: optionalNumber(
          payload.promptTokensPerSecond ?? payload.prompt_tokens_per_second
        ),
        promptEvalSeconds: optionalNumber(
          payload.promptEvalSeconds ?? payload.prompt_eval_seconds
        ),
        generationSeconds: optionalNumber(
          payload.generationSeconds ?? payload.generation_seconds
        ),
        timeToFirstToken: optionalNumber(
          payload.timeToFirstToken ?? payload.time_to_first_token
        ),
        estimated: Boolean(payload.estimated)
      }
      usageByRunId[event.runId] = nextUsage
      tokenUsage = nextUsage
    }
  }

  return {
    tools: [...toolsById.values()],
    todosByRunId,
    plansByRunId,
    runIdByMessageId,
    usageByRunId,
    tokenUsage
  }
}

export { formatSessionExportMarkdown } from './transcript-markdown-export'
