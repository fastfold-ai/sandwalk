import { matchPath, type PathMatch } from 'react-router-dom'

export type AppRouteMatches = {
  detailRoute: PathMatch<'skillName'> | null
  importGithubRoute: PathMatch<string> | null
  importFileRoute: PathMatch<string> | null
  trustedSourcesRoute: PathMatch<string> | null
  catalogDetailRoute: PathMatch<'*'> | null
  legacySkillRoute: PathMatch<'skillName'> | null
  integrationDetailRoute: PathMatch<'integrationKey'> | null
  mcpCatalogDetailRoute: PathMatch<'catalogId'> | null
  mcpServerDetailRoute: PathMatch<'serverId'> | null
  sandboxDetailRoute: PathMatch<'kind'> | null
  onboardingRoute: PathMatch<'slug'> | null
  legacyIntegrationRoute: PathMatch<'integrationKey'> | null
  sessionRoute: PathMatch<'sessionId'> | null
  projectRoute: PathMatch<'projectId'> | null
  specialistNewRoute: PathMatch<string> | null
  specialistEditRoute: PathMatch<'specialistId'> | null
}

export function matchAppRoutes(pathname: string): AppRouteMatches {
  return {
    detailRoute: matchPath('/dashboard/skills/:skillName', pathname),
    importGithubRoute: matchPath('/dashboard/skills/import/github', pathname),
    importFileRoute: matchPath('/dashboard/skills/import/file', pathname),
    trustedSourcesRoute: matchPath(
      '/dashboard/skills/trusted/sources',
      pathname
    ),
    catalogDetailRoute: matchPath(
      { path: '/dashboard/skills/catalog/*', end: true },
      pathname
    ),
    legacySkillRoute: matchPath('/agents/skills/:skillName', pathname),
    integrationDetailRoute: matchPath(
      '/dashboard/integrations/:integrationKey',
      pathname
    ),
    mcpCatalogDetailRoute: matchPath(
      '/dashboard/mcp/catalog/:catalogId',
      pathname
    ),
    mcpServerDetailRoute: matchPath('/dashboard/mcp/server/:serverId', pathname),
    sandboxDetailRoute: matchPath('/dashboard/agent/sandbox/:kind', pathname),
    onboardingRoute: matchPath('/onboarding/:slug', pathname),
    legacyIntegrationRoute: matchPath(
      '/agents/integrations/:integrationKey',
      pathname
    ),
    sessionRoute: matchPath('/agents/:sessionId', pathname),
    projectRoute: matchPath('/projects/:projectId', pathname),
    specialistNewRoute: matchPath('/dashboard/specialists/new', pathname),
    specialistEditRoute: matchPath(
      '/dashboard/specialists/:specialistId',
      pathname
    )
  }
}

export function decodeRouteParam(value: string | undefined) {
  if (!value) return null
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

export function resolveDashboardSection(pathname: string) {
  if (
    pathname.startsWith('/dashboard/general') ||
    pathname.startsWith('/dashboard/settings')
  ) {
    return 'general' as const
  }
  if (pathname.startsWith('/dashboard/agent/sandbox')) {
    return 'agent_sandbox' as const
  }
  if (pathname.startsWith('/dashboard/context')) {
    return 'context' as const
  }
  if (pathname.startsWith('/dashboard/voice')) {
    return 'voice' as const
  }
  if (pathname.startsWith('/dashboard/agent')) {
    return 'agent_runtime' as const
  }
  if (pathname.startsWith('/dashboard/models')) {
    return 'models' as const
  }
  if (pathname.startsWith('/dashboard/datasets')) {
    return 'datasets' as const
  }
  if (pathname.startsWith('/dashboard/tools')) {
    return 'tools' as const
  }
  if (pathname.startsWith('/dashboard/doctor')) {
    return 'doctor' as const
  }
  if (pathname.startsWith('/dashboard/storage')) {
    return 'storage' as const
  }
  if (pathname.startsWith('/dashboard/environment')) {
    return 'environment' as const
  }
  if (pathname.startsWith('/dashboard/skills')) {
    return 'skills' as const
  }
  if (pathname.startsWith('/dashboard/specialists')) {
    return 'specialists' as const
  }
  if (pathname.startsWith('/dashboard/integrations')) {
    return 'integrations' as const
  }
  if (pathname.startsWith('/dashboard/mcp')) {
    return 'mcp' as const
  }
  return 'overview' as const
}
