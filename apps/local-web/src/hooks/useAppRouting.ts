import { matchPath, type Location } from 'react-router-dom'

import { type DashboardSection } from '@/components/agents/DashboardSidebar'
import { type DashboardSkeletonKind } from '@/components/agents/PageSkeletons'
import {
  isOnboardingPath,
  onboardingStepFromSlug
} from '@/lib/onboarding'
import {
  parseCatalogSkillId,
  type SkillsViewMode
} from '@/lib/skills-catalog'

export function useAppRouting(location: Location) {
  const detailRoute = matchPath(
    '/dashboard/skills/:skillName',
    location.pathname
  )
  const importGithubRoute = matchPath(
    '/dashboard/skills/import/github',
    location.pathname
  )
  const importFileRoute = matchPath(
    '/dashboard/skills/import/file',
    location.pathname
  )
  const trustedSourcesRoute = matchPath(
    '/dashboard/skills/trusted/sources',
    location.pathname
  )
  const catalogDetailRoute = matchPath(
    { path: '/dashboard/skills/catalog/*', end: true },
    location.pathname
  )
  const legacySkillRoute = matchPath(
    '/agents/skills/:skillName',
    location.pathname
  )
  const integrationDetailRoute = matchPath(
    '/dashboard/integrations/:integrationKey',
    location.pathname
  )
  const mcpCatalogDetailRoute = matchPath(
    '/dashboard/mcp/catalog/:catalogId',
    location.pathname
  )
  const mcpServerDetailRoute = matchPath(
    '/dashboard/mcp/server/:serverId',
    location.pathname
  )
  const sandboxDetailRoute = matchPath(
    '/dashboard/agent/sandbox/:kind',
    location.pathname
  )
  const onboardingRoute = matchPath('/onboarding/:slug', location.pathname)
  const onOnboardingPath = isOnboardingPath(location.pathname)
  const onboardingStep = onOnboardingPath
    ? onboardingStepFromSlug(onboardingRoute?.params.slug)
    : 0
  const legacyIntegrationRoute = matchPath(
    '/agents/integrations/:integrationKey',
    location.pathname
  )
  const isCatalogSearchPath = location.pathname === '/dashboard/skills/search'
  const isCatalogPath = location.pathname.startsWith('/dashboard/skills/catalog')
  const skillRouteName =
    isCatalogSearchPath || isCatalogPath
      ? null
      : (detailRoute?.params.skillName ?? legacySkillRoute?.params.skillName)
  const catalogSkillRoute = parseCatalogSkillId(
    catalogDetailRoute?.params['*']
      ? (() => {
          try {
            return decodeURIComponent(catalogDetailRoute.params['*'])
          } catch {
            return catalogDetailRoute.params['*']
          }
        })()
      : null
  )
  const integrationRouteName =
    integrationDetailRoute?.params.integrationKey ??
    legacyIntegrationRoute?.params.integrationKey ??
    null
  const decodedIntegrationRouteName = integrationRouteName
    ? (() => {
        try {
          return decodeURIComponent(integrationRouteName)
        } catch {
          return integrationRouteName
        }
      })()
    : null
  const normalizedIntegrationRouteName = decodedIntegrationRouteName
    ? decodedIntegrationRouteName.toLowerCase().replace(/[_\s]+/g, '-')
    : null
  const sessionRoute = matchPath('/agents/:sessionId', location.pathname)
  const projectRoute = matchPath('/projects/:projectId', location.pathname)
  const specialistNewRoute = matchPath(
    '/dashboard/specialists/new',
    location.pathname
  )
  const specialistEditRoute = matchPath(
    '/dashboard/specialists/:specialistId',
    location.pathname
  )
  const routeProjectId = projectRoute?.params.projectId ?? null
  const specialistsViewMode: 'list' | 'new' | 'edit' = specialistNewRoute
    ? 'new'
    : specialistEditRoute?.params.specialistId &&
        specialistEditRoute.params.specialistId !== 'new'
      ? 'edit'
      : 'list'
  const specialistsEditId =
    specialistsViewMode === 'edit'
      ? specialistEditRoute?.params.specialistId ?? null
      : null
  const isDashboard =
    location.pathname === '/dashboard' ||
    location.pathname.startsWith('/dashboard/')
  const dashboardSection: DashboardSection = location.pathname.startsWith(
    '/dashboard/status'
  ) || location.pathname.startsWith('/dashboard/server')
    ? 'status'
    : location.pathname.startsWith('/dashboard/general') ||
        location.pathname.startsWith('/dashboard/settings')
      ? 'general'
      : location.pathname.startsWith('/dashboard/agent/sandbox')
        ? 'agent_sandbox'
        : location.pathname.startsWith('/dashboard/agent/prompts')
          ? 'agent_prompts'
          : location.pathname.startsWith('/dashboard/agent')
            ? 'agent_runtime'
            : location.pathname.startsWith('/dashboard/models')
              ? 'models'
              : location.pathname.startsWith('/dashboard/datasets')
                ? 'datasets'
                : location.pathname.startsWith('/dashboard/tools')
                  ? 'tools'
                  : location.pathname.startsWith('/dashboard/doctor')
                    ? 'doctor'
                    : location.pathname.startsWith('/dashboard/storage')
                      ? 'storage'
                      : location.pathname.startsWith('/dashboard/environment')
                        ? 'environment'
                        : location.pathname.startsWith('/dashboard/skills')
                          ? 'skills'
                          : location.pathname.startsWith('/dashboard/specialists')
                            ? 'specialists'
                            : location.pathname.startsWith('/dashboard/integrations')
                              ? 'integrations'
                              : location.pathname.startsWith('/dashboard/mcp')
                                ? 'mcp'
                                : 'overview'
  const isSkills =
    dashboardSection === 'skills' ||
    location.pathname === '/agents/skills' ||
    Boolean(legacySkillRoute)
  const skillsViewMode: SkillsViewMode =
    catalogSkillRoute
    ? 'catalog_detail'
    : (detailRoute || legacySkillRoute) && !isCatalogSearchPath
    ? 'detail'
    : importGithubRoute
    ? 'import_github'
    : importFileRoute
    ? 'import_file'
    : trustedSourcesRoute
    ? 'trusted_sources'
    : 'list'
  const isIntegrations =
    dashboardSection === 'integrations' ||
    location.pathname === '/agents/integrations' ||
    Boolean(legacyIntegrationRoute)
  const isDashboardStatus = dashboardSection === 'status'
  const isDashboardGeneral = dashboardSection === 'general'
  const isDashboardAgentRuntime = dashboardSection === 'agent_runtime'
  const isDashboardAgentSandbox = dashboardSection === 'agent_sandbox'
  const isDashboardAgentPrompts = dashboardSection === 'agent_prompts'
  const isDashboardModels = dashboardSection === 'models'
  const isDashboardData = dashboardSection === 'datasets'
  const isDashboardTools = dashboardSection === 'tools'
  const isDashboardDoctor = dashboardSection === 'doctor'
  const isDashboardStorage = dashboardSection === 'storage'
  const isDashboardEnvironment = dashboardSection === 'environment'
  const isDashboardMcp = dashboardSection === 'mcp'
  const mcpCatalogDetailId = mcpCatalogDetailRoute?.params.catalogId
    ? decodeURIComponent(mcpCatalogDetailRoute.params.catalogId)
    : null
  const mcpServerDetailId = mcpServerDetailRoute?.params.serverId
    ? decodeURIComponent(mcpServerDetailRoute.params.serverId)
    : null
  const isMcpDetail = Boolean(mcpCatalogDetailId || mcpServerDetailId)
  const sandboxKindRaw = sandboxDetailRoute?.params.kind
  const sandboxKind =
    sandboxKindRaw === 'local' || sandboxKindRaw === 'modal'
      ? sandboxKindRaw
      : null
  const isSandboxLocalDetail = sandboxKind === 'local'
  const isSandboxModalDetail = sandboxKind === 'modal'
  const isDashboardSpecialists = dashboardSection === 'specialists'
  const isDashboardOverview = isDashboard && dashboardSection === 'overview'
  const isHome =
    location.pathname === '/' || location.pathname === '/agents/home'
  const isProjectHome = Boolean(routeProjectId)
  const isInspect = new URLSearchParams(location.search).get('inspect') === '1'
  const dashboardSkeletonKind: DashboardSkeletonKind = (() => {
    if (isHome || isProjectHome) return 'home'
    if (isDashboardOverview) return 'overview'
    if (isDashboardDoctor) return 'doctor'
    if (
      isDashboardStatus ||
      isDashboardGeneral ||
      isDashboardAgentRuntime ||
      isDashboardAgentPrompts ||
      isDashboardStorage ||
      isDashboardEnvironment
    ) {
      return 'settings'
    }
    if (isDashboardModels) return 'models'
    if (isDashboardData || isDashboardTools) return 'list'
    if (isDashboardSpecialists) {
      return specialistsViewMode === 'list' ? 'list' : 'detail'
    }
    if (isDashboardMcp || isIntegrations) return 'cards'
    if (isDashboardAgentSandbox) {
      return sandboxKind ? 'settings' : 'cards'
    }
    if (isSkills) {
      return skillsViewMode === 'list' ? 'cards' : 'detail'
    }
    return 'detail'
  })()
  const sessionId =
    !isDashboard &&
    !isSkills &&
    !isIntegrations &&
    !isHome &&
    !isProjectHome &&
    sessionRoute?.params.sessionId &&
    sessionRoute.params.sessionId !== 'home' &&
    sessionRoute.params.sessionId !== 'skills' &&
    sessionRoute.params.sessionId !== 'integrations'
      ? sessionRoute.params.sessionId
      : null

  return {
    detailRoute,
    importGithubRoute,
    importFileRoute,
    trustedSourcesRoute,
    catalogDetailRoute,
    legacySkillRoute,
    integrationDetailRoute,
    mcpCatalogDetailRoute,
    mcpServerDetailRoute,
    sandboxDetailRoute,
    onboardingRoute,
    onOnboardingPath,
    onboardingStep,
    legacyIntegrationRoute,
    isCatalogSearchPath,
    isCatalogPath,
    skillRouteName,
    catalogSkillRoute,
    integrationRouteName,
    decodedIntegrationRouteName,
    normalizedIntegrationRouteName,
    sessionRoute,
    projectRoute,
    specialistNewRoute,
    specialistEditRoute,
    routeProjectId,
    specialistsViewMode,
    specialistsEditId,
    isDashboard,
    dashboardSection,
    isSkills,
    skillsViewMode,
    isIntegrations,
    isDashboardStatus,
    isDashboardGeneral,
    isDashboardAgentRuntime,
    isDashboardAgentSandbox,
    isDashboardAgentPrompts,
    isDashboardModels,
    isDashboardData,
    isDashboardTools,
    isDashboardDoctor,
    isDashboardStorage,
    isDashboardEnvironment,
    isDashboardMcp,
    mcpCatalogDetailId,
    mcpServerDetailId,
    isMcpDetail,
    sandboxKind,
    isSandboxLocalDetail,
    isSandboxModalDetail,
    isDashboardSpecialists,
    isDashboardOverview,
    isHome,
    isProjectHome,
    isInspect,
    dashboardSkeletonKind,
    sessionId
  }
}
