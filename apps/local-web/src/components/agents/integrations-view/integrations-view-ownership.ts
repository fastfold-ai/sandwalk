import type { IntegrationSummary } from '@sandwalk/agent-ui-core'

export function integrationManagementPath(
  integration: IntegrationSummary
): string | null {
  if (integration.category === 'AI Models') return '/dashboard/models'
  if (integration.category === 'MCP') return '/dashboard/mcp'
  if (integration.key === 'modal') return '/dashboard/agent/sandbox/modal'
  return null
}

export function integrationsOwnedByIntegrations(
  integrations: IntegrationSummary[]
) {
  return integrations.filter(item => integrationManagementPath(item) === null)
}
