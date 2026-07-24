import type { AgentEvent, PendingHitlApproval } from '@sandwalk/agent-ui-core'

import { composerToMessage } from '@/components/agents/composer-parts'
import {
  emptySessionChatState,
  type SessionChatState
} from '@/lib/sessions'

export type ChatPatch =
  | Partial<SessionChatState>
  | ((prev: SessionChatState) => SessionChatState)

/** Fill fields added after a session was already in memory (HMR / old patches). */
export function normalizeSessionChatState(
  state: Partial<SessionChatState> | SessionChatState
): SessionChatState {
  return { ...emptySessionChatState(), ...state }
}

export function applyChatPatch(
  prev: SessionChatState,
  patch: ChatPatch
): SessionChatState {
  const base = normalizeSessionChatState(prev)
  const next =
    typeof patch === 'function' ? patch(base) : { ...base, ...patch }
  return normalizeSessionChatState(next)
}

export type BuildSendContentInput = {
  composerText: string
  composerSkills: string[]
  composerFiles: string[]
}

export function buildSendContent(input: BuildSendContentInput): string {
  const { composerText, composerSkills, composerFiles } = input
  const legacySkills = composerSkills
    .filter(name => !composerText.includes(`⟦/:${name}⟧`))
    .map(name => `/${name}`)
  const legacyFiles = composerFiles
    .filter(path => !composerText.includes(`⟦@:${path}⟧`))
    .map(path => `@${path}`)
  return [
    ...legacySkills,
    ...legacyFiles,
    composerToMessage(composerText)
  ]
    .filter(Boolean)
    .join(' ')
    .trim()
}

/** Mark in-flight tools finished when a run ends or a new run supersedes them. */
export function finalizePendingTools(
  tools: SessionChatState['tools'],
  options?: {
    runId?: string | null
    endedAt?: string
    reason?: string
    /** When true, finalize every pending tool (new run started). */
    allPending?: boolean
  }
): SessionChatState['tools'] {
  const runId = options?.runId
  const reason = options?.reason || 'Interrupted'
  const allPending = Boolean(options?.allPending)
  const stamp = options?.endedAt || new Date().toISOString()
  return tools.map(tool => {
    if (tool.status !== 'pending') return tool
    if (!allPending) {
      const sameRun = Boolean(runId && tool.runId === runId)
      const unscoped = tool.runId == null || tool.runId === ''
      // Match this run, unscoped tools, or everything if the end event has no runId.
      if (runId && !sameRun && !unscoped) return tool
    }
    return {
      ...tool,
      status: 'error' as const,
      result: { summary: reason },
      endedAt: stamp
    }
  })
}

export function reduceChatOnAgentEvent(
  prev: SessionChatState,
  event: AgentEvent
): SessionChatState {
  if (event.type === 'run.started') {
    return {
      ...prev,
      runActive: true,
      activeRunId: event.runId,
      liveDelta: '',
      pendingApproval: null,
      approvalSubmitting: false,
      // Drop zombie pending cards from a prior interrupted run.
      tools: finalizePendingTools(prev.tools, {
        endedAt: event.timestamp,
        reason: 'Superseded by a new run',
        allPending: true
      })
    }
  }

  if (event.type === 'run.awaiting_approval') {
    const payload = event.payload
    return {
      ...prev,
      runActive: true,
      activeRunId: event.runId ?? prev.activeRunId,
      pendingApproval: {
        interruptId: String(payload.interruptId || ''),
        runId: event.runId,
        actionRequests: (payload.actionRequests || []).map(action => ({
          name: String(action?.name || 'tool'),
          args:
            action?.args && typeof action.args === 'object'
              ? (action.args as Record<string, unknown>)
              : {},
          description: action?.description ?? null
        })),
        reviewConfigs: (payload.reviewConfigs || []).map(cfg => ({
          actionName: String(
            (cfg as { actionName?: string; action_name?: string }).actionName ||
              (cfg as { action_name?: string }).action_name ||
              ''
          ),
          allowedDecisions: ((
            cfg as {
              allowedDecisions?: string[]
              allowed_decisions?: string[]
            }
          ).allowedDecisions ||
            (cfg as { allowed_decisions?: string[] }).allowed_decisions ||
            []) as PendingHitlApproval['reviewConfigs'][number]['allowedDecisions'],
          description:
            (cfg as { description?: string | null }).description ?? null
        }))
      },
      approvalSubmitting: false
    }
  }

  if (event.type === 'run.approval_resolved') {
    return {
      ...prev,
      pendingApproval: null,
      approvalSubmitting: false
    }
  }

  if (event.type === 'assistant.delta') {
    return {
      ...prev,
      liveDelta: prev.liveDelta + event.payload.delta
    }
  }

  if (event.type === 'tool.started') {
    const toolId = event.payload.toolCallId || event.id
    if (prev.tools.some(tool => tool.id === toolId)) return prev
    return {
      ...prev,
      tools: [
        ...prev.tools,
        {
          id: toolId,
          // Some streams omit runId on tool events — inherit the active run.
          runId: event.runId ?? prev.activeRunId,
          messageId: null,
          name: event.payload.name,
          status: 'pending' as const,
          args: event.payload.arguments,
          startedAt: event.timestamp
        }
      ]
    }
  }

  if (event.type === 'tool.completed') {
    const toolId = event.payload.toolCallId || event.id
    return {
      ...prev,
      tools: prev.tools.map(tool =>
        tool.id === toolId
          ? {
              ...tool,
              status: event.payload.isError
                ? ('error' as const)
                : ('completed' as const),
              result: event.payload.output,
              durationSeconds: event.payload.durationSeconds,
              endedAt: event.timestamp
            }
          : tool
      )
    }
  }

  if (event.type === 'todos.updated') {
    if (!event.runId) return prev
    return {
      ...prev,
      todosByRunId: {
        ...(prev.todosByRunId ?? {}),
        [event.runId as string]: event.payload.todos
      }
    }
  }

  if (event.type === 'plan.created') {
    if (!event.runId) return prev
    const runId = event.runId as string
    const nextPlan = {
      path: event.payload.path,
      title: event.payload.title,
      summary: event.payload.summary
    }
    const plansByRunId = prev.plansByRunId ?? {}
    const existing = plansByRunId[runId] || []
    const deduped = existing.filter(plan => plan.path !== nextPlan.path)
    return {
      ...prev,
      plansByRunId: {
        ...plansByRunId,
        [runId]: [...deduped, nextPlan]
      }
    }
  }

  if (event.type === 'run.usage') {
    const payload = event.payload as Record<string, unknown>
    const optionalNumber = (value: unknown) => {
      if (value == null || value === '') return null
      const number = Number(value)
      return Number.isFinite(number) ? number : null
    }
    const nextUsage = {
      inputTokens: Number(payload.inputTokens ?? payload.input_tokens ?? 0),
      outputTokens: Number(payload.outputTokens ?? payload.output_tokens ?? 0),
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
    return {
      ...prev,
      tokenUsage: nextUsage,
      usageByRunId: event.runId
        ? {
            ...prev.usageByRunId,
            [event.runId as string]: nextUsage
          }
        : prev.usageByRunId
    }
  }

  if (event.type === 'assistant.message') {
    const message = event.payload.message
    const messages = prev.messages.some(item => item.id === message.id)
      ? prev.messages
      : [...prev.messages, message]
    return {
      ...prev,
      liveDelta: '',
      messages,
      messagesLoaded: true,
      runIdByMessageId: event.runId
        ? {
            ...prev.runIdByMessageId,
            [message.id]: event.runId as string
          }
        : prev.runIdByMessageId,
      tools: event.runId
        ? prev.tools.map(tool =>
            tool.runId === event.runId
              ? { ...tool, messageId: message.id }
              : tool
          )
        : prev.tools
    }
  }

  if (
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
    return {
      ...prev,
      runActive: false,
      activeRunId: null,
      liveDelta: '',
      activeBuildPlan: null,
      pendingApproval: null,
      approvalSubmitting: false,
      tools: finalizePendingTools(prev.tools, {
        runId: event.runId,
        endedAt: event.timestamp,
        reason
      }),
      todosByRunId:
        event.runId && prev.todosByRunId[event.runId]
          ? {
              ...prev.todosByRunId,
              [event.runId]: prev.todosByRunId[event.runId].map(todo =>
                todo.status === 'in_progress'
                  ? { ...todo, status: 'completed' as const }
                  : todo
              )
            }
          : prev.todosByRunId
    }
  }

  return prev
}
