import type {
  IntegrationSummary,
  SandboxProbeReport,
  SandboxSettings
} from '@sandwalk/agent-ui-core'
import { ArrowLeft, Check, Loader2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { ErrorPage } from '@/components/ErrorPage'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { cn } from '@/lib/utils'
import {
  CPU_PRESETS,
  DEFAULT_CPU_PRESET,
  DEFAULT_GPU_PRESET,
  GPU_PRESETS,
  matchCpuPresetId,
  matchGpuPreset
} from '@/lib/sandbox-presets'

type Draft = {
  backend: 'builtin' | 'modal'
  modalApp: string
  cpuImage: string
  gpuImage: string
  pipPackages: string
  computeType: 'cpu' | 'gpu'
  gpuClass: string
  cpuCores: string
  ramGb: string
  idleTtlSeconds: string
}

const DEFAULT_CPU_IMAGE = 'debian_slim'
const DEFAULT_GPU_IMAGE = 'debian_slim'
const DEFAULT_PIP =
  'pandas, numpy, scipy, scikit-learn, matplotlib, seaborn'

const selectClassName =
  'border-input bg-background h-9 w-full rounded-md border px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60'

function settingsToDraft(settings: SandboxSettings | null): Draft {
  const gpuClass = settings?.gpuClass?.trim() || DEFAULT_GPU_PRESET.gpu
  const knownGpu = GPU_PRESETS.some(item => item.gpu === gpuClass)
  return {
    backend: settings?.backend === 'modal' ? 'modal' : 'builtin',
    modalApp: settings?.modalApp ?? 'sandwalk',
    cpuImage: settings?.cpuImage?.trim() || DEFAULT_CPU_IMAGE,
    gpuImage: settings?.gpuImage?.trim() || DEFAULT_GPU_IMAGE,
    pipPackages: settings?.pipPackages ?? DEFAULT_PIP,
    computeType: settings?.computeType === 'gpu' ? 'gpu' : 'cpu',
    gpuClass: knownGpu ? gpuClass : DEFAULT_GPU_PRESET.gpu,
    cpuCores: String(settings?.cpuCores ?? DEFAULT_CPU_PRESET.cpu),
    ramGb: String(settings?.ramGb ?? DEFAULT_CPU_PRESET.ram),
    idleTtlSeconds: String(settings?.idleTtlSeconds ?? 600)
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

function ModalGlyph({ className }: { className?: string }) {
  const icon = INTEGRATION_ICONS.modal
  return (
    <img
      src={icon.src}
      alt=""
      className={cn('size-4 shrink-0 rounded-sm object-contain', className)}
    />
  )
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
  onBack
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
}) {
  const [draft, setDraft] = useState<Draft>(() =>
    settingsToDraft(sandboxSettings)
  )
  const [saved, setSaved] = useState<Draft>(() =>
    settingsToDraft(sandboxSettings)
  )
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
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

  useEffect(() => {
    if (!sandboxSettings) return
    const next = settingsToDraft(sandboxSettings)
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
    if (sandboxSettings || !connected || !onLoadSandboxSettings) return
    let cancelled = false
    setLoading(true)
    void onLoadSandboxSettings()
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
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [connected, onLoadSandboxSettings, sandboxSettings])

  const dirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(saved),
    [draft, saved]
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
  const formDisabled = !connected || busy || unavailable || loading

  const cpuCoresNum = Number(draft.cpuCores)
  const ramGbNum = Number(draft.ramGb)
  const cpuPresetId = matchCpuPresetId(cpuCoresNum, ramGbNum)
  const selectedGpuPreset =
    matchGpuPreset(draft.gpuClass) ?? DEFAULT_GPU_PRESET

  const computeSummary =
    draft.computeType === 'gpu'
      ? `${selectedGpuPreset.gpu} · ${selectedGpuPreset.vram} GB VRAM · ${draft.cpuCores} CPU · ${draft.ramGb} GB RAM`
      : `${draft.cpuCores} CPU cores · ${draft.ramGb} GB RAM`

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
          ? 'Probe endpoint missing on this agent server. Restart Sandwalk / `sandwalk serve` after updating the CLI, then retry.'
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

  async function apply() {
    if (!connected || busy || !dirty || unavailable) return
    setBusy(true)
    setError(null)
    setErrorStack(null)
    setOverlay({
      phase: 'working',
      message: 'Saving sandbox…',
      description: 'Applied when a chat enables Modal Sandbox.'
    })
    try {
      const next = await onUpdateSandboxSettings({
        // Chats default to Local; this page configures Modal defaults only.
        backend: 'builtin',
        modalApp: draft.modalApp.trim() || 'sandwalk',
        cpuImage: draft.cpuImage.trim() || DEFAULT_CPU_IMAGE,
        gpuImage: draft.gpuImage.trim() || DEFAULT_GPU_IMAGE,
        pipPackages: draft.pipPackages.trim(),
        computeType: draft.computeType,
        gpuClass: draft.gpuClass.trim() || DEFAULT_GPU_PRESET.gpu,
        cpuCores: clampNumber(
          draft.cpuCores,
          0.25,
          64,
          DEFAULT_CPU_PRESET.cpu
        ),
        ramGb: clampNumber(draft.ramGb, 0.5, 256, DEFAULT_CPU_PRESET.ram),
        idleTtlSeconds: Math.round(
          clampNumber(draft.idleTtlSeconds, 60, 86400, 600)
        )
      })
      const normalized = settingsToDraft(next)
      setDraft(normalized)
      setSaved(normalized)
      setUnavailable(false)
      await showDone(
        'Sandbox saved',
        'Modal chats use these compute and image settings.'
      )
    } catch (err) {
      setOverlay(null)
      setError(err instanceof Error ? err.message : String(err))
      setErrorStack(err instanceof Error ? err.stack || null : null)
    } finally {
      setBusy(false)
    }
  }

  function retryLoad() {
    if (!onLoadSandboxSettings) return
    setError(null)
    setErrorStack(null)
    setUnavailable(false)
    setLoading(true)
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
      .finally(() => setLoading(false))
  }

  function selectCpuPreset(presetId: string) {
    const preset =
      CPU_PRESETS.find(item => item.id === presetId) ?? DEFAULT_CPU_PRESET
    setDraft(current => ({
      ...current,
      computeType: 'cpu',
      cpuCores: String(preset.cpu),
      ramGb: String(preset.ram)
    }))
  }

  function selectGpuPreset(gpu: string) {
    const preset = matchGpuPreset(gpu) ?? DEFAULT_GPU_PRESET
    setDraft(current => ({
      ...current,
      computeType: 'gpu',
      gpuClass: preset.gpu,
      cpuCores: String(preset.cpu),
      ramGb: String(preset.ram)
    }))
  }

  return (
    <ScrollArea className="flex-1">
      <BusyConfirmOverlay
        open={Boolean(overlay)}
        phase={overlay?.phase || 'working'}
        message={overlay?.message || ''}
        description={overlay?.description}
      />
      <div className="mx-auto max-w-4xl space-y-10 px-8 py-10">
        {onBack ? (
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
        <div>
          <h2 className="text-2xl font-semibold">Modal Sandbox</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Configure Modal Sandbox compute, images, and credentials. Chats
            default to Local Sandbox; enable Modal per chat in the composer.
          </p>
        </div>

        {loading ? (
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading sandbox settings…
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
            Sandwalk / the agent server after updating the CLI, then reload this
            page.
          </div>
        ) : null}

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
            <div className="bg-muted/20 text-muted-foreground grid grid-cols-[1.15fr_2fr_1.1fr] border-b px-3 py-2 text-xs">
              <span>Key</span>
              <span>Value</span>
              <span>Status</span>
            </div>
            {modalFields.map(field => (
              <div
                key={field.envVar}
                className="grid grid-cols-[1.15fr_2fr_1.1fr] items-center gap-3 border-b px-3 py-3 last:border-b-0"
              >
                <div>
                  <strong className="text-sm">{field.envVar}</strong>
                  <span className="text-muted-foreground block text-xs">
                    {field.label}
                  </span>
                </div>
                <Input
                  type={field.isSecret ? 'password' : 'text'}
                  value={tokenDrafts[field.envVar] || ''}
                  disabled={formDisabled || savingTokens}
                  onChange={event => {
                    const value = event.target.value
                    setTokenDrafts(current => ({
                      ...current,
                      [field.envVar]: value
                    }))
                    setProbeOk(false)
                    setProbeDetail(null)
                  }}
                  placeholder={
                    field.configured
                      ? field.maskedPreview || 'Configured'
                      : `Enter ${field.envVar}`
                  }
                />
                <span className="text-muted-foreground text-xs">
                  {field.configured
                    ? `Configured · ${field.maskedPreview || field.source}`
                    : 'Not configured'}
                </span>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2">
            {modalReady ? (
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive"
                disabled={formDisabled || savingTokens}
                onClick={() => void clearModalTokens()}
              >
                Remove tokens
              </Button>
            ) : null}
            <Button
              variant="secondary"
              size="sm"
              disabled={
                formDisabled || savingTokens || !modalReady || !onProbeSandbox
              }
              onClick={() => void runProbe()}
            >
              {busy && overlay?.message.startsWith('Probing') ? (
                <Loader2 className="animate-spin" />
              ) : null}
              Test connection
            </Button>
            <Button
              size="sm"
              disabled={
                formDisabled ||
                savingTokens ||
                !tokenDirty ||
                !onSaveModalIntegration
              }
              onClick={() => void saveModalTokens()}
            >
              {savingTokens ? <Loader2 className="animate-spin" /> : null}
              Save tokens
            </Button>
          </div>

          {probeOk ? (
            <p className="text-sm text-emerald-700 dark:text-emerald-400">
              {probeDetail || 'Probe healthy.'}
            </p>
          ) : probeDetail ? (
            <p className="text-sm text-amber-800 dark:text-amber-200">
              {probeDetail}
            </p>
          ) : null}
        </section>

        <div className="grid gap-8 sm:grid-cols-2">
          <section className="space-y-3">
            <div>
              <h3 className="text-base font-semibold">Modal compute</h3>
              <p className="text-muted-foreground mt-1 text-sm">
                Default compute profile for chats that enable Modal Sandbox.
              </p>
            </div>

            <div className="inline-flex rounded-lg border p-1">
              <button
                type="button"
                disabled={formDisabled}
                onClick={() => {
                  const preset =
                    CPU_PRESETS.find(item => item.id === cpuPresetId) ??
                    DEFAULT_CPU_PRESET
                  setDraft(current => ({
                    ...current,
                    computeType: 'cpu',
                    cpuCores: String(preset.cpu),
                    ramGb: String(preset.ram)
                  }))
                }}
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                  draft.computeType === 'cpu'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                  formDisabled && 'cursor-not-allowed opacity-60'
                )}
              >
                CPU
              </button>
              <button
                type="button"
                disabled={formDisabled}
                onClick={() => selectGpuPreset(selectedGpuPreset.gpu)}
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                  draft.computeType === 'gpu'
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                  formDisabled && 'cursor-not-allowed opacity-60'
                )}
              >
                GPU
              </button>
            </div>

            {draft.computeType === 'cpu' ? (
              <label className="space-y-1.5 text-sm">
                <span className="text-muted-foreground text-xs">
                  CPU preset
                </span>
                <select
                  className={selectClassName}
                  disabled={formDisabled}
                  value={cpuPresetId ?? 'custom'}
                  onChange={event => {
                    if (event.target.value === 'custom') return
                    selectCpuPreset(event.target.value)
                  }}
                >
                  {CPU_PRESETS.map(preset => (
                    <option key={preset.id} value={preset.id}>
                      {preset.label}
                    </option>
                  ))}
                  {cpuPresetId === null ? (
                    <option value="custom">
                      {draft.cpuCores} CPU cores · {draft.ramGb} GB RAM
                    </option>
                  ) : null}
                </select>
              </label>
            ) : (
              <label className="space-y-1.5 text-sm">
                <span className="text-muted-foreground text-xs">GPU model</span>
                <select
                  className={selectClassName}
                  disabled={formDisabled}
                  value={selectedGpuPreset.gpu}
                  onChange={event => selectGpuPreset(event.target.value)}
                >
                  {GPU_PRESETS.map(preset => (
                    <option key={preset.gpu} value={preset.gpu}>
                      {preset.label}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <div className="flex items-center gap-2 border-t pt-3 text-xs">
              <ModalGlyph />
              <span className="text-muted-foreground font-medium">Modal</span>
              <span className="text-muted-foreground ml-auto">
                {computeSummary}
              </span>
            </div>

            <label className="space-y-1.5 text-sm">
              <span className="text-muted-foreground text-xs">App name</span>
              <Input
                value={draft.modalApp}
                disabled={formDisabled}
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
              <p className="text-muted-foreground text-[11px]">
                Terminate after this many idle seconds (60–86400).
              </p>
            </label>
          </section>

          <section className="space-y-3">
            <div>
              <h3 className="text-base font-semibold">Sandbox base images</h3>
              <p className="text-muted-foreground mt-1 text-sm">
                Base images and pip packages for Modal sessions.{' '}
                <code className="text-xs">debian_slim</code> is Modal’s built-in
                image helper (valid). Docker refs like{' '}
                <code className="text-xs">python:3.12-slim</code> also work.
              </p>
            </div>

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
              <p className="text-muted-foreground text-[11px]">
                Comma-separated packages installed for every Modal sandbox.
              </p>
            </label>
          </section>
        </div>

        {!loading && !unavailable ? (
          <div className="flex flex-col items-end gap-2 pt-2">
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
        ) : null}
      </div>
    </ScrollArea>
  )
}
