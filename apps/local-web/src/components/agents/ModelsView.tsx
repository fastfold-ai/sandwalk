import type {
  AgentModel,
  CreateAgentModelInput,
  DiscoverModelEndpointInput,
  IntegrationSummary,
  ModelProfile,
  ModelProfileProbeResult,
  UpsertModelProfileInput
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import {
  ModelsCustomDialog,
  ModelsProfileDialog
} from './models-view/models-view-dialogs'
import { ModelsListSection } from './models-view/models-view-list'
import {
  ModelsApiKeysSection,
  ModelsCustomSection,
  ModelsProfilesSection
} from './models-view/models-view-settings'
import {
  applyBackendDefaults,
  LLM_API_KEY_ORDER,
  MODEL_LIST_PREVIEW_LIMIT,
  PROFILE_BACKENDS,
  profileBackend,
  type ProfileBackendValue,
  type ProfileFormState
} from './models-view/models-view-utils'

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
  const [form, setForm] = useState<ProfileFormState>({
    label: '',
    backend: 'ollama',
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
    const envVar =
      integration.fields.find(field => field.isSecret)?.envVar ||
      integration.envVar
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
      const nextModels = result.models || []
      setDiscoveredModels(nextModels)
      setDiscoverSource(result.modelsSource || null)
      if (result.error && nextModels.length === 0) {
        setDiscoverError(result.error)
        return
      }
      if (nextModels.length === 0) {
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

        <ModelsListSection
          query={query}
          sourceFilter={sourceFilter}
          providerFilter={providerFilter}
          models={models}
          loading={loading}
          refreshing={refreshing}
          filteredModels={filteredModels}
          visibleModels={visibleModels}
          providerFilterOptions={providerFilterOptions}
          canToggleModelList={canToggleModelList}
          showAllModels={showAllModels}
          pendingEnabled={pendingEnabled}
          onQueryChange={setQuery}
          onSourceFilterChange={setSourceFilter}
          onProviderFilterChange={setProviderFilter}
          onShowAllModelsChange={setShowAllModels}
          onOpenCustomCreate={openCustomCreate}
          onOpenCreate={() => {
            setProfilesOpen(true)
            openCreate()
          }}
          onRefresh={() => void refresh()}
          onToggleModel={model => void toggleModel(model)}
          onRemoveCustomModel={model => void removeCustomModel(model)}
        />

        <ModelsApiKeysSection
          open={apiKeysOpen}
          providerIntegrations={providerIntegrations}
          keyDrafts={keyDrafts}
          savingKeys={savingKeys}
          revealedKeys={revealedKeys}
          onOpenChange={setApiKeysOpen}
          onKeyDraftChange={(key, value) =>
            setKeyDrafts(prev => ({ ...prev, [key]: value }))
          }
          onRevealedKeyChange={(key, revealed) =>
            setRevealedKeys(prev => ({ ...prev, [key]: revealed }))
          }
          onSaveProviderKey={integration => void saveProviderKey(integration)}
          onClearProviderKey={integration => void clearProviderKey(integration)}
        />

        <ModelsCustomSection
          open={customOpen}
          customModels={customModels}
          onOpenChange={setCustomOpen}
          onOpenCustomCreate={openCustomCreate}
          onRemoveCustomModel={model => void removeCustomModel(model)}
        />

        <ModelsProfilesSection
          open={profilesOpen}
          localProfiles={localProfiles}
          onOpenChange={setProfilesOpen}
          onOpenCreate={openCreate}
          onProbeProfile={profile => void probeProfile(profile)}
          onOpenEdit={openEdit}
          onRemoveProfile={profile => void removeProfile(profile)}
        />
      </div>

      <ModelsProfileDialog
        open={dialogOpen}
        editing={editing}
        form={form}
        selectedBackend={selectedBackend}
        savingProfile={savingProfile}
        discovering={discovering}
        discoveredModels={discoveredModels}
        discoverSource={discoverSource}
        discoverError={discoverError}
        showProfileApiKey={showProfileApiKey}
        onOpenChange={open => {
          setDialogOpen(open)
          if (!open) {
            resetDiscoverState()
            resetProfileDialogSecrets()
          }
        }}
        onFormChange={setForm}
        onBackendChange={backend => {
          setForm(prev => applyBackendDefaults(backend, prev))
          resetDiscoverState()
        }}
        onDiscoverModels={() => void discoverModels()}
        onSaveProfile={() => void saveProfile()}
        onShowProfileApiKeyChange={setShowProfileApiKey}
        onResetDiscoverState={resetDiscoverState}
      />

      <ModelsCustomDialog
        open={customDialogOpen}
        customForm={customForm}
        savingCustom={savingCustom}
        onOpenChange={setCustomDialogOpen}
        onCustomFormChange={setCustomForm}
        onSaveCustomModel={() => void saveCustomModel()}
      />
    </ScrollArea>
  )
}
