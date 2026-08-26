import type {
  AgentSession,
  IntegrationSummary,
  SessionGroup
} from '@sandwalk/agent-ui-core'

import { slugifyIntegrationRoute } from '@/components/agents/dashboard-main-view-helpers'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import { groupTabItems, type TabItem } from '@/lib/sessions'
import { assertNever } from '@/lib/strip-item'

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
  /** FAS-107: terminals of the active project (optional). */
  terminals?: import('@sandwalk/agent-ui-core').TerminalSession[]
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
    g.itemIds.some(id => displayedIds.has(id))
  )
  // Pass `input.sessions` (unfiltered) so groupTabItems can resolve foreign
  // chats inside cross-project groups. Standalone chats stay scoped via
  // `displayedSessions`; only group `children` benefit from the wider pool.
  // FAS-107: same scope filter as chats — terminals of the active
  // project only. Cross-project terminals aren't shown outside their
  // home project (parallel to sessions filtering).
  const displayedTerminals = input.activeProjectId
    ? (input.terminals ?? []).filter(
        t => t.projectId === input.activeProjectId
      )
    : input.terminals ?? []
  const sections = groupTabItems(
    displayedSessions,
    applicableGroups,
    input.sessions,
    displayedTerminals
  )
  // `openTabs` mezcla chats y grupos en el orden real de `openTabIds`. Los
  // items que no se pueden resolver (chat en otro scope, grupo aún cargando)
  // se saltean. `activeSessionId` respeta la visibilidad del chat/grupo
  // activo aunque el filtro de proyecto lo excluiría.
  const sessionsById = new Map(input.sessions.map(s => [s.id, s]))
  const groupsById = new Map(input.tabGroups.map(g => [g.id, g]))
  // FAS-107 X4.4-hotfix: reconocer terminales en `openTabs`. Antes solo
  // se resolvían chats y grupos → cuando la strip tenía SOLO terminales,
  // `openTabs.length` daba 0 y `computeShowSessionTabs` retornaba false
  // → aparecía "New Chat" en franja negra arriba mientras el chip del
  // terminal seguía visible por otra vía. Cruce visual feo.
  const terminalsById = new Map(
    (input.terminals ?? []).map(t => [t.id, t])
  )
  const openTabs: TabItem[] = input.openTabIds
    .map<TabItem | null>(id => {
      const group = groupsById.get(id)
      if (group) {
        const children = group.itemIds
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
      const terminal = terminalsById.get(id)
      if (terminal) {
        return {
          kind: 'terminal',
          id: terminal.id,
          terminal,
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
      // FAS-107 X5.3 · exhaustive switch con `assertNever`. Si en el
      // futuro agregamos un `kind` a `TabItem` (nota, canvas, mcp),
      // TypeScript señala este bloque en compile time — no puede haber
      // "consumidor olvidó tipo X" que compile con éxito.
      switch (item.kind) {
        case 'chat':
          return item.session.projectId === input.activeProjectId
        case 'terminal':
          return (item.terminal.projectId ?? null) === input.activeProjectId
        case 'group':
          return item.children.some(
            s => s.projectId === input.activeProjectId
          )
        default:
          return assertNever(item)
      }
    })
  return { displayedSessions, sections, openTabs }
}
