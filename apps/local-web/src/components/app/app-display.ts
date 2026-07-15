import type { AgentSession, IntegrationSummary } from '@sandwalk/agent-ui-core'

import { groupSessions } from '@/lib/sessions'

const CONCURRENT_RUN_SOFT_LIMIT = 3

export { CONCURRENT_RUN_SOFT_LIMIT }

export function resolveSelectedIntegrationKey(
  decodedIntegrationRouteName: string | null,
  normalizedIntegrationRouteName: string | null,
  integrations: IntegrationSummary[]
) {
  if (!decodedIntegrationRouteName) return null
  return (
    integrations.find(item => {
      const normalizedKey = item.key.toLowerCase().replace(/[_\s]+/g, '-')
      const normalizedName = item.name.toLowerCase().replace(/[_\s]+/g, '-')
      return (
        item.key === decodedIntegrationRouteName ||
        normalizedKey === normalizedIntegrationRouteName ||
        normalizedName === normalizedIntegrationRouteName
      )
    })?.key ?? decodedIntegrationRouteName
  )
}

export function computeRunningCount(sessions: AgentSession[]) {
  const runningSessionIdsKey = sessions
    .filter(item => item.status === 'running')
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
  isDashboardAgentRuntime: boolean
  isDashboardAgentPrompts: boolean
  isDashboardModels: boolean
  isDashboardData: boolean
  isDashboardTools: boolean
  isDashboardDoctor: boolean
  isDashboardStorage: boolean
  isDashboardEnvironment: boolean
  isSkills: boolean
  isDashboardSpecialists: boolean
  isIntegrations: boolean
  isDashboardMcp: boolean
  isHome: boolean
  isProjectHome: boolean
  sessionTitle: string | undefined
}) {
  if (input.isDashboardOverview) return 'Overview'
  if (input.isDashboardStatus) return 'Status'
  if (input.isDashboardGeneral) return 'General'
  if (input.isDashboardAgentRuntime) return 'Runtime'
  if (input.isDashboardAgentPrompts) return 'Prompts'
  if (input.isDashboardModels) return 'Models'
  if (input.isDashboardData) return 'Datasets'
  if (input.isDashboardTools) return 'Tools'
  if (input.isDashboardDoctor) return 'Doctor'
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
  isProjectHome: boolean
  isSkills: boolean
  isIntegrations: boolean
  sessionId: string | null
  openTabsLength: number
}) {
  return (
    !input.isDashboard &&
    !input.isHome &&
    !input.isProjectHome &&
    !input.isSkills &&
    !input.isIntegrations &&
    (Boolean(input.sessionId) || input.openTabsLength > 0)
  )
}

export function buildSessionSidebarModel(input: {
  sessions: AgentSession[]
  activeProjectId: string | null
  openTabIds: string[]
}) {
  const displayedSessions = input.activeProjectId
    ? input.sessions.filter(item => item.projectId === input.activeProjectId)
    : input.sessions
  const sections = groupSessions(displayedSessions)
  const openTabs = input.openTabIds
    .map(id => input.sessions.find(item => item.id === id))
    .filter((item): item is AgentSession => Boolean(item))
    .filter(
      item => !input.activeProjectId || item.projectId === input.activeProjectId
    )
  return { displayedSessions, sections, openTabs }
}
