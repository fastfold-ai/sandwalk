import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { OnboardingModelCloudPanel } from './onboarding/onboarding-model-cloud-panel'
import { OnboardingModelLocalPanel } from './onboarding/onboarding-model-local-panel'
import {
  LLM_API_KEY_ORDER,
  OnboardingChip,
  PROFILE_BACKENDS,
  type OnboardingBackendValue
} from './onboarding/onboarding-model-shared'

type Mode = 'cloud' | 'local'

export function OnboardingModelStep({
  client
}: {
  client: LocalAgentClient
}) {
  const [mode, setMode] = useState<Mode>('cloud')
  const [integrations, setIntegrations] = useState<IntegrationSummary[]>([])
  const [loadingIntegrations, setLoadingIntegrations] = useState(true)

  const [selectedCloud, setSelectedCloud] = useState<string | null>(null)
  const [cloudKey, setCloudKey] = useState('')
  const [showCloudKey, setShowCloudKey] = useState(false)
  const [cloudBusy, setCloudBusy] = useState(false)
  const [cloudSaved, setCloudSaved] = useState(false)

  const [localBackend, setLocalBackend] = useState<OnboardingBackendValue>('ollama')
  const [localUrl, setLocalUrl] = useState<string>(PROFILE_BACKENDS[0]!.baseUrl)
  const [localKey, setLocalKey] = useState('')
  const [showLocalKey, setShowLocalKey] = useState(false)
  const [localLabel, setLocalLabel] = useState<string>(
    PROFILE_BACKENDS[0]!.defaultLabel
  )
  const [discoverBusy, setDiscoverBusy] = useState(false)
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([])
  const [discoverSource, setDiscoverSource] = useState<string | null>(null)
  const [discoverError, setDiscoverError] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [localBusy, setLocalBusy] = useState(false)
  const [localSaved, setLocalSaved] = useState(false)

  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const cloudProviders = useMemo(() => {
    const byKey = new Map(integrations.map(item => [item.key, item]))
    return LLM_API_KEY_ORDER.map(key => byKey.get(key)).filter(
      (item): item is IntegrationSummary => Boolean(item)
    )
  }, [integrations])

  const selectedBackend =
    PROFILE_BACKENDS.find(item => item.value === localBackend) ||
    PROFILE_BACKENDS[0]!

  const selectedIntegration = cloudProviders.find(
    item => item.key === selectedCloud
  )

  const refreshIntegrations = useCallback(async () => {
    setLoadingIntegrations(true)
    try {
      const next = await client.listIntegrations()
      setIntegrations(next)
    } catch {
      // Keep wizard usable if listing fails.
    } finally {
      setLoadingIntegrations(false)
    }
  }, [client])

  useEffect(() => {
    void refreshIntegrations()
  }, [refreshIntegrations])

  const pickBackend = (value: OnboardingBackendValue) => {
    const next = PROFILE_BACKENDS.find(item => item.value === value)
    if (!next) return
    setLocalBackend(next.value)
    setLocalUrl(next.baseUrl)
    setLocalLabel(next.defaultLabel)
    setDiscoveredModels([])
    setDiscoverSource(null)
    setDiscoverError(null)
    setSelectedModel(null)
    setLocalSaved(false)
  }

  const saveCloud = async () => {
    if (!selectedIntegration) {
      setError('Pick a cloud provider.')
      return
    }
    const envVar =
      selectedIntegration.fields.find(field => field.isSecret)?.envVar ||
      selectedIntegration.envVar
    const value = cloudKey.trim()
    if (!value) {
      setError(`Paste a ${selectedIntegration.name} API key.`)
      return
    }
    setError(null)
    setNotice(null)
    setCloudBusy(true)
    try {
      await client.updateIntegration(selectedIntegration.key, {
        [envVar]: value
      })
      await client.updateRuntimeSettings({
        provider: selectedIntegration.key
      })
      setCloudKey('')
      setCloudSaved(true)
      setNotice(`${selectedIntegration.name} connected.`)
      await refreshIntegrations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save API key.')
    } finally {
      setCloudBusy(false)
    }
  }

  const discoverLocal = async () => {
    setDiscoverBusy(true)
    setDiscoverError(null)
    setError(null)
    setNotice(null)
    try {
      const result = await client.discoverModelEndpoint({
        backend: localBackend,
        baseUrl: localUrl.trim() || selectedBackend.baseUrl,
        apiKey: localKey.trim() || null
      })
      const models = result.models || []
      setDiscoveredModels(models)
      setDiscoverSource(result.modelsSource || null)
      setSelectedModel(models[0] || null)
      if (result.error) {
        setDiscoverError(result.error)
      } else if (!models.length) {
        setDiscoverError('No models found at this endpoint.')
      } else {
        setNotice(
          `Found ${models.length} model${models.length === 1 ? '' : 's'}${
            result.modelsSource ? ` via ${result.modelsSource}` : ''
          }.`
        )
      }
    } catch (err) {
      setDiscoverError(
        err instanceof Error ? err.message : 'Discovery failed.'
      )
      setDiscoveredModels([])
      setSelectedModel(null)
    } finally {
      setDiscoverBusy(false)
    }
  }

  const saveLocal = async () => {
    setError(null)
    setNotice(null)
    setLocalBusy(true)
    try {
      await client.createModelProfile({
        label: localLabel.trim() || selectedBackend.defaultLabel,
        backend: localBackend,
        baseUrl: localUrl.trim() || selectedBackend.baseUrl,
        apiKey: localKey.trim() || undefined,
        defaultModel: selectedModel || undefined,
        setActive: true,
        setDefault: true
      })
      await client.updateRuntimeSettings({ provider: 'openai' })
      setLocalSaved(true)
      setNotice(`${selectedBackend.label} profile saved.`)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not save local profile.'
      )
    } finally {
      setLocalBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <OnboardingChip
          selected={mode === 'cloud'}
          onClick={() => {
            setMode('cloud')
            setError(null)
            setNotice(null)
          }}
        >
          Cloud
        </OnboardingChip>
        <OnboardingChip
          selected={mode === 'local'}
          onClick={() => {
            setMode('local')
            setError(null)
            setNotice(null)
          }}
        >
          Local
        </OnboardingChip>
      </div>

      {mode === 'cloud' ? (
        <OnboardingModelCloudPanel
          loadingIntegrations={loadingIntegrations}
          cloudProviders={cloudProviders}
          selectedCloud={selectedCloud}
          selectedIntegration={selectedIntegration}
          cloudKey={cloudKey}
          showCloudKey={showCloudKey}
          cloudBusy={cloudBusy}
          cloudSaved={cloudSaved}
          onSelectProvider={key => {
            setSelectedCloud(key)
            setCloudKey('')
            setShowCloudKey(false)
            setCloudSaved(false)
            setError(null)
            setNotice(null)
          }}
          onCloudKeyChange={value => {
            setCloudKey(value)
            setCloudSaved(false)
          }}
          onToggleShowKey={() => setShowCloudKey(open => !open)}
          onSave={() => void saveCloud()}
        />
      ) : (
        <OnboardingModelLocalPanel
          localBackend={localBackend}
          localUrl={localUrl}
          localKey={localKey}
          showLocalKey={showLocalKey}
          localLabel={localLabel}
          discoverBusy={discoverBusy}
          discoveredModels={discoveredModels}
          discoverSource={discoverSource}
          discoverError={discoverError}
          selectedModel={selectedModel}
          localBusy={localBusy}
          localSaved={localSaved}
          selectedBackend={selectedBackend}
          onPickBackend={pickBackend}
          onLocalLabelChange={value => {
            setLocalLabel(value)
            setLocalSaved(false)
          }}
          onLocalUrlChange={value => {
            setLocalUrl(value)
            setLocalSaved(false)
            setDiscoveredModels([])
            setSelectedModel(null)
          }}
          onLocalKeyChange={value => {
            setLocalKey(value)
            setLocalSaved(false)
          }}
          onToggleShowKey={() => setShowLocalKey(open => !open)}
          onDiscover={() => void discoverLocal()}
          onSave={() => void saveLocal()}
          onSelectModel={modelId => {
            setSelectedModel(modelId)
            setLocalSaved(false)
          }}
        />
      )}

      {error ? <p className="text-destructive text-sm">{error}</p> : null}
      {notice ? <p className="text-muted-foreground text-sm">{notice}</p> : null}
    </div>
  )
}
