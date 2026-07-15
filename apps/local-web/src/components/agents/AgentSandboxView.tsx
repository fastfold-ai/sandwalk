import type {
  IntegrationSummary,
  SandboxProbeReport,
  SandboxSettings
} from '@sandwalk/agent-ui-core'
import { ArrowLeft, Check, CircleCheck, Loader2, RotateCcw } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { ErrorPage } from '@/components/ErrorPage'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'

type ImageDraft = {
  modalApp: string
  idleTtlSeconds: string
  cpuImage: string
  gpuImage: string
  pipPackages: string
}

const DEFAULT_CPU_IMAGE = 'python:3.12-slim'
const DEFAULT_GPU_IMAGE = 'pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime'
const DEFAULT_PIP =
  'pandas, numpy, scipy, scikit-learn, matplotlib, seaborn'
const DEFAULT_MODAL_APP = 'sandwalk'
const DEFAULT_IDLE_TTL = '600'

function settingsToImageDraft(settings: SandboxSettings | null): ImageDraft {
  return {
    modalApp: settings?.modalApp ?? DEFAULT_MODAL_APP,
    idleTtlSeconds: String(settings?.idleTtlSeconds ?? DEFAULT_IDLE_TTL),
    cpuImage: settings?.cpuImage?.trim() || DEFAULT_CPU_IMAGE,
    gpuImage: settings?.gpuImage?.trim() || DEFAULT_GPU_IMAGE,
    pipPackages: settings?.pipPackages ?? DEFAULT_PIP
  }
}

function defaultImageDraft(): ImageDraft {
  return {
    modalApp: DEFAULT_MODAL_APP,
    idleTtlSeconds: DEFAULT_IDLE_TTL,
    cpuImage: DEFAULT_CPU_IMAGE,
    gpuImage: DEFAULT_GPU_IMAGE,
    pipPackages: DEFAULT_PIP
  }
}

function clampNumber(
  value: string,
  minimum: number,
  maximum: number,
  fallback: number
) {
  const n = Number(value)
  if (!Number.isFinite(n)) return fallback
  return Math.max(minimum, Math.min(maximum, n))
}

export function AgentSandboxView({
  connected,
  sandboxSettings,
  modalIntegration,
  onLoadSandboxSettings,
  onUpdateSandboxSettings,
  onProbeSandbox,
  onSaveModalIntegration,
  onRemoveModalIntegration,
  onRefreshIntegrations,
  onBack,
  embedded = false,
  bare = false
}: {
  connected: boolean
  sandboxSettings: SandboxSettings | null
  modalIntegration?: IntegrationSummary | null
  onLoadSandboxSettings?: () => Promise<SandboxSettings | null>
  onUpdateSandboxSettings: (
    changes: Partial<SandboxSettings>
  ) => Promise<SandboxSettings>
  onProbeSandbox?: () => Promise<SandboxProbeReport>
  onSaveModalIntegration?: (
    values: Record<string, string>
  ) => Promise<IntegrationSummary>
  onRemoveModalIntegration?: () => Promise<void>
  onRefreshIntegrations?: () => Promise<void>
  onBack?: () => void
  embedded?: boolean
  /** Skip page chrome / ScrollArea (e.g. onboarding embed). */
  bare?: boolean
}) {
  const [draft, setDraft] = useState<ImageDraft>(() =>
    settingsToImageDraft(sandboxSettings)
  )
  const [saved, setSaved] = useState<ImageDraft>(() =>
    settingsToImageDraft(sandboxSettings)
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorStack, setErrorStack] = useState<string | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  const [probeOk, setProbeOk] = useState(false)
  const [probeDetail, setProbeDetail] = useState<string | null>(null)
  const [tokenDrafts, setTokenDrafts] = useState<Record<string, string>>({})
  const [savingTokens, setSavingTokens] = useState(false)
  const [overlay, setOverlay] = useState<{
    phase: 'working' | 'done'
    message: string
    description?: string
  } | null>(null)
  const savedRef = useRef(saved)
  savedRef.current = saved
  const preserveDraftRef = useRef(false)
  const onLoadSandboxSettingsRef = useRef(onLoadSandboxSettings)
  onLoadSandboxSettingsRef.current = onLoadSandboxSettings

  useEffect(() => {
    if (!sandboxSettings) return
    const next = settingsToImageDraft(sandboxSettings)
    setSaved(next)
    setDraft(prev => {
      if (preserveDraftRef.current) return prev
      const dirty =
        JSON.stringify(prev) !== JSON.stringify(savedRef.current)
      return dirty ? prev : next
    })
    setUnavailable(false)
  }, [sandboxSettings])

  useEffect(() => {
    if (sandboxSettings || !connected || !onLoadSandboxSettingsRef.current) {
      return
    }
    let cancelled = false
    // Load in the background — form is already visible with defaults.
    void onLoadSandboxSettingsRef.current()
      .then(next => {
        if (cancelled) return
        if (!next) {
          setUnavailable(true)
          setError(
            'FastFold Agent API 404: Not Found [GET /v1/settings/sandbox]'
          )
          setErrorStack(null)
        }
      })
      .catch(err => {
        if (cancelled) return
        setUnavailable(true)
        setError(err instanceof Error ? err.message : String(err))
        setErrorStack(err instanceof Error ? err.stack || null : null)
      })
    return () => {
      cancelled = true
    }
  }, [connected, sandboxSettings])

  const dirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(saved),
    [draft, saved]
  )
  const atDefaults = useMemo(
    () => JSON.stringify(draft) === JSON.stringify(defaultImageDraft()),
    [draft]
  )

  const modalReady = Boolean(
    modalIntegration?.configured ?? sandboxSettings?.modalConfigured
  )
  const modalFields = modalIntegration?.fields ?? [
    {
      envVar: 'MODAL_TOKEN_ID',
      label: 'Modal Token ID',
      isSecret: false,
      configured: false,
      source: 'none' as const,
      maskedPreview: null
    },
    {
      envVar: 'MODAL_TOKEN_SECRET',
      label: 'Modal Token Secret',
      isSecret: true,
      configured: false,
      source: 'none' as const,
      maskedPreview: null
    }
  ]
  const tokenDirty = Object.values(tokenDrafts).some(value => value.trim())
  const formDisabled = !connected || busy || unavailable

  async function showDone(message: string, description?: string) {
    setOverlay({ phase: 'done', message, description })
    await new Promise(resolve => setTimeout(resolve, 900))
    setOverlay(null)
  }

  async function runProbe() {
    if (!onProbeSandbox || !connected || busy || !modalReady) return
    setBusy(true)
    setError(null)
    setErrorStack(null)
    setProbeDetail(null)
    setOverlay({
      phase: 'working',
      message: 'Probing Modal…',
      description:
        'Creating a sandbox, syncing files, and running a health check.'
    })
    try {
      const report = await onProbeSandbox()
      setProbeOk(report.ok)
      const failed = report.steps.find(step => !step.ok)
      setProbeDetail(
        report.ok
          ? 'Modal sandbox probe passed.'
          : failed?.detail || 'Modal sandbox probe failed.'
      )
      if (!report.ok) {
        setOverlay(null)
        return
      }
      await showDone('Probe healthy', 'Modal sandbox is ready to use.')
    } catch (err) {
      setProbeOk(false)
      setOverlay(null)
      const message = err instanceof Error ? err.message : String(err)
      const missingProbe =
        /\/v1\/settings\/sandbox\/probe/i.test(message) &&
        /\b404\b|not found/i.test(message)
      setProbeDetail(
        missingProbe
          ? 'Probe endpoint missing on this agent server. Restart sandwalk / `sandwalk serve` after updating the CLI, then retry.'
          : message
      )
    } finally {
      setBusy(false)
    }
  }

  async function saveModalTokens() {
    if (!onSaveModalIntegration || !tokenDirty || savingTokens) return
    setSavingTokens(true)
    setError(null)
    setErrorStack(null)
    setOverlay({
      phase: 'working',
      message: 'Saving Modal tokens…'
    })
    preserveDraftRef.current = true
    try {
      const values = Object.fromEntries(
        Object.entries(tokenDrafts)
          .map(([key, value]) => [key, value.trim()])
          .filter(([, value]) => Boolean(value))
      )
      await onSaveModalIntegration(values)
      setTokenDrafts({})
      setProbeOk(false)
      setProbeDetail(null)
      await onRefreshIntegrations?.()
      await onLoadSandboxSettings?.()
      await showDone('Tokens saved', 'Run Test connection to verify Modal.')
    } catch (err) {
      setOverlay(null)
      setError(err instanceof Error ? err.message : String(err))
      setErrorStack(err instanceof Error ? err.stack || null : null)
    } finally {
      setSavingTokens(false)
      queueMicrotask(() => {
        preserveDraftRef.current = false
      })
    }
  }

  async function clearModalTokens() {
    if (!onRemoveModalIntegration || savingTokens) return
    setSavingTokens(true)
    setError(null)
    preserveDraftRef.current = true
    try {
      await onRemoveModalIntegration()
      setProbeOk(false)
      setProbeDetail(null)
      setTokenDrafts({})
      await onRefreshIntegrations?.()
      await onLoadSandboxSettings?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setErrorStack(err instanceof Error ? err.stack || null : null)
    } finally {
      setSavingTokens(false)
      queueMicrotask(() => {
        preserveDraftRef.current = false
      })
    }
  }

  async function apply(nextDraft: ImageDraft = draft) {
    if (!connected || busy || unavailable) return
    setBusy(true)
    setError(null)
    setErrorStack(null)
    setOverlay({
      phase: 'working',
      message: 'Saving sandbox…',
      description: 'Used when a chat enables Modal Sandbox.'
    })
    try {
      const next = await onUpdateSandboxSettings({
        modalApp: nextDraft.modalApp.trim() || DEFAULT_MODAL_APP,
        idleTtlSeconds: Math.round(
          clampNumber(
            nextDraft.idleTtlSeconds,
            60,
            86400,
            Number(DEFAULT_IDLE_TTL)
          )
        ),
        cpuImage: nextDraft.cpuImage.trim() || DEFAULT_CPU_IMAGE,
        gpuImage: nextDraft.gpuImage.trim() || DEFAULT_GPU_IMAGE,
        pipPackages: nextDraft.pipPackages.trim()
      })
      const normalized = settingsToImageDraft(next)
      setDraft(normalized)
      setSaved(normalized)
      setUnavailable(false)
      await showDone('Sandbox saved')
    } catch (err) {
      setOverlay(null)
      setError(err instanceof Error ? err.message : String(err))
      setErrorStack(err instanceof Error ? err.stack || null : null)
    } finally {
      setBusy(false)
    }
  }

  function restoreDefaults() {
    setDraft(defaultImageDraft())
  }

  function retryLoad() {
    if (!onLoadSandboxSettings) return
    setError(null)
    setErrorStack(null)
    setUnavailable(false)
    void onLoadSandboxSettings()
      .then(next => {
        if (!next) {
          setUnavailable(true)
          setError(
            'FastFold Agent API 404: Not Found [GET /v1/settings/sandbox]'
          )
        }
      })
      .catch(err => {
        setUnavailable(true)
        setError(err instanceof Error ? err.message : String(err))
        setErrorStack(err instanceof Error ? err.stack || null : null)
      })
  }

  const body = (
    <>
      <BusyConfirmOverlay
        open={Boolean(overlay)}
        phase={overlay?.phase || 'working'}
        message={overlay?.message || ''}
        description={overlay?.description}
      />
      <div
        className={
          bare
            ? 'space-y-6'
            : 'mx-auto max-w-3xl space-y-8 px-8 py-10'
        }
      >
        {!bare && onBack ? (
          <div className="flex items-center gap-2 text-sm">
            <button
              type="button"
              onClick={onBack}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </button>
            <span className="text-muted-foreground/40">/</span>
            <button
              type="button"
              onClick={onBack}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              Sandbox
            </button>
          </div>
        ) : null}

        {!bare && !embedded ? (
          <div>
            <h2 className="text-2xl font-semibold">Modal Sandbox</h2>
            <p className="text-muted-foreground mt-2 text-sm">
              Credentials, app defaults, and base images. Compute is chosen per
              chat.
            </p>
          </div>
        ) : null}
        {!bare && embedded ? (
          <div>
            <h2 className="text-lg font-semibold">Modal Sandbox</h2>
          </div>
        ) : null}

        {error ? (
          <ErrorPage
            variant="inline"
            className="mt-0"
            error={
              errorStack
                ? Object.assign(new Error(error), { stack: errorStack })
                : error
            }
            onRetry={onLoadSandboxSettings ? retryLoad : undefined}
            retryLabel="Retry load"
          />
        ) : null}

        {unavailable && !error ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-900 dark:text-amber-200">
            This agent server does not expose{' '}
            <code className="text-xs">/v1/settings/sandbox</code> yet. Restart
            sandwalk / the agent server after updating the CLI, then reload this
            page.
          </div>
        ) : null}

        {!unavailable ? (
          <>
            <section className="space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold">Modal credentials</h3>
                  <p className="text-muted-foreground mt-1 text-sm">
                    Required before chats can start Modal Sandbox.
                  </p>
                </div>
                <Link
                  to="/dashboard/integrations/modal"
                  className="text-muted-foreground hover:text-foreground shrink-0 text-xs underline underline-offset-4"
                >
                  Open Integrations
                </Link>
              </div>

              {!modalReady ? (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-900 dark:text-amber-200">
                  Modal is not set up.{' '}
                  <Link
                    to="/dashboard/integrations/modal"
                    className="font-medium underline underline-offset-2"
                  >
                    Set up Modal
                  </Link>{' '}
                  to enable Modal Sandbox in chats.
                </div>
              ) : null}

              <div className="overflow-hidden rounded-md border">
                <div className="bg-muted/20 text-muted-foreground grid grid-cols-[minmax(9.5rem,0.9fr)_minmax(0,1.4fr)_minmax(7.5rem,0.85fr)_4.5rem] items-center gap-3 border-b px-3 py-2 text-xs">
                  <span>Key</span>
                  <span>Value</span>
                  <span>Status</span>
                  <span className="text-right">Action</span>
                </div>
                {modalFields.map(field => (
                  <div
                    key={field.envVar}
                    className="grid grid-cols-[minmax(9.5rem,0.9fr)_minmax(0,1.4fr)_minmax(7.5rem,0.85fr)_4.5rem] items-center gap-3 border-b px-3 py-3 last:border-b-0"
                  >
                    <div className="min-w-0">
                      <strong className="block truncate text-sm">
                        {field.envVar}
                      </strong>
                      <span className="text-muted-foreground block truncate text-xs">
                        {field.label}
                      </span>
                    </div>
                    <Input
                      type={field.isSecret ? 'password' : 'text'}
                      value={tokenDrafts[field.envVar] || ''}
                      disabled={formDisabled || savingTokens}
                      className="min-w-0 w-full"
                      onChange={event => {
                        const value = event.target.value
                        setTokenDrafts(current => ({
                          ...current,
                          [field.envVar]: value
                        }))
                        setProbeOk(false)
                        setProbeDetail(null)
                      }}
                      placeholder={`Enter ${field.envVar}`}
                    />
                    <span className="text-muted-foreground min-w-0 truncate text-xs">
                      {field.configured
                        ? `Configured · ${field.maskedPreview || field.source}`
                        : 'Not configured'}
                    </span>
                    {field.configured ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive justify-self-end"
                        disabled={formDisabled || savingTokens}
                        onClick={() => void clearModalTokens()}
                      >
                        Remove
                      </Button>
                    ) : (
                      <span className="text-muted-foreground justify-self-end px-1">
                        -
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {probeOk ? (
                <p className="text-sm text-emerald-700 dark:text-emerald-400">
                  {probeDetail || 'Probe healthy.'}
                </p>
              ) : probeDetail ? (
                <p className="text-muted-foreground text-sm">{probeDetail}</p>
              ) : null}

              <div className="flex flex-wrap items-center justify-end gap-2">
                <Button
                  variant="secondary"
                  disabled={
                    formDisabled ||
                    savingTokens ||
                    !modalReady ||
                    !onProbeSandbox
                  }
                  onClick={() => void runProbe()}
                >
                  {busy && overlay?.message.startsWith('Probing') ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <CircleCheck className="size-4" />
                  )}
                  Test API Key
                </Button>
                <Button
                  disabled={
                    formDisabled ||
                    savingTokens ||
                    !tokenDirty ||
                    !onSaveModalIntegration
                  }
                  onClick={() => void saveModalTokens()}
                >
                  {savingTokens ? <Loader2 className="animate-spin" /> : null}
                  Save Overrides
                </Button>
              </div>
            </section>

            <section className="space-y-4">
              <h3 className="text-base font-semibold">Sandbox settings</h3>

              <label className="space-y-1.5 text-sm">
                <span className="text-muted-foreground text-xs">App name</span>
                <Input
                  value={draft.modalApp}
                  disabled={formDisabled}
                  placeholder={DEFAULT_MODAL_APP}
                  onChange={event =>
                    setDraft(current => ({
                      ...current,
                      modalApp: event.target.value
                    }))
                  }
                />
              </label>

              <label className="space-y-1.5 text-sm">
                <span className="text-muted-foreground text-xs">
                  Idle TTL (seconds)
                </span>
                <Input
                  type="number"
                  min={60}
                  max={86400}
                  step={60}
                  value={draft.idleTtlSeconds}
                  disabled={formDisabled}
                  onChange={event =>
                    setDraft(current => ({
                      ...current,
                      idleTtlSeconds: event.target.value
                    }))
                  }
                />
              </label>

              <label className="space-y-1.5 text-sm">
                <span className="text-muted-foreground text-xs">
                  CPU base image
                </span>
                <Input
                  value={draft.cpuImage}
                  disabled={formDisabled}
                  placeholder={DEFAULT_CPU_IMAGE}
                  className="font-mono text-xs"
                  onChange={event =>
                    setDraft(current => ({
                      ...current,
                      cpuImage: event.target.value
                    }))
                  }
                />
              </label>

              <label className="space-y-1.5 text-sm">
                <span className="text-muted-foreground text-xs">
                  GPU base image
                </span>
                <Input
                  value={draft.gpuImage}
                  disabled={formDisabled}
                  placeholder={DEFAULT_GPU_IMAGE}
                  className="font-mono text-xs"
                  onChange={event =>
                    setDraft(current => ({
                      ...current,
                      gpuImage: event.target.value
                    }))
                  }
                />
              </label>

              <label className="space-y-1.5 text-sm">
                <span className="text-muted-foreground text-xs">
                  Default pip installs
                </span>
                <Input
                  value={draft.pipPackages}
                  disabled={formDisabled}
                  placeholder={DEFAULT_PIP}
                  className="text-xs"
                  onChange={event =>
                    setDraft(current => ({
                      ...current,
                      pipPackages: event.target.value
                    }))
                  }
                />
              </label>

              <div className="flex flex-wrap items-center justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={formDisabled || atDefaults}
                  onClick={restoreDefaults}
                >
                  <RotateCcw className="size-3.5" />
                  Restore to defaults
                </Button>
                <Button
                  size="sm"
                  disabled={formDisabled || !dirty}
                  onClick={() => void apply()}
                >
                  {busy && overlay?.message.startsWith('Saving') ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <Check />
                  )}
                  Save settings
                </Button>
              </div>
            </section>
          </>
        ) : null}
      </div>
    </>
  )

  if (bare) return body
  return <ScrollArea className="flex-1">{body}</ScrollArea>
}
