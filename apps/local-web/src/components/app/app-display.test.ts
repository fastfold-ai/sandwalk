import { describe, expect, it } from 'vitest'

import { integrationRouteSegment } from '@/components/agents/dashboard-main-view-helpers'

import {
  computeShowSessionTabs,
  resolveActiveTitle,
  resolveSelectedIntegrationKey
} from './app-display'

const integrations = [
  {
    key: 'moonshot',
    name: 'Kimi',
    category: 'AI Models',
    description: 'Kimi',
    configured: false,
    fields: [],
    envVar: 'MOONSHOT_API_KEY'
  },
  {
    key: 'google',
    name: 'Google Gemini',
    category: 'AI Models',
    description: 'Gemini',
    configured: false,
    fields: [],
    envVar: 'GEMINI_API_KEY'
  }
] as const

describe('resolveSelectedIntegrationKey', () => {
  it('matches Kimi via name slug kimi', () => {
    const segment = integrationRouteSegment([...integrations], 'moonshot')
    expect(segment).toBe('kimi')
    expect(
      resolveSelectedIntegrationKey(segment, segment, [...integrations])
    ).toBe('moonshot')
  })

  it('matches by provider key slug', () => {
    expect(
      resolveSelectedIntegrationKey('moonshot', 'moonshot', [...integrations])
    ).toBe('moonshot')
  })

  it('matches Google Gemini name slug', () => {
    const segment = integrationRouteSegment([...integrations], 'google')
    expect(segment).toBe('google-gemini')
    expect(
      resolveSelectedIntegrationKey(segment, segment, [...integrations])
    ).toBe('google')
  })

  it('names every dashboard section and hides tabs on home', () => {
    const flags = {
      isDashboardOverview: false,
      isDashboardStatus: false,
      isDashboardGeneral: false,
      isDashboardAppearance: false,
      isDashboardAgentRuntime: false,
      isDashboardAgentSecurity: false,
      isDashboardAgentPrompts: false,
      isDashboardVoice: false,
      isDashboardModels: false,
      isDashboardData: false,
      isDashboardTools: false,
      isDashboardDoctor: false,
      isDashboardLogs: false,
      isDashboardBench: false,
      isDashboardStorage: false,
      isDashboardEnvironment: false,
      isSkills: false,
      isDashboardSpecialists: false,
      isIntegrations: false,
      isDashboardMcp: false,
      isHome: false,
      isLibrary: false,
      isSites: false,
      isProjectHome: false,
      sessionTitle: 'Chat'
    }
    expect(resolveActiveTitle({ ...flags, isLibrary: true })).toBe('Library')
    expect(resolveActiveTitle({ ...flags, isSites: true })).toBe('Sites')
    expect(resolveActiveTitle({ ...flags, isDashboardOverview: true })).toBe(
      'Overview'
    )
    expect(resolveActiveTitle({ ...flags, isDashboardStatus: true })).toBe(
      'Status'
    )
    expect(resolveActiveTitle({ ...flags, isDashboardModels: true })).toBe(
      'Models'
    )
    expect(resolveActiveTitle({ ...flags, isDashboardBench: true })).toBe(
      'Benchmarking'
    )
    expect(resolveActiveTitle({ ...flags, isHome: true })).toBe('Home')
    expect(resolveActiveTitle(flags)).toBe('Chat')
    expect(
      computeShowSessionTabs({
        isDashboard: false,
        isHome: true,
        isLibrary: false,
        isSites: false,
        isProjectHome: false,
        isSkills: false,
        isIntegrations: false,
        sessionId: 'chat-1',
        openTabsLength: 1
      })
    ).toBe(false)
    expect(
      computeShowSessionTabs({
        isDashboard: false,
        isHome: false,
        isLibrary: false,
        isSites: false,
        isProjectHome: false,
        isSkills: false,
        isIntegrations: false,
        sessionId: 'chat-1',
        openTabsLength: 1
      })
    ).toBe(true)
  })

  it('returns null for unknown routes', () => {
    expect(
      resolveSelectedIntegrationKey('not-a-provider', 'not-a-provider', [
        ...integrations
      ])
    ).toBeNull()
  })
})
