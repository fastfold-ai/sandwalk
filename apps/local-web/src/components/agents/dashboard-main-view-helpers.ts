import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession, IntegrationSummary } from '@sandwalk/agent-ui-core'
import type { NavigateFunction } from 'react-router-dom'

export function integrationRouteSegment(
  integrations: IntegrationSummary[],
  key: string | null
) {
  if (!key) return null
  const target = integrations.find(item => item.key === key)
  const segment = (target?.name || key)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return segment || key
}

export function navigateToIntegration(
  navigate: NavigateFunction,
  integrations: IntegrationSummary[],
  key: string | null
) {
  if (!key) {
    navigate('/dashboard/integrations')
    return
  }
  const segment = integrationRouteSegment(integrations, key)
  navigate(`/dashboard/integrations/${encodeURIComponent(segment || key)}`)
}

export async function openVercelIntegrationTerminal(input: {
  client: LocalAgentClient
  sessions: AgentSession[]
  activeProjectId: string | null
  loadSessions: () => Promise<void>
}) {
  const existing = input.sessions.find(item =>
    String(item.workspacePath || '')
      .trim()
      .endsWith('/.sandwalk/vercel-integration')
  )
  if (existing) return existing.id
  const created = await input.client.createSession({
    title: 'Vercel integration setup',
    workspacePath: '~/.sandwalk/vercel-integration',
    projectId: input.activeProjectId || undefined
  })
  await input.loadSessions()
  return created.id
}
