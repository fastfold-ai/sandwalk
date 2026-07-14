import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { Check, Cpu, Eye, EyeOff, Loader2, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

const LLM_API_KEY_ORDER = [
  'openai',
  'anthropic',
  'google',
  'xai',
  'nvidia',
  'opencode'
] as const

/** Same backends as ModelsView local modal / CLI setup. */
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
    label: 'Other',
    hint: 'OpenAI-compatible',
    baseUrl: 'http://127.0.0.1:11434/v1',
    defaultLabel: 'Custom Compatible Endpoint',
    icon: 'cpu'
  }
] as const

type Mode = 'cloud' | 'local'
type BackendValue = (typeof PROFILE_BACKENDS)[number]['value']

function primaryEnvVar(integration: IntegrationSummary) {
  return (
    integration.fields.find(field => field.isSecret)?.envVar ||
    integration.envVar
  )
}

function primaryMaskedPreview(integration: IntegrationSummary) {
  return (
    integration.fields.find(field => field.isSecret)?.maskedPreview ||
    integration.maskedPreview ||
    null
  )
}

function BackendIcon({
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

function Chip({
  selected,
  onClick,
  children
}: {
  selected: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
        selected
          ? 'border-foreground bg-foreground text-background'
          : 'border-border text-muted-foreground hover:text-foreground'
      )}
    >
      {children}
    </button>
  )
}

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

  const [localBackend, setLocalBackend] = useState<BackendValue>('ollama')
  const [localUrl, setLocalUrl] = useState(PROFILE_BACKENDS[0]!.baseUrl)
  const [localKey, setLocalKey] = useState('')
  const [showLocalKey, setShowLocalKey] = useState(false)
  const [localLabel, setLocalLabel] = useState(PROFILE_BACKENDS[0]!.defaultLabel)
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

  const pickBackend = (value: BackendValue) => {
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
    const envVar = primaryEnvVar(selectedIntegration)
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
        <Chip
          selected={mode === 'cloud'}
          onClick={() => {
            setMode('cloud')
            setError(null)
            setNotice(null)
          }}
        >
          Cloud
        </Chip>
        <Chip
          selected={mode === 'local'}
          onClick={() => {
            setMode('local')
            setError(null)
            setNotice(null)
          }}
        >
          Local
        </Chip>
      </div>

      {mode === 'cloud' ? (
        <div className="space-y-3">
          {loadingIntegrations ? (
            <p className="text-muted-foreground flex items-center gap-2 text-sm">
              <Loader2 className="size-4 animate-spin" />
              Loading providers…
            </p>
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {cloudProviders.map(item => {
                const selected = selectedCloud === item.key
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => {
                      setSelectedCloud(item.key)
                      setCloudKey('')
                      setShowCloudKey(false)
                      setCloudSaved(false)
                      setError(null)
                      setNotice(null)
                    }}
                    className={cn(
                      'hover:bg-muted/50 flex items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-colors',
                      selected
                        ? 'border-foreground bg-muted/40'
                        : 'border-border/70'
                    )}
                  >
                    <IntegrationIcon integration={item} size="sm" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        {item.name}
                      </span>
                      <span className="text-muted-foreground block text-[11px]">
                        {item.configured ? 'Connected' : 'Add key'}
                      </span>
                    </span>
                    {item.configured ? (
                      <Check className="text-foreground size-3.5 shrink-0" />
                    ) : null}
                  </button>
                )
              })}
            </div>
          )}

          {selectedIntegration ? (
            <div className="space-y-2 pt-1">
              <div className="relative">
                <Input
                  type={showCloudKey ? 'text' : 'password'}
                  autoComplete="off"
                  placeholder={
                    selectedIntegration.configured
                      ? primaryMaskedPreview(selectedIntegration) ||
                        'Secret saved. Enter a new key to replace it.'
                      : `Paste ${selectedIntegration.name} API key`
                  }
                  value={cloudKey}
                  onChange={event => {
                    setCloudKey(event.target.value)
                    setCloudSaved(false)
                  }}
                  className="pr-10 font-mono text-sm"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute top-1/2 right-1 size-7 -translate-y-1/2"
                  onClick={() => setShowCloudKey(open => !open)}
                  aria-label={showCloudKey ? 'Hide API key' : 'Show API key'}
                >
                  {showCloudKey ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                </Button>
              </div>
              {selectedIntegration.configured &&
              primaryMaskedPreview(selectedIntegration) &&
              !cloudKey.trim() ? (
                <p className="text-muted-foreground font-mono text-[11px]">
                  Saved key {primaryMaskedPreview(selectedIntegration)}
                </p>
              ) : null}
              <div className="flex items-center justify-between gap-3">
                {selectedIntegration.setupUrl ? (
                  <a
                    href={selectedIntegration.setupUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-muted-foreground hover:text-foreground text-xs underline underline-offset-2"
                  >
                    Get a {selectedIntegration.name} key
                  </a>
                ) : (
                  <span />
                )}
                <Button
                  type="button"
                  disabled={cloudBusy || !cloudKey.trim()}
                  onClick={() => void saveCloud()}
                >
                  {cloudBusy ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : cloudSaved ? (
                    <Check className="size-4" />
                  ) : null}
                  {cloudSaved ? 'Saved' : 'Save & use'}
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {PROFILE_BACKENDS.map(item => (
              <Chip
                key={item.value}
                selected={localBackend === item.value}
                onClick={() => pickBackend(item.value)}
              >
                <BackendIcon icon={item.icon} />
                {item.label}
              </Chip>
            ))}
          </div>

          <div className="space-y-2">
            <Input
              value={localLabel}
              onChange={event => {
                setLocalLabel(event.target.value)
                setLocalSaved(false)
              }}
              placeholder="Profile name"
            />
            <Input
              value={localUrl}
              onChange={event => {
                setLocalUrl(event.target.value)
                setLocalSaved(false)
                setDiscoveredModels([])
                setSelectedModel(null)
              }}
              placeholder={selectedBackend.baseUrl}
              className="font-mono text-sm"
            />
            <div className="relative">
              <Input
                type={showLocalKey ? 'text' : 'password'}
                autoComplete="off"
                value={localKey}
                onChange={event => {
                  setLocalKey(event.target.value)
                  setLocalSaved(false)
                }}
                placeholder={
                  localBackend === 'ollama'
                    ? 'API key (optional)'
                    : 'API key (if required)'
                }
                className="pr-10"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute top-1/2 right-1 size-7 -translate-y-1/2"
                onClick={() => setShowLocalKey(open => !open)}
                aria-label={showLocalKey ? 'Hide API key' : 'Show API key'}
              >
                {showLocalKey ? (
                  <EyeOff className="size-4" />
                ) : (
                  <Eye className="size-4" />
                )}
              </Button>
            </div>
            <p className="text-muted-foreground text-[11px]">
              Suggested for {selectedBackend.label}: {selectedBackend.baseUrl}{' '}
              · discovers via {selectedBackend.hint}
            </p>
          </div>

          <div className="flex items-center justify-between gap-3">
            <Button
              type="button"
              variant="ghost"
              disabled={discoverBusy}
              onClick={() => void discoverLocal()}
            >
              {discoverBusy ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RefreshCw className="size-4" />
              )}
              Discover models
            </Button>
            <Button
              type="button"
              disabled={localBusy}
              onClick={() => void saveLocal()}
            >
              {localBusy ? (
                <Loader2 className="size-4 animate-spin" />
              ) : localSaved ? (
                <Check className="size-4" />
              ) : null}
              {localSaved ? 'Saved' : 'Save & use'}
            </Button>
          </div>

          {discoverError ? (
            <p className="text-destructive text-sm">{discoverError}</p>
          ) : null}

          {discoveredModels.length ? (
            <div className="space-y-2">
              <p className="text-muted-foreground text-xs">
                Pick a default model
                {discoverSource ? ` (${discoverSource})` : ''}:
              </p>
              <div className="max-h-40 space-y-1 overflow-y-auto pr-1">
                {discoveredModels.map(modelId => {
                  const selected = selectedModel === modelId
                  return (
                    <button
                      key={modelId}
                      type="button"
                      onClick={() => {
                        setSelectedModel(modelId)
                        setLocalSaved(false)
                      }}
                      className={cn(
                        'hover:bg-muted/50 flex w-full items-center rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                        selected
                          ? 'border-foreground bg-muted/40'
                          : 'border-border/60'
                      )}
                    >
                      <span className="min-w-0 flex-1 truncate font-mono text-xs">
                        {modelId}
                      </span>
                      {selected ? <Check className="size-3.5 shrink-0" /> : null}
                    </button>
                  )
                })}
              </div>
            </div>
          ) : null}
        </div>
      )}

      {error ? <p className="text-destructive text-sm">{error}</p> : null}
      {notice ? <p className="text-muted-foreground text-sm">{notice}</p> : null}
    </div>
  )
}
