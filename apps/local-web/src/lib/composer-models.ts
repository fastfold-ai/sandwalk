import { resolveMultimodalCapabilityFlags } from '@/lib/multimodal-attach'

export type ComposerModelOption = {
  provider: string
  model: string
  label: string
  speed: string
  profileId?: string | null
  source?: 'cloud' | 'profile' | 'custom'
  backend?: string | null
  supportsReasoningEffort?: boolean
  reasoningEffortOptions?: string[]
  reasoningEffort?: string | null
  reasoningFast?: boolean
  supportsImageInputs?: boolean
  supportsPdfInputs?: boolean
  supportsAudioInputs?: boolean
  supportsVideoInputs?: boolean
  /** Effective context window when known (local max_model_len, etc.). */
  contextWindow?: number | null
}

/** Compact context-window label, e.g. 200_000 → "200k", 1_048_576 → "1M". */
export function formatContextWindow(
  window: number | null | undefined
): string | null {
  if (typeof window !== 'number' || window <= 0) return null
  if (window >= 1_000_000) {
    const millions = window / 1_000_000
    return `${millions >= 10 || Number.isInteger(millions) ? Math.round(millions) : millions.toFixed(1)}M`
  }
  if (window >= 1_000) return `${Math.round(window / 1_000)}k`
  return String(window)
}

/** Model-picker badge: only mega-context models (Cursor-style inline "1M"). */
export function formatPickerContextBadge(
  window: number | null | undefined
): string | null {
  if (typeof window !== 'number' || window < 1_000_000) return null
  return '1M'
}

const CLOUD_PROVIDER_LABELS: Record<string, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Gemini',
  xai: 'Grok',
  moonshot: 'Kimi',
  nvidia: 'NVIDIA',
  opencode: 'OpenCode Zen',
  deepseek: 'DeepSeek',
  minimax: 'MiniMax',
  mistral: 'Mistral',
  qwen: 'Qwen Cloud',
  together: 'Together AI',
  openrouter: 'OpenRouter'
}

/** Drop redundant “· via Provider” suffixes — provider shows under the name. */
export function formatComposerModelLabel(label: string): string {
  return String(label || '')
    .replace(/\s*·\s*via\s+.+$/i, '')
    .trim()
}

const LOCAL_BACKEND_LABELS: Record<string, string> = {
  ollama: 'Ollama',
  unsloth: 'Unsloth',
  omlx: 'oMLX',
  ds4: 'DS4',
  llama_cpp: 'llama.cpp',
  lm_studio: 'LM Studio',
  other: 'Local'
}

/** Provider / local-backend label shown under the model name in the picker. */
export function modelOptionBadge(model: {
  source: string
  provider: string
  backend?: string | null
  description?: string | null
}): string {
  if (model.source === 'profile' || model.provider === 'local') {
    let backend = String(model.backend || '')
      .trim()
      .toLowerCase()
    if (!backend && model.description) {
      const match = String(model.description).match(/\(([^)]+)\)\s*$/)
      if (match?.[1]) backend = match[1].trim().toLowerCase()
    }
    if (backend in LOCAL_BACKEND_LABELS) {
      return LOCAL_BACKEND_LABELS[backend]
    }
    if (backend) {
      return backend
    }
    return 'Local'
  }
  const provider = String(model.provider || '')
    .trim()
    .toLowerCase()
  if (provider in CLOUD_PROVIDER_LABELS) {
    return CLOUD_PROVIDER_LABELS[provider]
  }
  if (model.source === 'custom') {
    return provider ? provider : 'Custom'
  }
  return provider || 'Cloud'
}

export function toComposerModelOptions(
  models: Array<{
    id: string
    label: string
    provider: string
    source: 'cloud' | 'profile' | 'custom'
    profileId: string | null
    backend?: string | null
    description?: string | null
    enabled: boolean
    supportsReasoningEffort?: boolean
    reasoningEffortOptions?: string[]
    reasoningEffort?: string | null
    reasoningFast?: boolean
    supportsImageInputs?: boolean
    supportsPdfInputs?: boolean
    supportsAudioInputs?: boolean
    supportsVideoInputs?: boolean
    contextWindow?: number | null
  }>
): ComposerModelOption[] {
  return models
    .filter(model => model.enabled)
    .map(model => ({
      provider: model.provider,
      model: model.id,
      label: formatComposerModelLabel(model.label),
      speed: modelOptionBadge(model),
      profileId: model.profileId,
      source: model.source,
      backend: model.backend ?? null,
      supportsReasoningEffort: Boolean(model.supportsReasoningEffort),
      reasoningEffortOptions: model.reasoningEffortOptions || [],
      reasoningEffort: model.reasoningEffort ?? 'medium',
      reasoningFast: Boolean(model.reasoningFast),
      contextWindow:
        typeof model.contextWindow === 'number' && model.contextWindow > 0
          ? model.contextWindow
          : null,
      ...resolveMultimodalCapabilityFlags(model)
    }))
}

export type ComposerRuntimeModelRef = {
  provider: string
  model: string
  openaiProfileId?: string | null
}

/**
 * Resolve the selected catalog option when the same model id can appear under
 * multiple providers (e.g. OpenCode Zen + DS4 both listing DeepSeek V4 Flash).
 */
export function resolveComposerModelOption(
  options: ComposerModelOption[],
  runtime: ComposerRuntimeModelRef | null | undefined
): ComposerModelOption | null {
  if (!runtime?.model) return null
  const modelId = runtime.model
  const runtimeProvider = String(runtime.provider || '')
    .trim()
    .toLowerCase()
  const profileId = String(runtime.openaiProfileId || '').trim() || null
  const matches = options.filter(option => option.model === modelId)
  if (matches.length === 0) return null
  if (matches.length === 1) return matches[0]

  // Cloud/proxy providers keep their catalog provider (opencode, anthropic, …).
  // Prefer that over any lingering local profile id.
  if (runtimeProvider && runtimeProvider !== 'openai') {
    const byCatalogProvider = matches.find(
      option =>
        String(option.provider || '')
          .trim()
          .toLowerCase() === runtimeProvider
    )
    if (byCatalogProvider) return byCatalogProvider
  }

  if (profileId) {
    const byProfile = matches.find(
      option => (option.profileId || null) === profileId
    )
    if (byProfile) return byProfile
    if (profileId === 'openai_cloud') {
      const cloudOpenAI = matches.find(
        option =>
          option.provider === 'openai' &&
          option.source !== 'profile' &&
          !option.profileId
      )
      if (cloudOpenAI) return cloudOpenAI
    }
  }

  if (runtimeProvider === 'openai') {
    const local = matches.find(
      option => option.source === 'profile' || option.provider === 'local'
    )
    if (local && profileId && profileId !== 'openai_cloud') return local
    const cloudOpenAI = matches.find(
      option =>
        option.provider === 'openai' &&
        option.source !== 'profile' &&
        !option.profileId
    )
    if (cloudOpenAI) return cloudOpenAI
  }

  return matches[0]
}

export function isComposerModelSelected(
  option: ComposerModelOption,
  runtime: ComposerRuntimeModelRef | null | undefined,
  options: ComposerModelOption[] = []
): boolean {
  const resolved = resolveComposerModelOption(
    options.length > 0 ? options : [option],
    runtime
  )
  if (!resolved) return false
  return (
    resolved.model === option.model &&
    resolved.provider === option.provider &&
    (resolved.profileId || null) === (option.profileId || null) &&
    (resolved.source || null) === (option.source || null)
  )
}

export const REASONING_EFFORT_LABELS: Record<string, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High'
}

export function formatReasoningEffortLabel(effort: string | null | undefined): string {
  const key = String(effort || 'medium')
    .trim()
    .toLowerCase()
  return REASONING_EFFORT_LABELS[key] || REASONING_EFFORT_LABELS.medium
}

export function formatModelEffortBadge(option: {
  reasoningEffort?: string | null
  reasoningFast?: boolean
}): string {
  return `${formatReasoningEffortLabel(option.reasoningEffort)}${
    option.reasoningFast ? ' Fast' : ''
  }`
}
