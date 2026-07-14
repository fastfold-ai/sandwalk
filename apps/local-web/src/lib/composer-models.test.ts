import { describe, expect, it } from 'vitest'

import {
  isComposerModelSelected,
  modelOptionBadge,
  resolveComposerModelOption,
  toComposerModelOptions
} from './composer-models'

describe('modelOptionBadge', () => {
  it('labels local profile models by backend', () => {
    expect(
      modelOptionBadge({
        source: 'profile',
        provider: 'local',
        backend: 'omlx'
      })
    ).toBe('oMLX')
    expect(
      modelOptionBadge({
        source: 'profile',
        provider: 'local',
        backend: 'ollama'
      })
    ).toBe('Ollama')
    expect(
      modelOptionBadge({
        source: 'profile',
        provider: 'local',
        backend: 'unsloth'
      })
    ).toBe('Unsloth')
    expect(
      modelOptionBadge({ source: 'profile', provider: 'local', backend: null })
    ).toBe('Local')
    expect(
      modelOptionBadge({
        source: 'profile',
        provider: 'local',
        backend: null,
        description: 'oMLX Local (omlx)'
      })
    ).toBe('oMLX')
  })

  it('labels cloud models with their provider', () => {
    expect(modelOptionBadge({ source: 'cloud', provider: 'anthropic' })).toBe(
      'Anthropic'
    )
    expect(modelOptionBadge({ source: 'cloud', provider: 'openai' })).toBe(
      'OpenAI'
    )
    expect(modelOptionBadge({ source: 'cloud', provider: 'opencode' })).toBe(
      'OpenCode Zen'
    )
    expect(modelOptionBadge({ source: 'cloud', provider: 'google' })).toBe(
      'Gemini'
    )
  })

  it('prefers provider over generic Custom for custom cloud models', () => {
    expect(modelOptionBadge({ source: 'custom', provider: 'openai' })).toBe(
      'OpenAI'
    )
  })
})

describe('toComposerModelOptions', () => {
  it('maps enabled models with provider badges', () => {
    const options = toComposerModelOptions([
      {
        id: 'claude-sonnet',
        label: 'Sonnet',
        provider: 'anthropic',
        source: 'cloud',
        profileId: null,
        backend: null,
        enabled: true
      },
      {
        id: 'qwen-local',
        label: 'Qwen Local',
        provider: 'local',
        source: 'profile',
        profileId: 'omlx_local',
        backend: 'omlx',
        enabled: true
      },
      {
        id: 'hidden',
        label: 'Hidden',
        provider: 'openai',
        source: 'cloud',
        profileId: null,
        enabled: false
      }
    ])
    expect(options).toEqual([
      {
        provider: 'anthropic',
        model: 'claude-sonnet',
        label: 'Sonnet',
        speed: 'Anthropic',
        profileId: null,
        source: 'cloud',
        backend: null,
        supportsReasoningEffort: false,
        reasoningEffortOptions: [],
        reasoningEffort: 'medium',
        reasoningFast: false
      },
      {
        provider: 'local',
        model: 'qwen-local',
        label: 'Qwen Local',
        speed: 'oMLX',
        profileId: 'omlx_local',
        source: 'profile',
        backend: 'omlx',
        supportsReasoningEffort: false,
        reasoningEffortOptions: [],
        reasoningEffort: 'medium',
        reasoningFast: false
      }
    ])
  })
})

describe('resolveComposerModelOption', () => {
  const options = [
    {
      provider: 'opencode',
      model: 'deepseek-v4-flash',
      label: 'Deepseek V4 Flash',
      speed: 'OpenCode Zen',
      profileId: null,
      source: 'cloud' as const
    },
    {
      provider: 'local',
      model: 'deepseek-v4-flash',
      label: 'Deepseek V4 Flash',
      speed: 'DS4',
      profileId: 'ds4_local',
      source: 'profile' as const,
      backend: 'ds4'
    }
  ]

  it('prefers catalog provider when runtime is OpenCode', () => {
    const runtime = {
      provider: 'opencode',
      model: 'deepseek-v4-flash',
      openaiProfileId: 'ds4_local'
    }
    expect(resolveComposerModelOption(options, runtime)?.speed).toBe(
      'OpenCode Zen'
    )
    expect(isComposerModelSelected(options[0], runtime, options)).toBe(true)
    expect(isComposerModelSelected(options[1], runtime, options)).toBe(false)
  })

  it('prefers active local profile when runtime is openai', () => {
    const runtime = {
      provider: 'openai',
      model: 'deepseek-v4-flash',
      openaiProfileId: 'ds4_local'
    }
    expect(resolveComposerModelOption(options, runtime)?.speed).toBe('DS4')
    expect(isComposerModelSelected(options[1], runtime, options)).toBe(true)
    expect(isComposerModelSelected(options[0], runtime, options)).toBe(false)
  })
})
