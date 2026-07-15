import type { AgentEvent } from '@sandwalk/agent-ui-core'

import { composerToMessage } from '@/components/agents/composer-parts'
import type { SessionChatState } from '@/lib/sessions'

export type ChatPatch =
  | Partial<SessionChatState>
  | ((prev: SessionChatState) => SessionChatState)

export function applyChatPatch(
  prev: SessionChatState,
  patch: ChatPatch
): SessionChatState {
  return typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
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

export function reduceChatOnAgentEvent(
  prev: SessionChatState,
  event: AgentEvent
): SessionChatState {
  if (event.type === 'run.started') {
    return {
      ...prev,
      runActive: true,
      activeRunId: event.runId,
      liveDelta: ''
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
          runId: event.runId,
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
    return {
      ...prev,
      tools: prev.tools.map(tool =>
        tool.id === event.payload.toolCallId
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
        ...prev.todosByRunId,
        [event.runId as string]: event.payload.todos
      }
    }
  }

  if (event.type === 'run.usage') {
    const payload = event.payload as Record<string, unknown>
    const nextUsage = {
      inputTokens: Number(payload.inputTokens ?? payload.input_tokens ?? 0),
      outputTokens: Number(payload.outputTokens ?? payload.output_tokens ?? 0)
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
    return {
      ...prev,
      runActive: false,
      activeRunId: null,
      liveDelta: '',
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
