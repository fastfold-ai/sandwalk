import type {
  AgentMessage,
  AgentPlanCard,
  AgentSession,
  AgentTodo,
  PendingHitlApproval
} from '@sandwalk/agent-ui-core'

import type { TranscriptTool } from '@/components/agents/ToolCard'

export type RunTokenUsage = {
  inputTokens: number
  outputTokens: number
  tokensPerSecond?: number | null
  promptTokensPerSecond?: number | null
  promptEvalSeconds?: number | null
  generationSeconds?: number | null
  timeToFirstToken?: number | null
  estimated?: boolean
}

export type SessionChatState = {
  messages: AgentMessage[]
  tools: TranscriptTool[]
  todosByRunId: Record<string, AgentTodo[]>
  plansByRunId: Record<string, AgentPlanCard[]>
  runIdByMessageId: Record<string, string>
  usageByRunId: Record<string, RunTokenUsage>
  tokenUsage: RunTokenUsage
  activeRunId: string | null
  runActive: boolean
  liveDelta: string
  composer: string
  composerSkills: string[]
  composerFiles: string[]
  queuedMessages: QueuedMessage[]
  expandedToolRunKeys: Record<string, boolean>
  messagesLoaded: boolean
  /** Plan currently being built/executed (set by Build action). */
  activeBuildPlan: AgentPlanCard | null
  /** Plan paths the user already started building — hide Created Plan cards. */
  builtPlanPaths: string[]
  /** Pending Deep Agents HITL interrupt awaiting desktop decisions. */
  pendingApproval: PendingHitlApproval | null
  approvalSubmitting: boolean
}

export type QueuedMessage = {
  id: string
  text: string
}

export function emptySessionChatState(): SessionChatState {
  return {
    messages: [],
    tools: [],
    todosByRunId: {},
    plansByRunId: {},
    runIdByMessageId: {},
    usageByRunId: {},
    tokenUsage: { inputTokens: 0, outputTokens: 0 },
    activeRunId: null,
    runActive: false,
    liveDelta: '',
    composer: '',
    composerSkills: [],
    composerFiles: [],
    queuedMessages: [],
    expandedToolRunKeys: {},
    messagesLoaded: false,
    activeBuildPlan: null,
    builtPlanPaths: [],
    pendingApproval: null,
    approvalSubmitting: false
  }
}

export function relativeTime(value: string) {
  const elapsed = Math.max(0, Date.now() - new Date(value).getTime())
  const minutes = Math.floor(elapsed / 60_000)
  if (minutes < 1) return 'now'
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}

export function formatMessagePopoverDate(value: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  }).format(date)
}

export async function downloadMarkdown(filename: string, content: string) {
  const { downloadTextWithLocation } = await import('@/lib/workspace-download')
  await downloadTextWithLocation(filename, content)
}

// Two full turns (user + assistant × 2) before asking the model for a title.
export const AUTO_TITLE_FIRST_RESPONSE_THRESHOLD = 4

export function isLowSignalTitle(title: string): boolean {
  const normalized = String(title || '')
    .trim()
    .toLowerCase()
  if (!normalized) return true
  const defaults = new Set([
    'untitled',
    'untitled session',
    'untitled thread',
    'new chat',
    'new agent',
    'new agent session',
    'new research session'
  ])
  if (defaults.has(normalized)) return true
  return (
    normalized.includes('greeting chat') ||
    normalized.includes('casual greeting') ||
    normalized === 'general conversation' ||
    normalized === 'small talk'
  )
}
export function groupSessions(sessions: AgentSession[]) {
  const now = new Date()
  const today = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
  ).getTime()
  const yesterday = today - 86_400_000
  const pinned = sessions.filter(item => item.organizeLabel === 'pinned')
  const archived = sessions.filter(item => item.organizeLabel === 'archive')
  const ordinary = sessions.filter(
    item => item.organizeLabel !== 'pinned' && item.organizeLabel !== 'archive'
  )
  return [
    { id: 'pinned', title: 'Pinned', items: pinned },
    {
      id: 'today',
      title: 'Today',
      items: ordinary.filter(
        item =>
          new Date(item.lastMessageAt || item.updatedAt).getTime() >= today
      )
    },
    {
      id: 'yesterday',
      title: 'Yesterday',
      items: ordinary.filter(item => {
        const timestamp = new Date(
          item.lastMessageAt || item.updatedAt
        ).getTime()
        return timestamp >= yesterday && timestamp < today
      })
    },
    {
      id: 'older',
      title: 'Older',
      items: ordinary.filter(
        item =>
          new Date(item.lastMessageAt || item.updatedAt).getTime() < yesterday
      )
    },
    { id: 'archive', title: 'Archived', items: archived }
  ].filter(section => section.items.length > 0)
}

export function visibleSessionIds(
  sections: ReturnType<typeof groupSessions>,
  collapsed: Record<string, boolean>
): string[] {
  const ids: string[] = []
  for (const section of sections) {
    if (collapsed[section.id]) continue
    for (const item of section.items) ids.push(item.id)
  }
  return ids
}
