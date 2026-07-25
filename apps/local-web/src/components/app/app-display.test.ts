import { describe, expect, it } from 'vitest'

import { integrationRouteSegment } from '@/components/agents/dashboard-main-view-helpers'

import { resolveSelectedIntegrationKey } from './app-display'

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

  it('returns null for unknown routes', () => {
    expect(
      resolveSelectedIntegrationKey('not-a-provider', 'not-a-provider', [
        ...integrations
      ])
    ).toBeNull()
  })
})
