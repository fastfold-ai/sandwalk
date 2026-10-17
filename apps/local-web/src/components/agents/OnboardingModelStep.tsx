import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  IntegrationSummary,
  RuntimeSettings
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  type ComposerModelOption,
  toComposerModelOptions
} from '@/lib/composer-models'

import { ChatGPTSignInCard } from './models-view/ChatGPTSignInCard'
import { OnboardingModelCloudPanel } from './onboarding/onboarding-model-cloud-panel'
import { OnboardingModelDefaultPicker } from './onboarding/onboarding-model-default-picker'
import { OnboardingModelLocalPanel } from './onboarding/onboarding-model-local-panel'
import {
  LLM_API_KEY_ORDER,
  type OnboardingBackendValue,
  OnboardingChip,
  PROFILE_BACKENDS
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

  const [providerModelOptions, setProviderModelOptions] = useState<
    ComposerModelOption[]
  >([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [runtimeSettings, setRuntimeSettings] =
    useState<RuntimeSettings | null>(null)
  const [defaultBusy, setDefaultBusy] = useState(false)
  const [defaultSaved, setDefaultSaved] = useState(false)
  const [showDefaultPicker, setShowDefaultPicker] = useState(false)

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

  // Set when the user connected via Sign in with ChatGPT rather than a key.
  const [chatGPTConnected, setChatGPTConnected] = useState(false)
  const CHATGPT_PROVIDER = 'openai-chatgpt'

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

  const loadProviderModels = useCallback(
    async (providerKey: string) => {
      setModelsLoading(true)
      try {
        const [models, runtime] = await Promise.all([
          client.listModels({
            enabledOnly: true,
            discover: true
          }),
          client.getRuntimeSettings().catch(() => null)
        ])
        // Composer picker, but only the just-verified provider — never the
        // full catalog of providers that still have no API key.
        const filtered = toComposerModelOptions(
          models.filter(
            item =>
              item.source === 'cloud' &&
              String(item.provider || '')
                .trim()
                .toLowerCase() === providerKey.toLowerCase()
          )
        )
        setProviderModelOptions(filtered)
        if (runtime) {
          const nextModel =
            filtered.find(item => item.model === runtime.model)?.model ||
            filtered[0]?.model ||
            runtime.model
          setRuntimeSettings({
            ...runtime,
            provider: providerKey,
            model: nextModel
          })
        } else if (filtered[0]) {
          setRuntimeSettings({
            provider: providerKey,
            model: filtered[0].model,
            openaiBaseUrl: null,
            agentProfile: 'default',
            toolMode: 'default',
            recursionLimit: 100_000,
            maxSdkTurns: 500,
            groupToolTraces: true,
            toolTraceDetailLimit: 0,
            backgroundWatchTimeoutS: 7200,
            interruptDrainTimeoutS: 10,
            parallelMaxThreads: 5,
            toolHealthEnabled: true,
            toolHealthFailThreshold: 2,
            toolHealthSuppressSeconds: 900
          })
        }
      } catch {
        setProviderModelOptions([])
      } finally {
        setModelsLoading(false)
      }
    },
    [client]
  )

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
    if (!value && !selectedIntegration.configured) {
      setError(`Paste a ${selectedIntegration.name} API key.`)
      return
    }
    setError(null)
    setNotice(null)
    setCloudBusy(true)
    setShowDefaultPicker(false)
    setDefaultSaved(false)
    try {
      if (value) {
        await client.updateIntegration(selectedIntegration.key, {
          [envVar]: value
        })
        setCloudKey('')
      }
      const result = await client.validateIntegration(selectedIntegration.key)
      if (!result.ok) {
        setCloudSaved(false)
        setError(
          result.message ||
            `${selectedIntegration.name} key did not work. Check the key and try again.`
        )
        return
      }
      await client.updateRuntimeSettings({
        provider: selectedIntegration.key
      })
      setCloudSaved(true)
      setNotice(`${selectedIntegration.name} key verified.`)
      await refreshIntegrations()
      setShowDefaultPicker(true)
      await loadProviderModels(selectedIntegration.key)
    } catch (err) {
      setCloudSaved(false)
      setError(err instanceof Error ? err.message : 'Could not save API key.')
    } finally {
      setCloudBusy(false)
    }
  }

  const onChatGPTConnected = async () => {
    setError(null)
    setNotice(null)
    setSelectedCloud(null)
    setCloudKey('')
    setCloudSaved(false)
    setDefaultSaved(false)
    setChatGPTConnected(true)
    try {
      await client.updateRuntimeSettings({ provider: CHATGPT_PROVIDER })
      setNotice('ChatGPT connected. Pick a default model below.')
      await refreshIntegrations()
      setShowDefaultPicker(true)
      await loadProviderModels(CHATGPT_PROVIDER)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'ChatGPT connected, but the models could not be loaded.'
      )
    }
  }

  const onChatGPTDisconnected = async () => {
    setChatGPTConnected(false)
    setShowDefaultPicker(false)
    setProviderModelOptions([])
    setNotice('ChatGPT disconnected.')
  }

  const selectDefaultModel = async (
    provider: string,
    model: string,
    _profileId?: string | null
  ) => {
    setDefaultBusy(true)
    setError(null)
    try {
      const next = await client.updateRuntimeSettings({
        provider,
        model
      })
      setRuntimeSettings(next)
      setDefaultSaved(true)
      setNotice(
        `${model} will start your first chat. You can change it anytime.`
      )
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not set default model.'
      )
    } finally {
      setDefaultBusy(false)
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
      setSelectedModel(null)
      if (result.error) {
        setDiscoverError(result.error)
      } else if (!models.length) {
        setDiscoverError('No models found at this endpoint.')
      } else {
        setNotice(
          `Found ${models.length} healthy model${models.length === 1 ? '' : 's'}${
            result.modelsSource ? ` via ${result.modelsSource}` : ''
          }. Pick one for your first chat.`
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

  const saveLocal = async (modelId?: string) => {
    const model = modelId || selectedModel
    if (!model) {
      setError('Pick a discovered model for your first chat.')
      return
    }
    if (modelId) setSelectedModel(modelId)
    setError(null)
    setNotice(null)
    setLocalBusy(true)
    try {
      await client.createModelProfile({
        id: localBackend === 'llama' ? 'llama_local' : undefined,
        label: localLabel.trim() || selectedBackend.defaultLabel,
        backend: localBackend,
        baseUrl: localUrl.trim() || selectedBackend.baseUrl,
        apiKey: localKey.trim() || undefined,
        defaultModel: model,
        setActive: true,
        setDefault: true
      })
      await client.updateRuntimeSettings({
        provider: 'openai',
        model
      })
      setLocalSaved(true)
      setNotice(
        `${model} will start your first chat. You can change it anytime.`
      )
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
      <ChatGPTSignInCard
        client={client}
        compact
        onConnected={onChatGPTConnected}
        onDisconnected={onChatGPTDisconnected}
      />
      <div className="border-border/70 space-y-2 rounded-xl border p-3">
        <div className="flex items-start gap-3">
          <span className="bg-muted/50 grid size-9 shrink-0 place-items-center rounded-lg">
            <img src="/local-llm/llama.png" alt="" className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Llama</p>
            <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">
              Run a model on this machine. One click installs it, then you pick
              the model for your first chat.
            </p>
          </div>
        </div>
        <button
          type="button"
          className="bg-foreground text-background inline-flex h-8 items-center rounded-md px-3 text-sm font-medium"
          onClick={() => {
            setMode('local')
            pickBackend('llama')
            setError(null)
            setNotice(null)
            void client.llamaRuntimeEnsure()
          }}
        >
          Set up Llama
        </button>
      </div>
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
            setShowDefaultPicker(false)
          }}
        >
          Local
        </OnboardingChip>
      </div>

      {mode === 'cloud' ? (
        <>
          <div className="flex items-center gap-3">
            <span className="bg-border/70 h-px flex-1" />
            <span className="text-muted-foreground text-[11px] tracking-wide uppercase">
              or add an API key
            </span>
            <span className="bg-border/70 h-px flex-1" />
          </div>
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
              setShowDefaultPicker(false)
              setDefaultSaved(false)
              setProviderModelOptions([])
              setChatGPTConnected(false)
              setError(null)
              setNotice(null)
            }}
            onCloudKeyChange={value => {
              setCloudKey(value)
              setCloudSaved(false)
              setShowDefaultPicker(false)
            }}
            onToggleShowKey={() => setShowCloudKey(open => !open)}
            onSave={() => void saveCloud()}
          />
          {showDefaultPicker && (selectedIntegration || chatGPTConnected) ? (
            <OnboardingModelDefaultPicker
              providerName={
                chatGPTConnected
                  ? 'ChatGPT plan'
                  : selectedIntegration?.name || 'this provider'
              }
              modelOptions={providerModelOptions}
              runtimeSettings={runtimeSettings}
              loading={modelsLoading}
              saving={defaultBusy}
              saved={defaultSaved}
              onModelSelect={selectDefaultModel}
            />
          ) : null}
        </>
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
          llamaRuntime={{
            load: () => client.llamaRuntimeStatus(),
            ensure: () => client.llamaRuntimeEnsure(),
            catalog: query => client.llamaRuntimeCatalog(query),
            install: (repo, quant) => client.llamaRuntimeInstall(repo, quant),
            remove: modelId => client.llamaRuntimeRemove(modelId),
            loadModel: modelId => client.llamaRuntimeLoad(modelId),
            unloadModel: modelId => client.llamaRuntimeUnload(modelId),
            update: () => client.llamaRuntimeUpdate()
          }}
          onUseLlama={modelId => void saveLocal(modelId)}
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
