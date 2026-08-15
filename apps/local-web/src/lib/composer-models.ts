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
  /** False when Fast (thinking off) is not allowed for this model. */
  supportsReasoningFast?: boolean
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
    supportsReasoningFast?: boolean
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
      supportsReasoningFast: model.supportsReasoningFast !== false,
      reasoningEffortOptions: model.reasoningEffortOptions || [],
      reasoningEffort: model.reasoningEffort ?? 'medium',
      reasoningFast:
        model.supportsReasoningFast === false
          ? false
          : Boolean(model.reasoningFast),
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

/** Patch Effort/Fast on matching catalog rows after a settings update. */
export function patchComposerModelEffort(
  options: ComposerModelOption[],
  changes: {
    provider: string
    model: string
    reasoningEffort?: string
    reasoningFast?: boolean
  }
): ComposerModelOption[] {
  const modelId = String(changes.model || '').trim()
  const provider = String(changes.provider || '')
    .trim()
    .toLowerCase()
  if (!modelId) return options
  return options.map(option => {
    if (option.model !== modelId) return option
    const optionProvider = String(option.provider || '')
      .trim()
      .toLowerCase()
    // Prefer same provider; still patch when the catalog row is the only match.
    const providerMatches =
      !provider ||
      optionProvider === provider ||
      (provider === 'openai' &&
        (optionProvider === 'local' || option.source === 'profile'))
    if (!providerMatches) return option
    return {
      ...option,
      ...(typeof changes.reasoningEffort === 'string'
        ? { reasoningEffort: changes.reasoningEffort }
        : {}),
      ...(typeof changes.reasoningFast === 'boolean'
        ? { reasoningFast: changes.reasoningFast }
        : {})
    }
  })
}

/** Strip vendor prefixes (`deepseek/deepseek-v4-flash` → `deepseek-v4-flash`). */
export function composerModelBareId(modelId: string): string {
  const raw = String(modelId || '').trim()
  const slash = raw.lastIndexOf('/')
  return slash >= 0 ? raw.slice(slash + 1) : raw
}

/** Stable favorites/recent key — matches CLI ``Config.model_pref_key``. */
export function composerModelPrefKey(option: {
  provider: string
  model: string
  profileId?: string | null
}): string {
  const mid = String(option.model || '').trim()
  const pid = String(option.profileId || '').trim()
  const prov = String(option.provider || '')
    .trim()
    .toLowerCase()
  if (pid) return `local:${pid}:${mid}`
  if (prov && mid) return `${prov}:${mid}`
  return mid
}

/** Catalog rows use ``id`` instead of composer ``model``. Same key space. */
export function catalogModelPrefKey(model: {
  id: string
  provider: string
  profileId?: string | null
}): string {
  return composerModelPrefKey({
    provider: model.provider,
    model: model.id,
    profileId: model.profileId
  })
}

/** Higher is better. Returns -1 when the option does not match ``query``. */
export function scoreComposerModelSearch(
  option: ComposerModelOption,
  query: string
): number {
  const q = query.trim().toLowerCase()
  if (!q) return 0
  const label = option.label.toLowerCase()
  const model = option.model.toLowerCase()
  const bare = composerModelBareId(option.model).toLowerCase()
  const provider = String(option.provider || '')
    .trim()
    .toLowerCase()
  const speed = String(option.speed || '')
    .trim()
    .toLowerCase()
  const words = label.split(/[\s\-_/]+/).filter(Boolean)

  if (label === q || model === q || bare === q) return 1000
  if (label.startsWith(q)) return 900
  if (bare.startsWith(q) || model.startsWith(q)) return 850
  if (words.some(word => word.startsWith(q))) return 800
  if (provider.startsWith(q) || speed.startsWith(q)) return 700
  if (label.includes(q)) return 500
  if (bare.includes(q) || model.includes(q)) return 400
  if (provider.includes(q) || speed.includes(q)) return 300
  const haystack = [
    label,
    model,
    provider,
    speed,
    option.source || '',
    option.profileId || ''
  ]
    .join(' ')
    .toLowerCase()
  if (haystack.includes(q)) return 100
  return -1
}

export type ComposerModelPreferences = {
  favorites: string[]
  recent: string[]
}

export type RankedComposerModelSection = {
  title: string | null
  options: ComposerModelOption[]
}

/**
 * Filter + rank for the composer picker. Empty query → Favorites → Recent → rest.
 * With a query → relevance-ranked matches (favorites boosted slightly).
 */
export function rankComposerModelOptions(
  options: ComposerModelOption[],
  query: string,
  preferences?: ComposerModelPreferences | null
): RankedComposerModelSection[] {
  const favKeys = preferences?.favorites || []
  const recentKeys = preferences?.recent || []
  const favSet = new Set(favKeys)
  const needle = query.trim()

  if (needle) {
    const scored = options
      .map(option => {
        const score = scoreComposerModelSearch(option, needle)
        if (score < 0) return null
        const key = composerModelPrefKey(option)
        const boost = favSet.has(key) ? 50 : 0
        return { option, score: score + boost }
      })
      .filter((row): row is { option: ComposerModelOption; score: number } =>
        Boolean(row)
      )
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return a.option.label.localeCompare(b.option.label)
      })
    if (scored.length === 0) return []
    return [{ title: null, options: scored.map(row => row.option) }]
  }

  const byKey = new Map(
    options.map(option => [composerModelPrefKey(option), option])
  )
  const sections: RankedComposerModelSection[] = []
  const seen = new Set<string>()

  const take = (title: string, keys: string[]) => {
    const rows = keys
      .map(key => byKey.get(key))
      .filter((option): option is ComposerModelOption => Boolean(option))
      .filter(option => {
        const key = composerModelPrefKey(option)
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
    if (rows.length > 0) sections.push({ title, options: rows })
  }

  take('Favorites', favKeys)
  take(
    'Recent',
    recentKeys.filter(key => !favSet.has(key))
  )

  const rest = options.filter(option => !seen.has(composerModelPrefKey(option)))
  if (rest.length > 0) {
    sections.push({ title: sections.length > 0 ? 'Models' : null, options: rest })
  }
  return sections
}

/** Shared search score for Models dashboard rows (AgentModel-shaped). */
export function scoreModelCatalogSearch(
  model: {
    id: string
    label: string
    provider: string
    description?: string | null
    source?: string | null
    profileId?: string | null
  },
  query: string
): number {
  return scoreComposerModelSearch(
    {
      provider: model.provider,
      model: model.id,
      label: model.label,
      speed: model.provider,
      profileId: model.profileId,
      source: (model.source as ComposerModelOption['source']) || undefined
    },
    query
  )
}
