import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { describe, expect, it } from 'vitest'

import {
  integrationManagementPath,
  integrationsOwnedByIntegrations
} from './integrations-view-ownership'

function integration(key: string, category: string): IntegrationSummary {
  return {
    key,
    category,
    name: key,
    description: '',
    envVar: '',
    configured: false,
    source: 'none',
    maskedPreview: null,
    setupUrl: null,
    free: false,
    fields: [],
    unlocks: []
  }
}

describe('Integrations UI ownership', () => {
  it('keeps independently managed credentials out of Integrations', () => {
    const entries = [
      integration('anthropic', 'AI Models'),
      integration('tamarind', 'MCP'),
      integration('modal', 'Agent Runtime'),
      integration('slack', 'Communication'),
      integration('tavily', 'MCP')
    ]

    expect(
      integrationsOwnedByIntegrations(entries).map(item => item.key)
    ).toEqual(['slack'])
  })

  it('routes hidden entries to their owning settings page', () => {
    expect(integrationManagementPath(integration('openai', 'AI Models'))).toBe(
      '/dashboard/models'
    )
    expect(integrationManagementPath(integration('linear', 'MCP'))).toBe(
      '/dashboard/mcp'
    )
    expect(integrationManagementPath(integration('tavily', 'MCP'))).toBe(
      '/dashboard/mcp'
    )
    expect(
      integrationManagementPath(integration('modal', 'Agent Runtime'))
    ).toBe('/dashboard/agent/sandbox/modal')
    expect(
      integrationManagementPath(integration('slack', 'Communication'))
    ).toBeNull()
  })
})
