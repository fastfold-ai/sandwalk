import { describe, expect, it } from 'vitest'

import {
  decodeRouteParam,
  matchAppRoutes,
  resolveDashboardSection
} from './app-routing-helpers'

describe('matchAppRoutes', () => {
  it('matches dashboard, session, and legacy paths', () => {
    const routes = matchAppRoutes(
      '/dashboard/skills/catalog/org/skill%20name'
    )
    expect(routes.catalogDetailRoute?.params['*']).toBe('org/skill%20name')
    expect(matchAppRoutes('/agents/chat-1').sessionRoute?.params.sessionId).toBe(
      'chat-1'
    )
    expect(
      matchAppRoutes('/terminals/term-1').terminalRoute?.params.terminalId
    ).toBe('term-1')
    expect(
      matchAppRoutes('/dashboard/specialists/new').specialistNewRoute
    ).toBeTruthy()
    expect(
      matchAppRoutes('/dashboard/mcp/server/local').mcpServerDetailRoute?.params
        .serverId
    ).toBe('local')
    expect(matchAppRoutes('/dashboard').sessionRoute).toBeNull()
  })
})

describe('decodeRouteParam', () => {
  it('decodes a param and keeps a broken escape as-is', () => {
    expect(decodeRouteParam(undefined)).toBeNull()
    expect(decodeRouteParam('a%20b')).toBe('a b')
    expect(decodeRouteParam('%')).toBe('%')
  })
})

describe('resolveDashboardSection', () => {
  it('maps each settings path and falls back to overview', () => {
    expect(resolveDashboardSection('/dashboard/settings/theme')).toBe('general')
    expect(resolveDashboardSection('/dashboard/appearance')).toBe('appearance')
    expect(resolveDashboardSection('/dashboard/agent/sandbox/modal')).toBe(
      'agent_sandbox'
    )
    expect(resolveDashboardSection('/dashboard/agent/security')).toBe(
      'agent_security'
    )
    expect(resolveDashboardSection('/dashboard/agent')).toBe('agent_runtime')
    expect(resolveDashboardSection('/dashboard/context')).toBe('context')
    expect(resolveDashboardSection('/dashboard/voice')).toBe('voice')
    expect(resolveDashboardSection('/dashboard/models')).toBe('models')
    expect(resolveDashboardSection('/dashboard/datasets')).toBe('datasets')
    expect(resolveDashboardSection('/dashboard/tools')).toBe('tools')
    expect(resolveDashboardSection('/dashboard/doctor')).toBe('doctor')
    expect(resolveDashboardSection('/dashboard/logs')).toBe('logs')
    expect(resolveDashboardSection('/dashboard/bench')).toBe('bench')
    expect(resolveDashboardSection('/dashboard/storage')).toBe('storage')
    expect(resolveDashboardSection('/dashboard/environment')).toBe('environment')
    expect(resolveDashboardSection('/dashboard/skills')).toBe('skills')
    expect(resolveDashboardSection('/dashboard/specialists')).toBe('specialists')
    expect(resolveDashboardSection('/dashboard/integrations')).toBe(
      'integrations'
    )
    expect(resolveDashboardSection('/dashboard/mcp')).toBe('mcp')
    expect(resolveDashboardSection('/dashboard')).toBe('overview')
  })
})
