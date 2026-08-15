import { describe, expect, it } from 'vitest'

import type { AgentModel } from '@sandwalk/agent-ui-core'

import { catalogModelPrefKey } from '@/lib/composer-models'

import { filterModelCatalog } from './models-view-utils'

function model(overrides: Partial<AgentModel> & Pick<AgentModel, 'id'>): AgentModel {
  return {
    label: overrides.id,
    description: null,
    provider: 'anthropic',
    source: 'cloud',
    profileId: null,
    enabled: true,
    health: null,
    ...overrides
  }
}

describe('filterModelCatalog', () => {
  const cloud = model({ id: 'claude-sonnet', provider: 'anthropic' })
  const openai = model({ id: 'gpt-5', provider: 'openai' })
  const local = model({
    id: 'qwen3',
    provider: 'local',
    source: 'profile',
    profileId: 'omlx'
  })

  it('keeps only favorited models on the favorites filter', () => {
    const filtered = filterModelCatalog([cloud, openai, local], {
      query: '',
      sourceFilter: 'favorites',
      providerFilter: 'all',
      favoriteKeys: [catalogModelPrefKey(cloud)]
    })
    expect(filtered.map(item => item.id)).toEqual(['claude-sonnet'])
  })

  it('still applies provider chips on top of favorites', () => {
    const filtered = filterModelCatalog([cloud, openai], {
      query: '',
      sourceFilter: 'favorites',
      providerFilter: 'openai',
      favoriteKeys: [
        catalogModelPrefKey(cloud),
        catalogModelPrefKey(openai)
      ]
    })
    expect(filtered.map(item => item.id)).toEqual(['gpt-5'])
  })

  it('matches local profile keys the same way as the composer', () => {
    const filtered = filterModelCatalog([cloud, local], {
      query: '',
      sourceFilter: 'favorites',
      providerFilter: 'all',
      favoriteKeys: ['local:omlx:qwen3']
    })
    expect(filtered.map(item => item.id)).toEqual(['qwen3'])
  })
})
