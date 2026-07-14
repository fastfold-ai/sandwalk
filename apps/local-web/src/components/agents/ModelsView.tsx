import type {
  AgentModel,
  CreateAgentModelInput,
  DiscoverModelEndpointInput,
  IntegrationSummary,
  ModelProfile,
  ModelProfileProbeResult,
  UpsertModelProfileInput
} from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronDown,
  Cpu,
  Eye,
  EyeOff,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { ListRowsSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

const CLOUD_PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google Gemini' },
  { value: 'xai', label: 'xAI (Grok)' },
  { value: 'nvidia', label: 'NVIDIA' },
  { value: 'opencode', label: 'OpenCode Zen' }
] as const

const MODEL_LIST_PREVIEW_LIMIT = 10

/** Mirrors CLI `OPENAI_PROFILE_DEFAULTS` / setup backend menu (local backends only). */
const PROFILE_BACKENDS = [
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

type ProfileBackendValue = (typeof PROFILE_BACKENDS)[number]['value']

function ProfileBackendIcon({
  icon,
  className
}: {
  icon: string
  className?: string
}) {
  if (icon === 'cpu') {
    return <Cpu className={cn('text-muted-foreground size-4 shrink-0', className)} />
  }
  return (
    <img
      src={icon}
      alt=""
      className={cn('size-4 shrink-0 rounded-sm object-cover', className)}
    />
  )
}

function profileBackend(
  value: string
): (typeof PROFILE_BACKENDS)[number] | undefined {
  return PROFILE_BACKENDS.find(item => item.value === value)
}

function isKnownDefaultBaseUrl(url: string): boolean {
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

function isKnownDefaultLabel(label: string): boolean {
  const needle = label.trim().toLowerCase()
  return PROFILE_BACKENDS.some(
    item => item.defaultLabel.toLowerCase() === needle
  )
}

/** Mirror CLI `format_discovered_model_label` for preview rows. */
function formatDiscoveredModelLabel(modelId: string): string {
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

const LLM_API_KEY_ORDER = [
  'openai',
  'anthropic',
  'google',
  'xai',
  'nvidia',
  'opencode'
] as const

const LLM_API_KEY_COPY: Record<
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

function ModelToggle({
  enabled,
  pending,
  label,
  onToggle
}: {
  enabled: boolean
  pending?: boolean
  label: string
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      disabled={pending}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700',
        pending && 'cursor-not-allowed opacity-60'
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onToggle()
      }}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          enabled ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}

function primaryEnvVar(integration: IntegrationSummary) {
  return (
    integration.fields.find(field => field.isSecret)?.envVar ||
    integration.envVar
  )
}

function primaryMaskedPreview(integration: IntegrationSummary) {
  return (
    integration.fields.find(field => field.isSecret)?.maskedPreview ||
    integration.maskedPreview
  )
}

export function ModelsView({
  integrations,
  onListModels,
  onUpdateModelEnabled,
  onCreateCustomModel,
  onDeleteCustomModel,
  onListProfiles,
  onCreateProfile,
  onUpdateProfile,
  onDeleteProfile,
  onProbeProfile,
  onDiscoverEndpoint,
  onSaveProviderKey,
  onClearProviderKey,
  embedded = false
}: {
  integrations: IntegrationSummary[]
  onListModels: (options?: {
    discover?: boolean
    signal?: AbortSignal
  }) => Promise<AgentModel[]>
  onUpdateModelEnabled: (
    modelId: string,
    enabled: boolean,
    signal?: AbortSignal
  ) => Promise<AgentModel>
  onCreateCustomModel: (
    input: CreateAgentModelInput,
    signal?: AbortSignal
  ) => Promise<AgentModel>
  onDeleteCustomModel: (
    modelId: string,
    signal?: AbortSignal
  ) => Promise<void>
  onListProfiles: (signal?: AbortSignal) => Promise<ModelProfile[]>
  onCreateProfile: (
    input: UpsertModelProfileInput,
    signal?: AbortSignal
  ) => Promise<ModelProfile>
  onUpdateProfile: (
    profileId: string,
    input: UpsertModelProfileInput,
    signal?: AbortSignal
  ) => Promise<ModelProfile>
  onDeleteProfile: (profileId: string, signal?: AbortSignal) => Promise<void>
  onProbeProfile: (
    profileId: string,
    signal?: AbortSignal
  ) => Promise<ModelProfileProbeResult>
  onDiscoverEndpoint: (
    input: DiscoverModelEndpointInput,
    signal?: AbortSignal
  ) => Promise<ModelProfileProbeResult>
  onSaveProviderKey: (
    key: string,
    envVar: string,
    value: string
  ) => Promise<void>
  onClearProviderKey: (key: string) => Promise<void>
  /** Compact chrome for setup wizard embedding. */
  embedded?: boolean
}) {
  const [models, setModels] = useState<AgentModel[]>([])
  const [profiles, setProfiles] = useState<ModelProfile[]>([])
  const [query, setQuery] = useState('')
  const [sourceFilter, setSourceFilter] = useState<'all' | 'cloud' | 'local'>(
    'all'
  )
  const [providerFilter, setProviderFilter] = useState<string>('all')
  const [showAllModels, setShowAllModels] = useState(false)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingEnabled, setPendingEnabled] = useState<Record<string, boolean>>(
    {}
  )
  const [apiKeysOpen, setApiKeysOpen] = useState(true)
  const [customOpen, setCustomOpen] = useState(true)
  const [profilesOpen, setProfilesOpen] = useState(true)
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({})
  const [savingKeys, setSavingKeys] = useState<Record<string, boolean>>({})
  const [revealedKeys, setRevealedKeys] = useState<Record<string, boolean>>({})
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<ModelProfile | null>(null)
  const [savingProfile, setSavingProfile] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([])
  const [discoverSource, setDiscoverSource] = useState<string | null>(null)
  const [discoverError, setDiscoverError] = useState<string | null>(null)
  const [showProfileApiKey, setShowProfileApiKey] = useState(false)
  const [customDialogOpen, setCustomDialogOpen] = useState(false)
  const [savingCustom, setSavingCustom] = useState(false)
  const [customForm, setCustomForm] = useState({
    provider: 'openai',
    id: '',
    label: ''
  })
  const [form, setForm] = useState({
    label: '',
    backend: 'ollama' as ProfileBackendValue,
    baseUrl: 'http://127.0.0.1:11434/v1',
    apiKey: ''
  })

  const selectedBackend = profileBackend(form.backend) || PROFILE_BACKENDS[0]

  const providerIntegrations = useMemo(() => {
    const byKey = new Map(integrations.map(item => [item.key, item]))
    return LLM_API_KEY_ORDER.map(key => byKey.get(key)).filter(
      (item): item is IntegrationSummary => Boolean(item)
    )
  }, [integrations])

  const customModels = useMemo(
    () => models.filter(model => model.source === 'custom'),
    [models]
  )

  const load = useCallback(
    async (discover = true) => {
      setError(null)
      const [nextModels, nextProfiles] = await Promise.all([
        onListModels({ discover }),
        onListProfiles()
      ])
      setModels(nextModels)
      setProfiles(nextProfiles)
    },
    [onListModels, onListProfiles]
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void load(true)
      .catch(err => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [load])

  const providerFilterOptions = useMemo(() => {
    const counts = new Map<string, number>()
    for (const model of models) {
      const key = model.source === 'profile' ? 'local' : model.provider
      counts.set(key, (counts.get(key) || 0) + 1)
    }
    const labels: Record<string, string> = {
      anthropic: 'Anthropic',
      openai: 'OpenAI',
      google: 'Gemini',
      xai: 'xAI',
      nvidia: 'NVIDIA',
      opencode: 'OpenCode Zen',
      local: 'Local'
    }
    return Array.from(counts.entries())
      .map(([id, count]) => ({
        id,
        label: labels[id] || id,
        count
      }))
      .sort((a, b) => a.label.localeCompare(b.label))
  }, [models])

  const filteredModels = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return models.filter(model => {
      const isLocal = model.source === 'profile'
      const isCloud = model.source === 'cloud' || model.source === 'custom'
      if (sourceFilter === 'local' && !isLocal) return false
      if (sourceFilter === 'cloud' && !isCloud) return false
      const providerKey = isLocal ? 'local' : model.provider
      if (providerFilter !== 'all' && providerKey !== providerFilter) return false
      if (!needle) return true
      const haystack = [
        model.id,
        model.label,
        model.description || '',
        model.provider,
        model.source,
        model.profileId || ''
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [models, query, sourceFilter, providerFilter])

  const isSearching = query.trim().length > 0
  const visibleModels =
    showAllModels || isSearching
      ? filteredModels
      : filteredModels.slice(0, MODEL_LIST_PREVIEW_LIMIT)
  const canToggleModelList =
    !isSearching && filteredModels.length > MODEL_LIST_PREVIEW_LIMIT

  const refresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRefreshing(false)
    }
  }

  const toggleModel = async (model: AgentModel) => {
    const key = `${model.profileId || 'cloud'}:${model.id}`
    setPendingEnabled(prev => ({ ...prev, [key]: true }))
    setError(null)
    try {
      const updated = await onUpdateModelEnabled(model.id, !model.enabled)
      setModels(prev =>
        prev.map(item =>
          item.id === model.id &&
          item.profileId === model.profileId &&
          item.source === model.source
            ? { ...item, enabled: updated.enabled }
            : item
        )
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setPendingEnabled(prev => {
        const next = { ...prev }
        delete next[key]
        return next
      })
    }
  }

  const saveProviderKey = async (integration: IntegrationSummary) => {
    const envVar = primaryEnvVar(integration)
    const value = (keyDrafts[integration.key] || '').trim()
    if (!value) {
      setError(`Enter a ${integration.name} API key to save.`)
      return
    }
    setSavingKeys(prev => ({ ...prev, [integration.key]: true }))
    setError(null)
    try {
      await onSaveProviderKey(integration.key, envVar, value)
      setKeyDrafts(prev => ({ ...prev, [integration.key]: '' }))
      // Re-discover models for proxy providers (e.g. OpenCode Go) whose catalog
      // is only available once an API key is configured.
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSavingKeys(prev => ({ ...prev, [integration.key]: false }))
    }
  }

  const clearProviderKey = async (integration: IntegrationSummary) => {
    if (
      !window.confirm(
        `Remove the saved ${integration.name} API key from this local agent?`
      )
    ) {
      return
    }
    setSavingKeys(prev => ({ ...prev, [integration.key]: true }))
    setError(null)
    try {
      await onClearProviderKey(integration.key)
      setKeyDrafts(prev => ({ ...prev, [integration.key]: '' }))
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSavingKeys(prev => ({ ...prev, [integration.key]: false }))
    }
  }

  const resetDiscoverState = () => {
    setDiscoveredModels([])
    setDiscoverSource(null)
    setDiscoverError(null)
  }

  const resetProfileDialogSecrets = () => {
    setShowProfileApiKey(false)
  }

  const applyBackendDefaults = (
    backendValue: ProfileBackendValue,
    previous: typeof form
  ) => {
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

  const openCreate = () => {
    setEditing(null)
    const ollama = PROFILE_BACKENDS[0]
    setForm({
      label: ollama.defaultLabel,
      backend: ollama.value,
      baseUrl: ollama.baseUrl,
      apiKey: ''
    })
    resetDiscoverState()
    resetProfileDialogSecrets()
    setDialogOpen(true)
  }

  const openCustomCreate = () => {
    setCustomForm({ provider: 'openai', id: '', label: '' })
    setCustomDialogOpen(true)
  }

  const saveCustomModel = async () => {
    const modelId = customForm.id.trim()
    if (!modelId) {
      setError('Enter a cloud model name (for example gpt-4.1-mini).')
      return
    }
    setSavingCustom(true)
    setError(null)
    try {
      await onCreateCustomModel({
        id: modelId,
        provider: customForm.provider,
        label: customForm.label.trim() || modelId
      })
      setCustomDialogOpen(false)
      await load(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSavingCustom(false)
    }
  }

  const removeCustomModel = async (model: AgentModel) => {
    if (!window.confirm(`Remove custom model “${model.label}” from the list?`)) {
      return
    }
    setError(null)
    try {
      await onDeleteCustomModel(model.id)
      await load(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const openEdit = (profile: ModelProfile) => {
    const backendValue =
      profile.backend === 'openai'
        ? 'other'
        : ((PROFILE_BACKENDS.find(item => item.value === profile.backend)
            ?.value || 'other') as ProfileBackendValue)
    setEditing(profile)
    setForm({
      label: profile.label,
      backend: backendValue,
      baseUrl: profile.baseUrl || '',
      apiKey: ''
    })
    resetDiscoverState()
    resetProfileDialogSecrets()
    setDialogOpen(true)
  }

  const discoverModels = async () => {
    const baseUrl = form.baseUrl.trim()
    if (!baseUrl) {
      setDiscoverError('Enter a base URL before discovering models.')
      return
    }
    setDiscovering(true)
    setDiscoverError(null)
    try {
      const result = await onDiscoverEndpoint({
        backend: form.backend,
        baseUrl,
        apiKey: form.apiKey.trim() || null
      })
      const models = result.models || []
      setDiscoveredModels(models)
      setDiscoverSource(result.modelsSource || null)
      if (result.error && models.length === 0) {
        setDiscoverError(result.error)
        return
      }
      if (models.length === 0) {
        setDiscoverError(
          'No models found. Check the base URL and API key, then try again.'
        )
      }
    } catch (err) {
      setDiscoverError(err instanceof Error ? err.message : String(err))
      setDiscoveredModels([])
      setDiscoverSource(null)
    } finally {
      setDiscovering(false)
    }
  }

  const saveProfile = async () => {
    setSavingProfile(true)
    setError(null)
    try {
      // Prefer a freshly discovered model as the profile default; otherwise keep
      // the existing default when editing. All discovered models still appear in
      // the model list via live probe after save.
      const defaultModel =
        discoveredModels[0] || editing?.defaultModel || null
      const input: UpsertModelProfileInput = {
        label: form.label.trim() || null,
        backend: editing?.isCloud ? 'openai' : form.backend,
        baseUrl: editing?.isCloud ? null : form.baseUrl.trim() || null,
        defaultModel,
        apiKey: form.apiKey.trim() || null
      }
      if (editing) {
        await onUpdateProfile(editing.id, input)
      } else {
        await onCreateProfile(input)
      }
      setDialogOpen(false)
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSavingProfile(false)
    }
  }

  const removeProfile = async (profile: ModelProfile) => {
    if (profile.isCloud) return
    if (!window.confirm(`Delete profile “${profile.label}”?`)) return
    setError(null)
    try {
      await onDeleteProfile(profile.id)
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const probeProfile = async (profile: ModelProfile) => {
    setError(null)
    try {
      const result = await onProbeProfile(profile.id)
      if (result.error && result.models.length === 0) {
        setError(`${profile.label}: ${result.error}`)
      }
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const localProfiles = profiles.filter(profile => !profile.isCloud)

  return (
    <ScrollArea className={embedded ? 'h-[min(28rem,55vh)]' : 'flex-1'}>
      <div
        className={cn(
          'mx-auto w-full space-y-8',
          embedded ? 'max-w-5xl p-1' : 'max-w-7xl p-4 md:p-6'
        )}
      >
        {!embedded ? (
          <div>
            <h2 className="text-2xl font-semibold">Models</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Choose which cloud and local models are available to the agent.
            </p>
          </div>
        ) : null}

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        <section className="bg-muted/20 border-border/60 space-y-0 overflow-hidden rounded-xl border shadow-sm">
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <Input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Add or search model"
              className="border-0 bg-transparent shadow-none focus-visible:ring-0"
            />
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground h-8 shrink-0 gap-1 whitespace-nowrap"
              onClick={openCustomCreate}
            >
              <Plus className="size-3.5" />
              Add Custom Model
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground h-8 shrink-0 gap-1 whitespace-nowrap"
              onClick={() => {
                setProfilesOpen(true)
                openCreate()
              }}
            >
              <Plus className="size-3.5" />
              Add Local Model
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-8 shrink-0"
              disabled={refreshing || loading}
              onClick={() => void refresh()}
              aria-label="Refresh models"
            >
              {refreshing || loading ? (
                <Loader2 className="animate-spin" />
              ) : (
                <RefreshCw />
              )}
            </Button>
          </div>

          <div className="space-y-2 border-b px-3 py-2">
            <div className="flex flex-wrap items-center gap-1">
              {(
                [
                  { id: 'all', label: 'All' },
                  { id: 'cloud', label: 'Cloud' },
                  { id: 'local', label: 'Local' }
                ] as const
              ).map(option => (
                <button
                  key={option.id}
                  type="button"
                  className={cn(
                    'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                    sourceFilter === option.id
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                  onClick={() => {
                    setSourceFilter(option.id)
                    setShowAllModels(false)
                    if (option.id === 'local') setProviderFilter('local')
                    else if (
                      option.id === 'cloud' &&
                      providerFilter === 'local'
                    ) {
                      setProviderFilter('all')
                    }
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
            {providerFilterOptions.length > 0 ? (
              <div className="flex flex-wrap items-center gap-1">
                <button
                  type="button"
                  className={cn(
                    'rounded-md px-2 py-1 text-xs font-normal transition-colors',
                    providerFilter === 'all'
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                  onClick={() => {
                    setProviderFilter('all')
                    setShowAllModels(false)
                  }}
                >
                  All ({models.length})
                </button>
                {providerFilterOptions.map(option => (
                  <button
                    key={option.id}
                    type="button"
                    className={cn(
                      'rounded-md px-2 py-1 text-xs font-normal transition-colors',
                      providerFilter === option.id
                        ? 'bg-muted text-foreground'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                    )}
                    onClick={() => {
                      setProviderFilter(option.id)
                      setShowAllModels(false)
                      if (option.id === 'local') setSourceFilter('local')
                      else if (sourceFilter === 'local') setSourceFilter('cloud')
                    }}
                  >
                    {option.label} ({option.count})
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <div className="divide-y">
            {loading && models.length === 0 ? (
              <ListRowsSkeleton rows={8} />
            ) : filteredModels.length === 0 ? (
              <div className="text-muted-foreground px-4 py-8 text-sm">
                {providerFilter !== 'all'
                  ? 'No models match this provider filter.'
                  : sourceFilter === 'local'
                    ? 'No local models yet. Add a Local LLM endpoint to discover them.'
                    : sourceFilter === 'cloud'
                      ? 'No cloud models match this filter.'
                      : 'No models match this search.'}
              </div>
            ) : (
              visibleModels.map(model => {
                const key = `${model.profileId || model.source}:${model.id}`
                const sourceLabel =
                  model.source === 'cloud'
                    ? `${model.provider} · cloud`
                    : model.source === 'custom'
                      ? `${model.provider} · custom`
                      : `local · ${model.profileId || 'endpoint'}`
                return (
                  <div
                    key={key}
                    className="flex items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium">
                        {model.label}
                      </div>
                      <div className="text-muted-foreground truncate text-xs">
                        {sourceLabel}
                        {model.health ? ` · ${model.health}` : ''}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {model.source === 'custom' ? (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8"
                          onClick={() => void removeCustomModel(model)}
                          aria-label={`Remove ${model.label}`}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      ) : null}
                      <ModelToggle
                        enabled={model.enabled}
                        pending={Boolean(pendingEnabled[key])}
                        label={`${model.enabled ? 'Hide' : 'Show'} ${model.label}`}
                        onToggle={() => void toggleModel(model)}
                      />
                    </div>
                  </div>
                )
              })
            )}
          </div>
          {canToggleModelList ? (
            <div className="border-t px-4 py-3">
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground text-sm font-medium"
                onClick={() => setShowAllModels(open => !open)}
              >
                {showAllModels
                  ? 'Show fewer models'
                  : `View All Models (${filteredModels.length})`}
              </button>
            </div>
          ) : null}
        </section>

        <section className="space-y-4">
          <button
            type="button"
            className="flex w-full items-center justify-between text-left"
            onClick={() => setApiKeysOpen(open => !open)}
          >
            <h3 className="text-base font-semibold">API Keys</h3>
            <ChevronDown
              className={cn(
                'text-muted-foreground size-4 transition-transform',
                apiKeysOpen && 'rotate-180'
              )}
            />
          </button>

          {apiKeysOpen ? (
            <div className="space-y-10">
              {providerIntegrations.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  No LLM provider integrations available from the agent backend.
                </p>
              ) : null}
              {providerIntegrations.map(integration => {
                const copy =
                  LLM_API_KEY_COPY[
                    integration.key as (typeof LLM_API_KEY_ORDER)[number]
                  ]
                const draft = keyDrafts[integration.key] || ''
                const saving = Boolean(savingKeys[integration.key])
                return (
                  <div key={integration.key} className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-1">
                        <div className="text-sm font-medium text-zinc-700 dark:text-zinc-200">
                          {copy?.title || `${integration.name} API Key`}
                        </div>
                        <p className="text-muted-foreground text-sm leading-relaxed">
                          {copy ? (
                            <>
                              {copy.beforeLink}
                              {integration.setupUrl ? (
                                <a
                                  href={integration.setupUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-foreground underline underline-offset-2"
                                >
                                  {copy.linkLabel}
                                </a>
                              ) : (
                                copy.linkLabel
                              )}
                              {copy.afterLink}
                            </>
                          ) : (
                            <>
                              {integration.description}{' '}
                              {integration.setupUrl ? (
                                <a
                                  href={integration.setupUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-foreground underline underline-offset-2"
                                >
                                  Get API key
                                </a>
                              ) : null}
                            </>
                          )}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2 pt-0.5">
                        <span className="text-muted-foreground text-xs">
                          {integration.configured ? 'Secret saved' : 'Not set'}
                        </span>
                        <ModelToggle
                          enabled={integration.configured}
                          pending={saving}
                          label={
                            integration.configured
                              ? `Clear ${integration.name} API key`
                              : `${integration.name} API key not set`
                          }
                          onToggle={() => {
                            if (integration.configured) {
                              void clearProviderKey(integration)
                            }
                          }}
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                      <div className="relative flex-1">
                        <Input
                          type={
                            revealedKeys[integration.key] ? 'text' : 'password'
                          }
                          value={draft}
                          autoComplete="off"
                          onChange={event =>
                            setKeyDrafts(prev => ({
                              ...prev,
                              [integration.key]: event.target.value
                            }))
                          }
                          placeholder={
                            integration.configured
                              ? primaryMaskedPreview(integration) ||
                                'Secret saved. Enter a new key to replace it.'
                              : copy?.placeholderUnset ||
                                `Enter your ${integration.name} API Key`
                          }
                          className="bg-muted/40 pr-9 font-mono text-sm"
                          onKeyDown={event => {
                            if (event.key === 'Enter') {
                              event.preventDefault()
                              void saveProviderKey(integration)
                            }
                          }}
                        />
                        <button
                          type="button"
                          className="text-muted-foreground hover:text-foreground absolute right-2 top-1/2 -translate-y-1/2"
                          aria-label={
                            revealedKeys[integration.key]
                              ? 'Hide API key'
                              : 'Show API key'
                          }
                          onClick={() =>
                            setRevealedKeys(prev => ({
                              ...prev,
                              [integration.key]: !prev[integration.key]
                            }))
                          }
                        >
                          {revealedKeys[integration.key] ? (
                            <EyeOff className="size-4" />
                          ) : (
                            <Eye className="size-4" />
                          )}
                        </button>
                      </div>
                      <Button
                        variant="outline"
                        className="sm:w-auto"
                        disabled={saving || !draft.trim()}
                        onClick={() => void saveProviderKey(integration)}
                      >
                        {saving ? <Loader2 className="animate-spin" /> : null}
                        Save
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : null}
        </section>

        <section className="space-y-3 border-t pt-6">
          <button
            type="button"
            className="flex w-full items-center justify-between text-left"
            onClick={() => setCustomOpen(open => !open)}
          >
            <div className="min-w-0 pr-3">
              <h3 className="text-base font-semibold">Custom cloud models</h3>
              <p className="text-muted-foreground mt-1 text-sm">
                Add a provider model by name (for example an OpenAI deployment
                id) so it appears in the list above.
              </p>
            </div>
            <ChevronDown
              className={cn(
                'text-muted-foreground size-4 shrink-0 transition-transform',
                customOpen && 'rotate-180'
              )}
            />
          </button>

          {customOpen ? (
            <div className="space-y-3">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground"
                onClick={openCustomCreate}
              >
                <Plus />
                Add Custom Model
              </Button>

              <div className="divide-y rounded-xl border">
                {customModels.length === 0 ? (
                  <div className="text-muted-foreground px-4 py-6 text-sm">
                    No custom cloud models yet.
                  </div>
                ) : (
                  customModels.map(model => (
                    <div
                      key={model.id}
                      className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">
                          {model.label}
                        </div>
                        <div className="text-muted-foreground truncate font-mono text-xs">
                          {model.provider} · {model.id}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => void removeCustomModel(model)}
                        aria-label={`Remove ${model.label}`}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : null}
        </section>

        <section className="space-y-3 border-t pt-6">
          <button
            type="button"
            className="flex w-full items-center justify-between text-left"
            onClick={() => setProfilesOpen(open => !open)}
          >
            <div className="min-w-0 pr-3">
              <h3 className="text-base font-semibold">Local LLM</h3>
              <p className="text-muted-foreground mt-1 text-sm">
                Discovered models from these endpoints appear in the model list
                above.
              </p>
            </div>
            <ChevronDown
              className={cn(
                'text-muted-foreground size-4 shrink-0 transition-transform',
                profilesOpen && 'rotate-180'
              )}
            />
          </button>

          {profilesOpen ? (
            <div className="space-y-3">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-foreground"
                onClick={openCreate}
              >
                <Plus />
                Add Local LLM
              </Button>

              <div className="divide-y rounded-xl border">
                {localProfiles.length === 0 ? (
                  <div className="text-muted-foreground px-4 py-6 text-sm">
                    No local OpenAI-compatible endpoints yet.
                  </div>
                ) : (
                  localProfiles.map(profile => {
                    const backendMeta =
                      profileBackend(
                        profile.backend === 'openai' ? 'other' : profile.backend
                      ) || PROFILE_BACKENDS.find(item => item.value === 'other')!
                    return (
                    <div
                      key={profile.id}
                      className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                    >
                      <div className="flex min-w-0 items-start gap-3">
                        <ProfileBackendIcon
                          icon={backendMeta.icon}
                          className="mt-0.5 size-5 rounded-md"
                        />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">
                            {profile.label}
                            {profile.isActive ? (
                              <span className="text-muted-foreground ml-2 text-xs">
                                active
                              </span>
                            ) : null}
                          </div>
                          <div className="text-muted-foreground truncate font-mono text-xs">
                            {profile.backend}
                            {profile.baseUrl ? ` · ${profile.baseUrl}` : ''}
                          </div>
                          <div className="text-muted-foreground text-xs">
                            {profile.hasApiKey
                              ? `Key ${profile.apiKeyPreview || '••••'}`
                              : 'No API key'}
                            {profile.defaultModel
                              ? ` · default ${profile.defaultModel}`
                              : ''}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8"
                          onClick={() => void probeProfile(profile)}
                          aria-label={`Probe ${profile.label}`}
                        >
                          <RefreshCw className="size-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8"
                          onClick={() => openEdit(profile)}
                          aria-label={`Edit ${profile.label}`}
                        >
                          <Pencil className="size-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8"
                          onClick={() => void removeProfile(profile)}
                          aria-label={`Delete ${profile.label}`}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    </div>
                    )
                  })
                )}
              </div>
            </div>
          ) : null}
        </section>
      </div>

      <Dialog
        open={dialogOpen}
        onOpenChange={open => {
          setDialogOpen(open)
          if (!open) {
            resetDiscoverState()
            resetProfileDialogSecrets()
          }
        }}
      >
        <DialogContent className="flex max-h-[min(90dvh,42rem)] flex-col gap-4 overflow-hidden sm:max-w-lg">
          <DialogHeader className="shrink-0">
            <DialogTitle>
              {editing ? 'Edit Local LLM' : 'Add Local LLM'}
            </DialogTitle>
          </DialogHeader>
          <div className="grid shrink-0 gap-3">
            <label className="space-y-1.5 text-sm">
              <span className="text-muted-foreground text-xs">Label</span>
              <Input
                value={form.label}
                onChange={event =>
                  setForm(prev => ({ ...prev, label: event.target.value }))
                }
                placeholder={selectedBackend.defaultLabel}
              />
            </label>

            <div className="space-y-1.5 text-sm">
              <span className="text-muted-foreground text-xs">Backend</span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    className="h-9 w-full justify-between px-3 font-normal"
                  >
                    <span className="flex min-w-0 items-center gap-2 truncate">
                      <ProfileBackendIcon icon={selectedBackend.icon} />
                      <span className="flex min-w-0 items-baseline gap-1.5 truncate">
                        <span className="truncate">{selectedBackend.label}</span>
                        <span className="text-muted-foreground shrink-0 text-[11px]">
                          · {selectedBackend.hint}
                        </span>
                      </span>
                    </span>
                    <ChevronDown className="text-muted-foreground size-4 shrink-0" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="start"
                  className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-72"
                >
                  <DropdownMenuLabel className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                    Endpoint type
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {PROFILE_BACKENDS.map(option => {
                    const selected = option.value === form.backend
                    return (
                      <DropdownMenuItem
                        key={option.value}
                        className="gap-2"
                        onSelect={() => {
                          setForm(prev => applyBackendDefaults(option.value, prev))
                          resetDiscoverState()
                        }}
                      >
                        <ProfileBackendIcon icon={option.icon} />
                        <span className="flex min-w-0 flex-1 items-baseline gap-1.5 truncate">
                          <span className="truncate text-sm">{option.label}</span>
                          <span className="text-muted-foreground truncate text-[11px]">
                            · {option.hint}
                          </span>
                        </span>
                        {selected ? (
                          <Check className="ml-auto size-4 shrink-0" />
                        ) : null}
                      </DropdownMenuItem>
                    )
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            <label className="space-y-1.5 text-sm">
              <span className="text-muted-foreground text-xs">Base URL</span>
              <Input
                value={form.baseUrl}
                onChange={event => {
                  setForm(prev => ({
                    ...prev,
                    baseUrl: event.target.value
                  }))
                  resetDiscoverState()
                }}
                placeholder={selectedBackend.baseUrl}
                className="font-mono text-sm"
              />
              <span className="text-muted-foreground block text-[11px]">
                Suggested for {selectedBackend.label}: {selectedBackend.baseUrl}
              </span>
            </label>

            <div className="space-y-1.5 text-sm">
              <span className="text-muted-foreground text-xs">
                API key {editing?.hasApiKey ? '(leave blank to keep)' : ''}
              </span>
              <div className="relative">
                <Input
                  type={showProfileApiKey ? 'text' : 'password'}
                  value={form.apiKey}
                  onChange={event =>
                    setForm(prev => ({ ...prev, apiKey: event.target.value }))
                  }
                  placeholder={
                    editing?.hasApiKey
                      ? editing.apiKeyPreview ||
                        'Secret saved. Enter a new key to replace it.'
                      : selectedBackend.value === 'ollama'
                        ? 'Optional (Ollama usually needs none)'
                        : 'Optional'
                  }
                  className="pr-10 font-mono text-sm"
                  autoComplete="off"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute top-1/2 right-1 size-7 -translate-y-1/2"
                  onClick={() => setShowProfileApiKey(open => !open)}
                  aria-label={
                    showProfileApiKey ? 'Hide API key' : 'Show API key'
                  }
                >
                  {showProfileApiKey ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                </Button>
              </div>
            </div>
          </div>

          <div className="flex min-h-0 min-w-0 flex-col gap-1.5">
            <div className="flex shrink-0 items-center justify-between gap-2">
              <span className="text-muted-foreground text-xs">Models</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                disabled={discovering || !form.baseUrl.trim()}
                onClick={() => void discoverModels()}
              >
                {discovering ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="size-3.5" />
                )}
                Discover models
              </Button>
            </div>

            {discoveredModels.length > 0 ? (
              <ScrollArea className="h-52 w-full min-w-0 rounded-xl border">
                <div className="divide-y pr-2">
                  {discoveredModels.map(modelId => (
                    <div
                      key={modelId}
                      className="flex min-w-0 items-center justify-between gap-3 px-4 py-3"
                      title={modelId}
                    >
                      <div className="min-w-0 flex-1 overflow-hidden">
                        <div className="truncate text-sm font-medium">
                          {formatDiscoveredModelLabel(modelId)}
                        </div>
                        <div className="text-muted-foreground truncate text-xs">
                          local · {selectedBackend.label.toLowerCase()}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            ) : (
              <p className="text-muted-foreground text-[11px]">
                Discover to preview models from this endpoint. After Save, they
                appear as selectable entries in the model list.
              </p>
            )}
            {discoverSource && discoveredModels.length > 0 ? (
              <span className="text-muted-foreground block shrink-0 text-[11px]">
                Found {discoveredModels.length} via {discoverSource}. After
                Save, all of them appear in the model list.
              </span>
            ) : null}
            {discoverError ? (
              <span className="text-destructive block shrink-0 text-[11px]">
                {discoverError}
              </span>
            ) : null}
          </div>

          <DialogFooter className="shrink-0">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button disabled={savingProfile} onClick={() => void saveProfile()}>
              {savingProfile ? <Loader2 className="animate-spin" /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={customDialogOpen} onOpenChange={setCustomDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Custom Model</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <label className="space-y-1.5 text-sm">
              <span className="text-muted-foreground text-xs">Provider</span>
              <select
                className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm"
                value={customForm.provider}
                onChange={event =>
                  setCustomForm(prev => ({
                    ...prev,
                    provider: event.target.value
                  }))
                }
              >
                {CLOUD_PROVIDERS.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="text-muted-foreground text-xs">Model name</span>
              <Input
                value={customForm.id}
                onChange={event =>
                  setCustomForm(prev => ({ ...prev, id: event.target.value }))
                }
                placeholder={
                  customForm.provider === 'anthropic'
                    ? 'claude-sonnet-4-20250514'
                    : 'gpt-4.1-mini'
                }
                className="font-mono text-sm"
              />
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="text-muted-foreground text-xs">
                Display label (optional)
              </span>
              <Input
                value={customForm.label}
                onChange={event =>
                  setCustomForm(prev => ({
                    ...prev,
                    label: event.target.value
                  }))
                }
                placeholder="Friendly name in the model list"
              />
            </label>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCustomDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              disabled={savingCustom || !customForm.id.trim()}
              onClick={() => void saveCustomModel()}
            >
              {savingCustom ? <Loader2 className="animate-spin" /> : null}
              Add to list
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ScrollArea>
  )
}
