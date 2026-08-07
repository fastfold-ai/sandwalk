import type { AgentSession, IntegrationSummary } from '@sandwalk/agent-ui-core'

import { slugifyIntegrationRoute } from '@/components/agents/dashboard-main-view-helpers'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import { groupSessions } from '@/lib/sessions'

const CONCURRENT_RUN_SOFT_LIMIT = 8

export { CONCURRENT_RUN_SOFT_LIMIT }

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

export function computeRunningCount(sessions: AgentSession[]) {
  const runningSessionIdsKey = sessions
    .filter(
      item => item.status === 'running' || item.status === 'awaiting_approval'
    )
    .map(item => item.id)
    .sort()
    .join(',')
  return runningSessionIdsKey
    ? runningSessionIdsKey.split(',').length
    : 0
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
  activeProjectId: string | null
  openTabIds: string[]
  /** Keep the open chat visible in the tab strip while its project assignment catches up. */
  activeSessionId?: string | null
}) {
  const displayedSessions = input.activeProjectId
    ? input.sessions.filter(item => item.projectId === input.activeProjectId)
    : input.sessions
  const sections = groupSessions(displayedSessions)
  const openTabs = input.openTabIds
    .map(id => input.sessions.find(item => item.id === id))
    .filter((item): item is AgentSession => Boolean(item))
    .filter(
      item =>
        !input.activeProjectId ||
        item.projectId === input.activeProjectId ||
        item.id === input.activeSessionId
    )
  return { displayedSessions, sections, openTabs }
}
