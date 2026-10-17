import { describe, expect, it } from 'vitest'

import {
  composerModelPrefKey,
  formatComposerModelLabel,
  formatContextWindow,
  formatLlamaModelLabel,
  formatPickerContextBadge,
  isComposerModelSelected,
  isLlamaWeightId,
  modelOptionBadge,
  rankComposerModelOptions,
  resolveComposerModelOption,
  scoreComposerModelSearch,
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
    expect(modelOptionBadge({ source: 'cloud', provider: 'openrouter' })).toBe(
      'OpenRouter'
    )
    expect(modelOptionBadge({ source: 'cloud', provider: 'together' })).toBe(
      'Together AI'
    )
  })

  it('prefers provider over generic Custom for custom cloud models', () => {
    expect(modelOptionBadge({ source: 'custom', provider: 'openai' })).toBe(
      'OpenAI'
    )
  })
})

describe('formatComposerModelLabel', () => {
  it('strips via-provider suffixes', () => {
    expect(formatComposerModelLabel('DeepSeek V4 Pro · via Together')).toBe(
      'DeepSeek V4 Pro'
    )
    expect(formatComposerModelLabel('Inkling · via Together')).toBe('Inkling')
    expect(formatComposerModelLabel('Claude Opus 4.6')).toBe('Claude Opus 4.6')
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
        id: 'deepseek-ai/DeepSeek-V4-Pro',
        label: 'DeepSeek V4 Pro · via Together',
        provider: 'together',
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
        supportsReasoningFast: true,
        reasoningEffortOptions: [],
        reasoningEffort: 'medium',
        reasoningFast: false,
        contextWindow: null,
        supportsImageInputs: false,
        supportsPdfInputs: false,
        supportsAudioInputs: false,
        supportsVideoInputs: false
      },
      {
        provider: 'together',
        model: 'deepseek-ai/DeepSeek-V4-Pro',
        label: 'DeepSeek V4 Pro',
        speed: 'Together AI',
        profileId: null,
        source: 'cloud',
        backend: null,
        supportsReasoningEffort: false,
        supportsReasoningFast: true,
        reasoningEffortOptions: [],
        reasoningEffort: 'medium',
        reasoningFast: false,
        contextWindow: null,
        supportsImageInputs: false,
        supportsPdfInputs: false,
        supportsAudioInputs: false,
        supportsVideoInputs: false
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
        supportsReasoningFast: true,
        reasoningEffortOptions: [],
        reasoningEffort: 'medium',
        reasoningFast: false,
        contextWindow: null,
        supportsImageInputs: false,
        supportsPdfInputs: false,
        supportsAudioInputs: false,
        supportsVideoInputs: false
      }
    ])
  })
})

describe('formatPickerContextBadge', () => {
  it('shows 1M only for mega-context models', () => {
    expect(formatPickerContextBadge(1_000_000)).toBe('1M')
    expect(formatPickerContextBadge(1_048_576)).toBe('1M')
    expect(formatPickerContextBadge(1_050_000)).toBe('1M')
    expect(formatPickerContextBadge(262_144)).toBeNull()
    expect(formatPickerContextBadge(200_000)).toBeNull()
    expect(formatPickerContextBadge(null)).toBeNull()
  })
})

describe('formatContextWindow', () => {
  it('formats sub-megabyte windows for usage UI', () => {
    expect(formatContextWindow(262_144)).toBe('262k')
    expect(formatContextWindow(1_050_000)).toBe('1.1M')
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

  it('matches an openai/ prefixed id to the bare catalog row', () => {
    const gpt = {
      provider: 'openai',
      model: 'gpt-6-luna',
      label: 'GPT-6 Luna',
      speed: 'OpenAI',
      profileId: null,
      source: 'cloud' as const,
      supportsReasoningEffort: true,
      reasoningEffortOptions: ['low', 'medium', 'high']
    }
    const resolved = resolveComposerModelOption([gpt], {
      provider: 'openai',
      model: 'openai/gpt-6-luna'
    })
    expect(resolved?.label).toBe('GPT-6 Luna')
    expect(resolved?.supportsReasoningEffort).toBe(true)
    expect(
      isComposerModelSelected(gpt, { provider: 'openai', model: 'openai/gpt-6-luna' }, [gpt])
    ).toBe(true)
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

describe('scoreComposerModelSearch', () => {
  it('ranks DeepSeek above unrelated models for Deep', () => {
    const deepseek = {
      provider: 'deepseek',
      model: 'deepseek-v4-flash',
      label: 'DeepSeek V4 Flash',
      speed: 'DeepSeek'
    }
    const opus = {
      provider: 'anthropic',
      model: 'claude-opus-5',
      label: 'Opus 5',
      speed: 'Anthropic'
    }
    expect(scoreComposerModelSearch(deepseek, 'Deep')).toBeGreaterThan(
      scoreComposerModelSearch(opus, 'Deep')
    )
    expect(scoreComposerModelSearch(opus, 'Deep')).toBe(-1)
  })

  it('matches hyphenated ids when the query uses spaces', () => {
    const gemini = {
      provider: 'google',
      model: 'google/gemini-3.7-flash',
      label: 'Gemini 3.7 Flash',
      speed: 'Gemini'
    }
    const opus = {
      provider: 'anthropic',
      model: 'claude-opus-5',
      label: 'Opus 5',
      speed: 'Anthropic'
    }
    expect(scoreComposerModelSearch(gemini, 'Gemini 3.7')).toBeGreaterThan(0)
    expect(scoreComposerModelSearch(opus, 'Gemini 3.7')).toBe(-1)
    expect(
      rankComposerModelOptions([gemini, opus], 'Gemini 3.7').flatMap(
        section => section.options
      )
    ).toEqual([gemini])
  })
})

describe('formatLlamaModelLabel', () => {
  it('hides the raw repo id when Llama is not in the catalog', () => {
    expect(isLlamaWeightId('ggml-org/gemma-3-270m-it-qat-GGUF:Q4_0')).toBe(true)
    expect(isLlamaWeightId('gpt-6-luna')).toBe(false)
    expect(formatLlamaModelLabel('ggml-org/gemma-3-270m-it-qat-GGUF:Q4_0')).toBe(
      'Gemma 3 270M Q4_0'
    )
    expect(formatLlamaModelLabel('ggml-org/gemma-4-26B-A4B-it-GGUF:Q4_0')).toBe(
      'Gemma 4 26B A4B Q4_0'
    )
  })
})

describe('scoreComposerModelSearch llama provider', () => {
  it('finds local Gemma rows when the query is the Llama badge', () => {
    const gemma = {
      provider: 'local',
      model: 'ggml-org/gemma-3-270m-it-qat-GGUF:Q4_0',
      label: 'Gemma 3 270m It Qat',
      speed: 'Llama',
      source: 'profile' as const,
      backend: 'llama',
      profileId: 'llama_local'
    }
    const gpt = {
      provider: 'openai-chatgpt',
      model: 'gpt-6-luna',
      label: 'GPT-6 Luna',
      speed: 'ChatGPT plan'
    }
    expect(scoreComposerModelSearch(gemma, 'llama')).toBeGreaterThan(0)
    expect(scoreComposerModelSearch(gpt, 'llama')).toBe(-1)
    expect(
      rankComposerModelOptions([gemma, gpt], 'llama').flatMap(
        section => section.options
      )
    ).toEqual([gemma])
  })
})

describe('rankComposerModelOptions', () => {
  it('sections favorites and recent when not searching', () => {
    const options: Parameters<typeof rankComposerModelOptions>[0] = [
      {
        provider: 'anthropic',
        model: 'claude-sonnet-5',
        label: 'Sonnet 5',
        speed: 'Anthropic',
        source: 'cloud'
      },
      {
        provider: 'deepseek',
        model: 'deepseek-v4-flash',
        label: 'DeepSeek V4 Flash',
        speed: 'DeepSeek',
        source: 'cloud'
      }
    ]
    const sections = rankComposerModelOptions(options, '', {
      favorites: [composerModelPrefKey(options[1])],
      recent: [composerModelPrefKey(options[0])]
    })
    expect(sections.map(section => section.title)).toEqual([
      'Favorites',
      'Recent'
    ])
    expect(sections[0].options[0].model).toBe('deepseek-v4-flash')
    expect(sections[1].options[0].model).toBe('claude-sonnet-5')
  })
})
