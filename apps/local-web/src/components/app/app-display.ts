import type {
  AgentSession,
  IntegrationSummary,
  SessionGroup
} from '@sandwalk/agent-ui-core'

import { slugifyIntegrationRoute } from '@/components/agents/dashboard-main-view-helpers'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import { groupTabItems, type TabItem } from '@/lib/sessions'

export function resolveSelectedIntegrationKey(
  decodedIntegrationRouteName: string | null,
  normalizedIntegrationRouteName: string | null,
  integrations: IntegrationSummary[]
) {
  if (!decodedIntegrationRouteName) return null
  const routeSlug =
    slugifyIntegrationRoute(
      normalizedIntegrationRouteName || decodedIntegrationRouteName
    ) || decodedIntegrationRouteName
  const matched = integrations.find(item => {
    const keySlug = slugifyIntegrationRoute(item.key)
    const nameSlug = slugifyIntegrationRoute(item.name)
    return (
      item.key === decodedIntegrationRouteName ||
      keySlug === routeSlug ||
      nameSlug === routeSlug
    )
  })
  // Prefer a real catalog key; never return a display slug that would bounce
  // the detail view back to the list (e.g. "moonshot-kimi" vs key "moonshot").
  return matched?.key ?? null
}

export function resolveActiveTitle(input: {
  isDashboardOverview: boolean
  isDashboardStatus: boolean
  isDashboardGeneral: boolean
  isDashboardAppearance: boolean
  isDashboardAgentRuntime: boolean
  isDashboardAgentSecurity: boolean
  isDashboardAgentPrompts: boolean
  isDashboardVoice: boolean
  isDashboardModels: boolean
  isDashboardData: boolean
  isDashboardTools: boolean
  isDashboardDoctor: boolean
  isDashboardBench: boolean
  isDashboardStorage: boolean
  isDashboardEnvironment: boolean
  isSkills: boolean
  isDashboardSpecialists: boolean
  isIntegrations: boolean
  isDashboardMcp: boolean
  isHome: boolean
  isLibrary: boolean
  isSites: boolean
  isProjectHome: boolean
  sessionTitle: string | undefined
}) {
  if (input.isLibrary) return 'Library'
  if (input.isSites) return 'Sites'
  if (input.isDashboardOverview) return 'Overview'
  if (input.isDashboardStatus) return 'Status'
  if (input.isDashboardGeneral) return 'General'
  if (input.isDashboardAppearance) return 'Appearance'
  if (input.isDashboardAgentRuntime) return 'Runtime'
  if (input.isDashboardAgentSecurity) return 'Security'
  if (input.isDashboardAgentPrompts) return 'Context'
  if (input.isDashboardVoice) return 'Voice'
  if (input.isDashboardModels) return 'Models'
  if (input.isDashboardData) return 'Datasets'
  if (input.isDashboardTools) return 'Tools'
  if (input.isDashboardDoctor) return 'Doctor'
  if (input.isDashboardBench) return 'Benchmarking'
  if (input.isDashboardStorage) return 'Storage'
  if (input.isDashboardEnvironment) return 'Environment'
  if (input.isSkills) return 'Skills'
  if (input.isDashboardSpecialists) return 'Specialists'
  if (input.isIntegrations) return 'Integrations'
  if (input.isDashboardMcp) return 'MCPs'
  if (input.isHome || input.isProjectHome) return 'Home'
  return input.sessionTitle || 'New Chat'
}

export function computeShowSessionTabs(input: {
  isDashboard: boolean
  isHome: boolean
  isLibrary: boolean
  isSites: boolean
  isProjectHome: boolean
  isSkills: boolean
  isIntegrations: boolean
  sessionId: string | null
  openTabsLength: number
}) {
  const realSession = Boolean(
    input.sessionId && !isDraftAgentSessionId(input.sessionId)
  )
  return (
    !input.isDashboard &&
    !input.isHome &&
    !input.isLibrary &&
    !input.isSites &&
    !input.isProjectHome &&
    !input.isSkills &&
    !input.isIntegrations &&
    (realSession || input.openTabsLength > 0)
  )
}

export function buildSessionSidebarModel(input: {
  sessions: AgentSession[]
  tabGroups: SessionGroup[]
  activeProjectId: string | null
  openTabIds: string[]
  /** Keep the open chat visible in the tab strip while its project assignment catches up. */
  activeSessionId?: string | null
}) {
  const displayedSessions = input.activeProjectId
    ? input.sessions.filter(item => item.projectId === input.activeProjectId)
    : input.sessions
  // Grupos que aplican al scope actual: al menos uno de sus chatIds vive en
  // `displayedSessions`. Los grupos son por-scope-de-proyecto ya en el store
  // (`useAppTabGroups` usa `projectTabsKey`), esta segunda vuelta filtra por
  // si acaso quedaron grupos con chats de otros scopes al vuelo.
  const displayedIds = new Set(displayedSessions.map(item => item.id))
  const applicableGroups = input.tabGroups.filter(g =>
    g.chatIds.some(id => displayedIds.has(id))
  )
  const sections = groupTabItems(displayedSessions, applicableGroups)
  // `openTabs` mezcla chats y grupos en el orden real de `openTabIds`. Los
  // items que no se pueden resolver (chat en otro scope, grupo aún cargando)
  // se saltean. `activeSessionId` respeta la visibilidad del chat/grupo
  // activo aunque el filtro de proyecto lo excluiría.
  const sessionsById = new Map(input.sessions.map(s => [s.id, s]))
  const groupsById = new Map(input.tabGroups.map(g => [g.id, g]))
  const openTabs: TabItem[] = input.openTabIds
    .map<TabItem | null>(id => {
      const group = groupsById.get(id)
      if (group) {
        const children = group.chatIds
          .map(cid => sessionsById.get(cid))
          .filter((s): s is AgentSession => Boolean(s))
        return {
          kind: 'group',
          id: group.id,
          group,
          children,
          lastActivity: 0
        }
      }
      const session = sessionsById.get(id)
      if (session) {
        return {
          kind: 'chat',
          id: session.id,
          session,
          lastActivity: 0
        }
      }
      return null
    })
    .filter((item): item is TabItem => Boolean(item))
    .filter(item => {
      if (!input.activeProjectId) return true
      if (item.id === input.activeSessionId) return true
      if (item.kind === 'chat') {
        return item.session.projectId === input.activeProjectId
      }
      // Grupos: aplican si al menos uno de sus chats pertenece al scope.
      return item.children.some(
        s => s.projectId === input.activeProjectId
      )
    })
  return { displayedSessions, sections, openTabs }
}
