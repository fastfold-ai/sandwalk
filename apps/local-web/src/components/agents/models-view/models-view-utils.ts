import type { AgentModel, IntegrationSummary } from '@sandwalk/agent-ui-core'

import {
  catalogModelPrefKey,
  scoreModelCatalogSearch
} from '@/lib/composer-models'

export type ModelSourceFilter = 'all' | 'cloud' | 'local' | 'favorites'

export function filterModelCatalog(
  models: AgentModel[],
  options: {
    query: string
    sourceFilter: ModelSourceFilter
    providerFilter: string
    favoriteKeys: string[]
  }
): AgentModel[] {
  const needle = options.query.trim()
  const favoriteSet = new Set(options.favoriteKeys)
  const filtered = models.filter(model => {
    const isLocal = model.source === 'profile'
    const isCloud = model.source === 'cloud' || model.source === 'custom'
    if (options.sourceFilter === 'favorites') {
      if (!favoriteSet.has(catalogModelPrefKey(model))) return false
    } else {
      if (options.sourceFilter === 'local' && !isLocal) return false
      if (options.sourceFilter === 'cloud' && !isCloud) return false
    }
    const providerKey = isLocal ? 'local' : model.provider
    if (
      options.providerFilter !== 'all' &&
      providerKey !== options.providerFilter
    ) {
      return false
    }
    if (!needle) return true
    return scoreModelCatalogSearch(model, needle) >= 0
  })
  if (!needle) return filtered
  return [...filtered].sort((a, b) => {
    const scoreDiff =
      scoreModelCatalogSearch(b, needle) - scoreModelCatalogSearch(a, needle)
    if (scoreDiff !== 0) return scoreDiff
    return a.label.localeCompare(b.label)
  })
}

export const CLOUD_PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google Gemini' },
  { value: 'xai', label: 'xAI (Grok)' },
  { value: 'moonshot', label: 'Kimi' },
  { value: 'nvidia', label: 'NVIDIA' },
  { value: 'opencode', label: 'OpenCode Zen' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'minimax', label: 'MiniMax' },
  { value: 'mistral', label: 'Mistral' },
  { value: 'qwen', label: 'Qwen Cloud' },
  { value: 'together', label: 'Together AI' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'cerebras', label: 'Cerebras' },
  { value: 'groq', label: 'Groq' },
  { value: 'fireworks', label: 'Fireworks AI' },
  { value: 'bedrock', label: 'Amazon Bedrock' }
] as const

export const MODEL_LIST_PREVIEW_LIMIT = 10

/** Mirrors CLI `OPENAI_PROFILE_DEFAULTS` / setup backend menu (local backends only). */
export const PROFILE_BACKENDS = [
  {
    value: 'ollama',
    label: 'Ollama',
    hint: '/api/tags',
    baseUrl: 'http://127.0.0.1:11434/v1',
    defaultLabel: 'Ollama',
    icon: '/local-llm/ollama.png'
  },
  {
    value: 'unsloth',
    label: 'Unsloth',
    hint: '/v1/models · auth',
    baseUrl: 'http://127.0.0.1:8888/v1',
    defaultLabel: 'Unsloth',
    icon: '/local-llm/unsloth.png'
  },
  {
    value: 'omlx',
    label: 'oMLX',
    hint: '/v1/models · auth',
    baseUrl: 'http://127.0.0.1:8000/v1',
    defaultLabel: 'oMLX',
    icon: '/local-llm/omlx.png'
  },
  {
    value: 'ds4',
    label: 'DS4',
    hint: '/v1/models',
    baseUrl: 'http://127.0.0.1:8000/v1',
    defaultLabel: 'DS4',
    icon: 'cpu'
  },
  {
    value: 'llama_cpp',
    label: 'llama.cpp',
    hint: '/v1/models',
    baseUrl: 'http://127.0.0.1:8080/v1',
    defaultLabel: 'llama.cpp',
    icon: '/local-llm/llama-cpp.png'
  },
  {
    value: 'lm_studio',
    label: 'LM Studio',
    hint: '/v1/models',
    baseUrl: 'http://127.0.0.1:1234/v1',
    defaultLabel: 'LM Studio',
    icon: '/local-llm/lm-studio.png'
  },
  {
    value: 'other',
    label: 'Other OpenAI-compatible',
    hint: '/v1/models then /api/tags',
    baseUrl: 'http://127.0.0.1:11434/v1',
    defaultLabel: 'Custom Compatible Endpoint',
    icon: 'cpu'
  }
] as const

export type ProfileBackendValue = (typeof PROFILE_BACKENDS)[number]['value']

export type ProfileFormState = {
  label: string
  backend: ProfileBackendValue
  baseUrl: string
  apiKey: string
}

export function profileBackend(
  value: string
): (typeof PROFILE_BACKENDS)[number] | undefined {
  return PROFILE_BACKENDS.find(item => item.value === value)
}

export function isKnownDefaultBaseUrl(url: string): boolean {
  const normalized = url
    .trim()
    .replace(/\/+$/, '')
    .replace('://localhost', '://127.0.0.1')
  return PROFILE_BACKENDS.some(item => {
    const candidate = item.baseUrl
      .replace(/\/+$/, '')
      .replace('://localhost', '://127.0.0.1')
    return candidate === normalized
  })
}

export function isKnownDefaultLabel(label: string): boolean {
  const needle = label.trim().toLowerCase()
  return PROFILE_BACKENDS.some(
    item => item.defaultLabel.toLowerCase() === needle
  )
}

/** Mirror CLI `format_discovered_model_label` for preview rows. */
export function formatDiscoveredModelLabel(modelId: string): string {
  const raw = modelId.trim()
  if (!raw) return raw
  const acronyms = new Set(['gpt', 'glm', 'aws', 'api', 'llm', 'ml'])
  return raw
    .replace(/_/g, '-')
    .split('-')
    .filter(Boolean)
    .map(part => {
      const lower = part.toLowerCase()
      if (acronyms.has(lower)) return lower.toUpperCase()
      return part.slice(0, 1).toUpperCase() + part.slice(1)
    })
    .join(' ')
}

export const LLM_API_KEY_ORDER = [
  'openai',
  'anthropic',
  'google',
  'xai',
  'moonshot',
  'nvidia',
  'opencode',
  'deepseek',
  'minimax',
  'mistral',
  'qwen',
  'together',
  'openrouter',
  'cerebras',
  'groq',
  'fireworks',
  'bedrock'
] as const

export const LLM_API_KEY_COPY: Record<
  (typeof LLM_API_KEY_ORDER)[number],
  {
    cardTitle: string
    title: string
    /** Short blurb above the key field. */
    description: string
    /** Host shown in “No key yet? Create one at …” */
    hostLabel: string
    placeholderUnset: string
  }
> = {
  openai: {
    cardTitle: 'OpenAI',
    title: 'OpenAI API Key',
    description: 'Use your OpenAI key for GPT models at cost.',
    hostLabel: 'platform.openai.com',
    placeholderUnset: 'Enter your OpenAI API Key'
  },
  anthropic: {
    cardTitle: 'Claude (Anthropic)',
    title: 'Anthropic API Key',
    description:
      'Use your Anthropic key for Claude. When enabled, this key is used for all models beginning with “claude-”.',
    hostLabel: 'console.anthropic.com',
    placeholderUnset: 'Enter your Anthropic API Key'
  },
  google: {
    cardTitle: 'Gemini (Google)',
    title: 'Google Gemini API Key',
    description: 'Use your Google AI Studio key for Gemini models at cost.',
    hostLabel: 'aistudio.google.com',
    placeholderUnset: 'Enter your Google AI Studio API Key'
  },
  xai: {
    cardTitle: 'xAI (Grok)',
    title: 'xAI API Key',
    description: 'Use your xAI key for Grok models at cost.',
    hostLabel: 'console.x.ai',
    placeholderUnset: 'Enter your xAI API Key'
  },
  moonshot: {
    cardTitle: 'Kimi (Moonshot AI)',
    title: 'Kimi API Key',
    description: 'Use your Kimi key for Moonshot models at cost.',
    hostLabel: 'platform.moonshot.ai',
    placeholderUnset: 'Enter your Kimi API Key'
  },
  nvidia: {
    cardTitle: 'NVIDIA',
    title: 'NVIDIA API Key',
    description: 'Use your NVIDIA key for NIM and model inference endpoints.',
    hostLabel: 'build.nvidia.com',
    placeholderUnset: 'Enter your NVIDIA API Key'
  },
  opencode: {
    cardTitle: 'OpenCode Zen',
    title: 'OpenCode Zen API Key',
    description:
      'Pay-as-you-go access to curated coding models (GPT, Claude, Gemini, Kimi, DeepSeek, and more).',
    hostLabel: 'opencode.ai',
    placeholderUnset: 'Enter your OpenCode Zen API Key'
  },
  deepseek: {
    cardTitle: 'DeepSeek',
    title: 'DeepSeek API Key',
    description: 'Use your DeepSeek key for DeepSeek models at cost.',
    hostLabel: 'platform.deepseek.com',
    placeholderUnset: 'Enter your DeepSeek API Key'
  },
  minimax: {
    cardTitle: 'MiniMax',
    title: 'MiniMax API Key',
    description: 'Use your MiniMax key for MiniMax models at cost.',
    hostLabel: 'platform.minimax.io',
    placeholderUnset: 'Enter your MiniMax API Key'
  },
  mistral: {
    cardTitle: 'Mistral',
    title: 'Mistral API Key',
    description: 'Use your Mistral key for Mistral models at cost.',
    hostLabel: 'console.mistral.ai',
    placeholderUnset: 'Enter your Mistral API Key'
  },
  qwen: {
    cardTitle: 'Qwen Cloud',
    title: 'Qwen Cloud API Key',
    description:
      'Paste your Qwen Cloud API key, then the OpenAI-compatible endpoint from your API Keys page (or leave the endpoint blank to auto-detect).',
    hostLabel: 'home.qwencloud.com',
    placeholderUnset: 'Enter your Qwen Cloud API Key'
  },
  together: {
    cardTitle: 'Together AI',
    title: 'Together AI API Key',
    description:
      "Uses Together AI's OpenAI-compatible API — the endpoint is prefilled, just add your key.",
    hostLabel: 'together.xyz',
    placeholderUnset: 'Enter your Together AI API Key'
  },
  openrouter: {
    cardTitle: 'OpenRouter',
    title: 'OpenRouter API Key',
    description:
      'Route many providers through OpenRouter. Sandwalk attributes usage to sandwalk.sh.',
    hostLabel: 'openrouter.ai',
    placeholderUnset: 'Enter your OpenRouter API Key'
  },
  cerebras: {
    cardTitle: 'Cerebras',
    title: 'Cerebras API Key',
    description: 'Wafer-scale inference for GPT-OSS and Gemma on Cerebras Cloud.',
    hostLabel: 'cloud.cerebras.ai',
    placeholderUnset: 'Enter your Cerebras API Key'
  },
  groq: {
    cardTitle: 'Groq',
    title: 'Groq API Key',
    description: 'Groq LPU inference for open models (Llama, Qwen, GPT-OSS).',
    hostLabel: 'console.groq.com',
    placeholderUnset: 'Enter your Groq API Key'
  },
  fireworks: {
    cardTitle: 'Fireworks AI',
    title: 'Fireworks AI API Key',
    description: 'Hosted open and proprietary models via Fireworks inference.',
    hostLabel: 'fireworks.ai',
    placeholderUnset: 'Enter your Fireworks API Key'
  },
  bedrock: {
    cardTitle: 'Amazon Bedrock',
    title: 'Amazon Bedrock (IAM)',
    description:
      'Uses your AWS CLI / IAM identity by default. Set a region and optional profile, then Test. Access keys are optional.',
    hostLabel: 'docs.aws.amazon.com',
    placeholderUnset: 'Optional access key ID'
  }
}

export function primaryEnvVar(integration: IntegrationSummary) {
  return (
    integration.fields.find(field => field.isSecret)?.envVar ||
    integration.envVar
  )
}

export function primaryMaskedPreview(integration: IntegrationSummary) {
  return (
    integration.fields.find(field => field.isSecret)?.maskedPreview ||
    integration.maskedPreview
  )
}

export function qwenEndpointValue(integration: IntegrationSummary) {
  const field = integration.fields.find(item => item.envVar === 'QWEN_BASE_URL')
  return (field?.maskedPreview || '').trim()
}

export function bedrockFieldValue(
  integration: IntegrationSummary,
  envVar: string
) {
  const field = integration.fields.find(item => item.envVar === envVar)
  return (field?.maskedPreview || '').trim()
}

export function applyBackendDefaults(
  backendValue: ProfileBackendValue,
  previous: ProfileFormState
): ProfileFormState {
  const next = profileBackend(backendValue) || PROFILE_BACKENDS[0]
  const suggestUrl =
    !previous.baseUrl.trim() || isKnownDefaultBaseUrl(previous.baseUrl)
  const suggestLabel =
    !previous.label.trim() || isKnownDefaultLabel(previous.label)
  return {
    ...previous,
    backend: next.value,
    baseUrl: suggestUrl ? next.baseUrl : previous.baseUrl,
    label: suggestLabel ? next.defaultLabel : previous.label
  }
}
