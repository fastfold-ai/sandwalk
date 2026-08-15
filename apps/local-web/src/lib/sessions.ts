import type {
  AgentMessage,
  AgentPlanCard,
  AgentSession,
  AgentTodo,
  PendingHitlApproval,
  SessionGroup
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

/** Calendar-day label: Today / Yesterday / `10d ago`. */
export function relativeDayLabel(value: string, now = new Date()) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const startOfToday = new Date(now)
  startOfToday.setHours(0, 0, 0, 0)
  const startOfTarget = new Date(date)
  startOfTarget.setHours(0, 0, 0, 0)
  const dayDiff = Math.round(
    (startOfToday.getTime() - startOfTarget.getTime()) / 86_400_000
  )
  if (dayDiff <= 0) return 'Today'
  if (dayDiff === 1) return 'Yesterday'
  return `${dayDiff}d ago`
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

/*
 * Modelo unificado del sidebar y de todas las listas donde chats y grupos
 * conviven como pares (misma jerarquía). Cada item de las secciones es un
 * `TabItem` polimórfico — puede ser un chat suelto o un grupo con sus
 * chats hijos. Los helpers downstream (visibleSessionIds, sidebar-session-
 * list, dropdown de tabs) iteran sobre `TabItem[]` y renderizan según kind.
 */
export type TabItem =
  | {
      kind: 'chat'
      id: string
      session: AgentSession
      lastActivity: number
    }
  | {
      kind: 'group'
      id: string
      group: SessionGroup
      children: AgentSession[]
      lastActivity: number
    }

export type TabItemSection = {
  id: string
  title: string
  items: TabItem[]
}

function sessionLastActivity(item: AgentSession): number {
  return new Date(item.lastMessageAt || item.updatedAt).getTime()
}

/**
 * Como `groupSessions`, pero incluye también los grupos de split view como
 * items dentro de las secciones. Los chats que viven dentro de un grupo NO
 * aparecen sueltos en las secciones — solo dentro del grupo (como children).
 */
export function groupTabItems(
  sessions: AgentSession[],
  groups: SessionGroup[] = [],
  /**
   * Optional pool used only to resolve `group.children` when the group
   * contains chatIds that don't belong to the currently scoped `sessions`
   * list (cross-project splits). Falls back to `sessions` when omitted so
   * existing callers stay unchanged.
   */
  sessionsForGroupChildren?: AgentSession[]
): TabItemSection[] {
  const now = new Date()
  const today = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
  ).getTime()
  const yesterday = today - 86_400_000

  const sessionsById = new Map<string, AgentSession>()
  for (const session of sessions) sessionsById.set(session.id, session)
  const groupChildrenById =
    sessionsForGroupChildren && sessionsForGroupChildren !== sessions
      ? new Map(sessionsForGroupChildren.map(s => [s.id, s]))
      : sessionsById

  const chatIdsInGroups = new Set<string>()
  for (const g of groups) for (const id of g.chatIds) chatIdsInGroups.add(id)

  const chatItems: TabItem[] = sessions
    .filter(item => !chatIdsInGroups.has(item.id))
    .map(item => ({
      kind: 'chat' as const,
      id: item.id,
      session: item,
      lastActivity: sessionLastActivity(item)
    }))

  const groupItems: TabItem[] = groups.map(group => {
    const children = group.chatIds
      .map(id => groupChildrenById.get(id))
      .filter((s): s is AgentSession => Boolean(s))
    // Actividad del grupo = la última actividad de cualquiera de sus chats.
    const lastActivity = children.reduce(
      (max, s) => Math.max(max, sessionLastActivity(s)),
      0
    )
    return {
      kind: 'group' as const,
      id: group.id,
      group,
      children,
      lastActivity
    }
  })

  const all = [...chatItems, ...groupItems]

  const isPinned = (item: TabItem) =>
    item.kind === 'chat'
      ? item.session.organizeLabel === 'pinned'
      : item.group.pinned
  const isArchived = (item: TabItem) =>
    item.kind === 'chat' && item.session.organizeLabel === 'archive'
  // Los grupos no tienen "archived" — solo chats pueden estar archivados.

  // Dentro de cada sección, "más reciente primero" — sirve para que un
  // chat/split recién creado aparezca arriba de todo en Today, y para que
  // los grupos (que antes iban al final) se ordenen naturalmente por su
  // actividad interna (max de sus chats hijos).
  const sortByRecent = (a: TabItem, b: TabItem) =>
    b.lastActivity - a.lastActivity

  const pinned = all.filter(isPinned).sort(sortByRecent)
  const archived = all.filter(isArchived).sort(sortByRecent)
  const ordinary = all
    .filter(item => !isPinned(item) && !isArchived(item))
    .sort(sortByRecent)

  return [
    { id: 'pinned', title: 'Pinned', items: pinned },
    {
      id: 'today',
      title: 'Today',
      items: ordinary.filter(item => item.lastActivity >= today)
    },
    {
      id: 'yesterday',
      title: 'Yesterday',
      items: ordinary.filter(
        item => item.lastActivity >= yesterday && item.lastActivity < today
      )
    },
    {
      id: 'older',
      title: 'Older',
      items: ordinary.filter(item => item.lastActivity < yesterday)
    },
    { id: 'archive', title: 'Archived', items: archived }
  ].filter(section => section.items.length > 0)
}

export function visibleSessionIds(
  sections: TabItemSection[],
  collapsed: Record<string, boolean>
): string[] {
  const ids: string[] = []
  for (const section of sections) {
    if (collapsed[section.id]) continue
    for (const item of section.items) {
      ids.push(item.id)
      // Los chats hijos de un grupo también son "visibles" en la vista si el
      // grupo no está colapsado (colapso del grupo se maneja aparte, por
      // grupo, dentro del sidebar).
      if (item.kind === 'group') {
        for (const child of item.children) ids.push(child.id)
      }
    }
  }
  return ids
}
