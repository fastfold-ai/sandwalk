import type { Location } from 'react-router-dom'

import { type DashboardSection } from '@/components/agents/DashboardSidebar'
import { type DashboardSkeletonKind } from '@/components/agents/PageSkeletons'
import {
  decodeRouteParam,
  matchAppRoutes,
  resolveDashboardSection
} from '@/hooks/app-routing-helpers'
import {
  isOnboardingPath,
  onboardingStepFromSlug
} from '@/lib/onboarding'
import {
  parseCatalogSkillId,
  type SkillsViewMode
} from '@/lib/skills-catalog'

export function useAppRouting(location: Location) {
  const routes = matchAppRoutes(location.pathname)
  const onOnboardingPath = isOnboardingPath(location.pathname)
  const onboardingStep = onOnboardingPath
    ? onboardingStepFromSlug(routes.onboardingRoute?.params.slug)
    : 0
  const isCatalogSearchPath = location.pathname === '/dashboard/skills/search'
  const isCatalogPath = location.pathname.startsWith('/dashboard/skills/catalog')
  const skillRouteName =
    isCatalogSearchPath || isCatalogPath
      ? null
      : (routes.detailRoute?.params.skillName ??
        routes.legacySkillRoute?.params.skillName)
  const catalogSkillRoute = parseCatalogSkillId(
    decodeRouteParam(routes.catalogDetailRoute?.params['*'])
  )
  const integrationRouteName =
    routes.integrationDetailRoute?.params.integrationKey ??
    routes.legacyIntegrationRoute?.params.integrationKey ??
    null
  const decodedIntegrationRouteName = decodeRouteParam(
    integrationRouteName ?? undefined
  )
  const normalizedIntegrationRouteName = decodedIntegrationRouteName
    ? decodedIntegrationRouteName.toLowerCase().replace(/[_\s]+/g, '-')
    : null
  const routeProjectId = routes.projectRoute?.params.projectId ?? null
  const specialistsViewMode: 'list' | 'new' | 'edit' = routes.specialistNewRoute
    ? 'new'
    : routes.specialistEditRoute?.params.specialistId &&
        routes.specialistEditRoute.params.specialistId !== 'new'
      ? 'edit'
      : 'list'
  const specialistsEditId =
    specialistsViewMode === 'edit'
      ? routes.specialistEditRoute?.params.specialistId ?? null
      : null
  const isDashboard =
    location.pathname === '/dashboard' ||
    location.pathname.startsWith('/dashboard/')
  const dashboardSection: DashboardSection = resolveDashboardSection(
    location.pathname
  )
  const isSkills =
    dashboardSection === 'skills' ||
    location.pathname === '/agents/skills' ||
    Boolean(routes.legacySkillRoute)
  const skillsViewMode: SkillsViewMode = catalogSkillRoute
    ? 'catalog_detail'
    : (routes.detailRoute || routes.legacySkillRoute) && !isCatalogSearchPath
      ? 'detail'
      : routes.importGithubRoute
        ? 'import_github'
        : routes.importFileRoute
          ? 'import_file'
          : routes.trustedSourcesRoute
            ? 'trusted_sources'
            : 'list'
  const isIntegrations =
    dashboardSection === 'integrations' ||
    location.pathname === '/agents/integrations' ||
    Boolean(routes.legacyIntegrationRoute)
  const isDashboardStatus = false
  const isDashboardGeneral = dashboardSection === 'general'
  const isDashboardAgentRuntime = dashboardSection === 'agent_runtime'
  const isDashboardAgentSandbox = dashboardSection === 'agent_sandbox'
  const isDashboardAgentPrompts = dashboardSection === 'context'
  const isDashboardVoice = dashboardSection === 'voice'
  const isDashboardModels = dashboardSection === 'models'
  const isDashboardData = dashboardSection === 'datasets'
  const isDashboardTools = dashboardSection === 'tools'
  const isDashboardDoctor = dashboardSection === 'doctor'
  const isDashboardStorage = dashboardSection === 'storage'
  const isDashboardEnvironment = dashboardSection === 'environment'
  const isDashboardMcp = dashboardSection === 'mcp'
  const mcpCatalogDetailId = decodeRouteParam(
    routes.mcpCatalogDetailRoute?.params.catalogId
  )
  const mcpServerDetailId = decodeRouteParam(
    routes.mcpServerDetailRoute?.params.serverId
  )
  const isMcpDetail = Boolean(mcpCatalogDetailId || mcpServerDetailId)
  const sandboxKindRaw = routes.sandboxDetailRoute?.params.kind
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
  const isLibrary =
    location.pathname === '/library' ||
    location.pathname.startsWith('/library/')
  const isProjectHome = Boolean(routeProjectId)
  const isInspect = new URLSearchParams(location.search).get('inspect') === '1'
  const dashboardSkeletonKind: DashboardSkeletonKind = (() => {
    if (isHome || isLibrary || isProjectHome) return 'home'
    if (isDashboardOverview) return 'overview'
    if (isDashboardDoctor) return 'doctor'
    if (
      isDashboardStatus ||
      isDashboardGeneral ||
      isDashboardAgentRuntime ||
      isDashboardAgentPrompts ||
      isDashboardVoice ||
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
    !isLibrary &&
    !isProjectHome &&
    routes.sessionRoute?.params.sessionId &&
    routes.sessionRoute.params.sessionId !== 'home' &&
    routes.sessionRoute.params.sessionId !== 'skills' &&
    routes.sessionRoute.params.sessionId !== 'integrations'
      ? routes.sessionRoute.params.sessionId
      : null

  return {
    ...routes,
    onOnboardingPath,
    onboardingStep,
    isCatalogSearchPath,
    isCatalogPath,
    skillRouteName,
    catalogSkillRoute,
    integrationRouteName,
    decodedIntegrationRouteName,
    normalizedIntegrationRouteName,
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
    isDashboardVoice,
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
    isLibrary,
    isProjectHome,
    isInspect,
    dashboardSkeletonKind,
    sessionId
  }
}
