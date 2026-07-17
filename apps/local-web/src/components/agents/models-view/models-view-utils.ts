import type { IntegrationSummary } from '@sandwalk/agent-ui-core'

export const CLOUD_PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google Gemini' },
  { value: 'xai', label: 'xAI (Grok)' },
  { value: 'moonshot', label: 'Kimi' },
  { value: 'nvidia', label: 'NVIDIA' },
  { value: 'opencode', label: 'OpenCode Zen' }
] as const

export const MODEL_LIST_PREVIEW_LIMIT = 10

/** Mirrors CLI `OPENAI_PROFILE_DEFAULTS` / setup backend menu (local backends only). */
export const PROFILE_BACKENDS = [
  {
    value: 'ollama',
    label: 'Ollama',
    hint: '/api/tags',
    baseUrl: 'http://127.0.0.1:11434/v1',
    defaultLabel: 'Ollama Local',
    icon: '/local-llm/ollama.png'
  },
  {
    value: 'unsloth',
    label: 'Unsloth',
    hint: '/v1/models · auth',
    baseUrl: 'http://127.0.0.1:8888/v1',
    defaultLabel: 'Unsloth Local',
    icon: '/local-llm/unsloth.png'
  },
  {
    value: 'omlx',
    label: 'oMLX',
    hint: '/v1/models · auth',
    baseUrl: 'http://127.0.0.1:8000/v1',
    defaultLabel: 'oMLX Local',
    icon: '/local-llm/omlx.png'
  },
  {
    value: 'ds4',
    label: 'DS4',
    hint: '/v1/models',
    baseUrl: 'http://127.0.0.1:8000/v1',
    defaultLabel: 'DS4 Local',
    icon: 'cpu'
  },
  {
    value: 'llama_cpp',
    label: 'llama.cpp',
    hint: '/v1/models',
    baseUrl: 'http://127.0.0.1:8080/v1',
    defaultLabel: 'llama.cpp Local',
    icon: '/local-llm/llama-cpp.png'
  },
  {
    value: 'lm_studio',
    label: 'LM Studio',
    hint: '/v1/models',
    baseUrl: 'http://127.0.0.1:1234/v1',
    defaultLabel: 'LM Studio Local',
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
  'opencode'
] as const

export const LLM_API_KEY_COPY: Record<
  (typeof LLM_API_KEY_ORDER)[number],
  {
    title: string
    beforeLink: string
    linkLabel: string
    afterLink: string
    placeholderUnset: string
  }
> = {
  openai: {
    title: 'OpenAI API Key',
    beforeLink: 'You can put in ',
    linkLabel: 'your OpenAI key',
    afterLink: ' to use OpenAI models at cost.',
    placeholderUnset: 'Enter your OpenAI API Key'
  },
  anthropic: {
    title: 'Anthropic API Key',
    beforeLink: 'You can put in ',
    linkLabel: 'your Anthropic key',
    afterLink:
      ' to use Claude at cost. When enabled, this key will be used for all models beginning with "claude-".',
    placeholderUnset: 'Enter your Anthropic API Key'
  },
  google: {
    title: 'Google Gemini API Key',
    beforeLink: 'You can put in ',
    linkLabel: 'your Google AI Studio key',
    afterLink: ' to use Gemini models at cost.',
    placeholderUnset: 'Enter your Google AI Studio API Key'
  },
  xai: {
    title: 'xAI API Key',
    beforeLink: 'You can put in ',
    linkLabel: 'your xAI key',
    afterLink: ' to use Grok models at cost.',
    placeholderUnset: 'Enter your xAI API Key'
  },
  moonshot: {
    title: 'Kimi API Key',
    beforeLink: 'You can put in ',
    linkLabel: 'your Kimi key',
    afterLink: ' to use Kimi models at cost.',
    placeholderUnset: 'Enter your Kimi API Key'
  },
  nvidia: {
    title: 'NVIDIA API Key',
    beforeLink: 'You can put in ',
    linkLabel: 'your NVIDIA API key',
    afterLink: ' to use NVIDIA NIM and model inference endpoints.',
    placeholderUnset: 'Enter your NVIDIA API Key'
  },
  opencode: {
    title: 'OpenCode Zen API Key',
    beforeLink: 'Sign in to OpenCode Zen and put in ',
    linkLabel: 'your Zen API key',
    afterLink:
      ' for pay-as-you-go access to curated coding models (GPT, Claude, Gemini, Kimi, DeepSeek, and more).',
    placeholderUnset: 'Enter your OpenCode Zen API Key'
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
