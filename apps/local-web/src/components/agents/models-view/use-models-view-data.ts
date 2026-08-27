import type {
  AgentModel,
  IntegrationSummary,
  ModelProfile,
  ToggleModelFavoriteResult
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { catalogModelPrefKey } from '@/lib/composer-models'

import {
  filterModelCatalog,
  LLM_API_KEY_ORDER,
  MODEL_LIST_PREVIEW_LIMIT,
  type ModelSourceFilter
} from './models-view-utils'

type ModelsViewDataCallbacks = {
  onListModels: (options?: {
    discover?: boolean
    signal?: AbortSignal
  }) => Promise<AgentModel[]>
  onUpdateModelEnabled: (
    modelId: string,
    enabled: boolean,
    signal?: AbortSignal,
    provider?: string | null
  ) => Promise<AgentModel>
  onListProfiles: (signal?: AbortSignal) => Promise<ModelProfile[]>
  onLoadModelPreferences: () => Promise<{ favorites: string[] }>
  onToggleModelFavorite: (model: AgentModel) => Promise<ToggleModelFavoriteResult>
}

type ModelsViewDataInput = ModelsViewDataCallbacks & {
  integrations: IntegrationSummary[]
  setError: (error: string | null) => void
}

export function useModelsViewData({
  integrations,
  onListModels,
  onUpdateModelEnabled,
  onListProfiles,
  onLoadModelPreferences,
  onToggleModelFavorite,
  setError
}: ModelsViewDataInput) {
  const [models, setModels] = useState<AgentModel[]>([])
  const [profiles, setProfiles] = useState<ModelProfile[]>([])
  const [favoriteKeys, setFavoriteKeys] = useState<string[]>([])
  const [query, setQuery] = useState('')
  const [sourceFilter, setSourceFilter] = useState<ModelSourceFilter>('all')
  const [providerFilter, setProviderFilter] = useState<string>('all')
  const [showAllModels, setShowAllModels] = useState(false)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [pendingEnabled, setPendingEnabled] = useState<Record<string, boolean>>(
    {}
  )

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

  const onListModelsRef = useRef(onListModels)
  onListModelsRef.current = onListModels
  const onListProfilesRef = useRef(onListProfiles)
  onListProfilesRef.current = onListProfiles
  const onLoadModelPreferencesRef = useRef(onLoadModelPreferences)
  onLoadModelPreferencesRef.current = onLoadModelPreferences
  const onToggleModelFavoriteRef = useRef(onToggleModelFavorite)
  onToggleModelFavoriteRef.current = onToggleModelFavorite

  const load = useCallback(
    async (discover = true) => {
      setError(null)
      const [nextModels, nextProfiles, nextPrefs] = await Promise.all([
        onListModelsRef.current({ discover }),
        onListProfilesRef.current(),
        onLoadModelPreferencesRef.current().catch(() => ({ favorites: [] }))
      ])
      setModels(nextModels)
      setProfiles(nextProfiles)
      setFavoriteKeys(nextPrefs.favorites || [])
    },
    [setError]
  )

  // Mount-only catalog fetch. Parent often passes inline callbacks; do not
  // re-subscribe when those identities change or we loop on setLoading.
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
  }, [])

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
      moonshot: 'Kimi',
      nvidia: 'NVIDIA',
      opencode: 'OpenCode Zen',
      deepseek: 'DeepSeek',
      minimax: 'MiniMax',
      mistral: 'Mistral',
      qwen: 'Qwen Cloud',
      together: 'Together AI',
      openrouter: 'OpenRouter',
      cerebras: 'Cerebras',
      groq: 'Groq',
      fireworks: 'Fireworks AI',
      bedrock: 'Amazon Bedrock',
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

  const filteredModels = useMemo(
    () =>
      filterModelCatalog(models, {
        query,
        sourceFilter,
        providerFilter,
        favoriteKeys
      }),
    [models, query, sourceFilter, providerFilter, favoriteKeys]
  )

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
    const key = `${model.provider}:${model.profileId || 'cloud'}:${model.id}`
    setPendingEnabled(prev => ({ ...prev, [key]: true }))
    setError(null)
    try {
      const updated = await onUpdateModelEnabled(
        model.id,
        !model.enabled,
        undefined,
        model.provider
      )
      setModels(prev =>
        prev.map(item =>
          item.id === model.id &&
          item.provider === model.provider &&
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

  const toggleFavorite = async (model: AgentModel) => {
    const key = catalogModelPrefKey(model)
    const wasFavorite = favoriteKeys.includes(key)
    setFavoriteKeys(prev =>
      wasFavorite ? prev.filter(item => item !== key) : [...prev, key]
    )
    setError(null)
    try {
      const result = await onToggleModelFavoriteRef.current(model)
      setFavoriteKeys(result.favorites)
    } catch (err) {
      setFavoriteKeys(prev =>
        wasFavorite
          ? prev.includes(key)
            ? prev
            : [...prev, key]
          : prev.filter(item => item !== key)
      )
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const localProfiles = useMemo(
    () => profiles.filter(profile => !profile.isCloud),
    [profiles]
  )

  return {
    models,
    profiles,
    favoriteKeys,
    query,
    sourceFilter,
    providerFilter,
    loading,
    refreshing,
    pendingEnabled,
    showAllModels,
    providerIntegrations,
    customModels,
    providerFilterOptions,
    filteredModels,
    visibleModels,
    canToggleModelList,
    localProfiles,
    load,
    setQuery,
    setSourceFilter,
    setProviderFilter,
    setShowAllModels,
    refresh,
    toggleModel,
    toggleFavorite
  }
}

export type ModelsViewDataState = ReturnType<typeof useModelsViewData>
