import type { AgentModel, IntegrationSummary, ModelProfile } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  LLM_API_KEY_ORDER,
  MODEL_LIST_PREVIEW_LIMIT
} from './models-view-utils'

type ModelsViewDataCallbacks = {
  onListModels: (options?: {
    discover?: boolean
    signal?: AbortSignal
  }) => Promise<AgentModel[]>
  onUpdateModelEnabled: (
    modelId: string,
    enabled: boolean,
    signal?: AbortSignal
  ) => Promise<AgentModel>
  onListProfiles: (signal?: AbortSignal) => Promise<ModelProfile[]>
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
  setError
}: ModelsViewDataInput) {
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
    [onListModels, onListProfiles, setError]
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
  }, [load, setError])

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

  const localProfiles = profiles.filter(profile => !profile.isCloud)

  return {
    models,
    profiles,
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
    toggleModel
  }
}

export type ModelsViewDataState = ReturnType<typeof useModelsViewData>
