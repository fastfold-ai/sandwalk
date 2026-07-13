import type {
  IntegrationSummary,
  SandboxProbeReport,
  SandboxSettings
} from '@sandwalk/agent-ui-core'
import { Check, HardDrive, Loader2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { ErrorPage } from '@/components/ErrorPage'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { cn } from '@/lib/utils'

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

const GPU_CLASSES: Array<{ id: string; label: string; detail: string }> = [
  { id: 'T4', label: 'T4', detail: 'Entry GPU · cost-efficient' },
  { id: 'L4', label: 'L4', detail: 'Efficient inference' },
  { id: 'A10', label: 'A10', detail: 'General purpose' },
  { id: 'L40S', label: 'L40S', detail: 'High memory / viz' },
  { id: 'A100', label: 'A100', detail: 'Training / large models' },
  { id: 'A100-40GB', label: 'A100 40GB', detail: '40GB HBM' },
  { id: 'A100-80GB', label: 'A100 80GB', detail: '80GB HBM' },
  { id: 'H100', label: 'H100', detail: 'Latest Hopper' },
  { id: 'H200', label: 'H200', detail: 'High-bandwidth HBM3e' },
  { id: 'B200', label: 'B200', detail: 'Blackwell' }
]

const CPU_IMAGE_PRESETS: Array<{ id: string; label: string; detail: string }> = [
  {
    id: 'debian_slim',
    label: 'Debian Slim',
    detail: 'Default lightweight Modal image'
  },
  {
    id: 'python:3.12-slim',
    label: 'Python 3.12 Slim',
    detail: 'Small CPU image for scripts'
  },
  {
    id: 'ubuntu:22.04',
    label: 'Ubuntu 22.04',
    detail: 'Common base for custom tooling'
  }
]

const GPU_IMAGE_PRESETS: Array<{ id: string; label: string; detail: string }> = [
  {
    id: 'debian_slim',
    label: 'Debian Slim + CUDA',
    detail: 'Modal default GPU base'
  },
  {
    id: 'pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime',
    label: 'PyTorch CUDA 12.4',
    detail: 'PyTorch GPU runtime'
  },
  {
    id: 'nvcr.io/nvidia/pytorch:24.02-py3',
    label: 'NGC PyTorch',
    detail: 'NVIDIA NGC container'
  }
]

function settingsToDraft(settings: SandboxSettings | null): Draft {
  const gpuClass = settings?.gpuClass?.trim() || 'T4'
  const knownGpu = GPU_CLASSES.some(item => item.id === gpuClass)
  return {
    backend: settings?.backend === 'modal' ? 'modal' : 'builtin',
    modalApp: settings?.modalApp ?? 'sandwalk',
    cpuImage: settings?.cpuImage?.trim() || 'debian_slim',
    gpuImage: settings?.gpuImage?.trim() || 'debian_slim',
    pipPackages:
      settings?.pipPackages ?? 'pandas,numpy,matplotlib,scipy,pillow',
    computeType: settings?.computeType === 'gpu' ? 'gpu' : 'cpu',
    gpuClass: knownGpu ? gpuClass : 'T4',
    cpuCores: String(settings?.cpuCores ?? 1),
    ramGb: String(settings?.ramGb ?? 4),
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

function NumberField({
  label,
  hint,
  value,
  min,
  max,
  step,
  disabled,
  onChange
}: {
  label: string
  hint?: string
  value: string
  min: number
  max: number
  step?: number
  disabled?: boolean
  onChange: (value: string) => void
}) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <Input
        type="number"
        min={min}
        max={max}
        step={step ?? 1}
        className="w-full"
        value={value}
        disabled={disabled}
        onChange={event => onChange(event.target.value)}
      />
      {hint ? (
        <p className="text-muted-foreground text-xs leading-relaxed">{hint}</p>
      ) : null}
    </label>
  )
}

function ChoiceCard({
  selected,
  disabled,
  title,
  detail,
  icon,
  onClick
}: {
  selected: boolean
  disabled?: boolean
  title: string
  detail: string
  icon?: ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'rounded-lg border px-3 py-2.5 text-left text-sm transition-colors',
        selected
          ? 'border-primary bg-muted/40 ring-primary/20 ring-2'
          : 'border-border hover:bg-muted/40',
        disabled && 'cursor-not-allowed opacity-60'
      )}
    >
      <div className="flex items-center gap-2 font-medium">
        {icon}
        <span>{title}</span>
      </div>
      <div className="text-muted-foreground mt-0.5 text-xs">{detail}</div>
    </button>
  )
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
  onRefreshIntegrations
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
  const modalSaveBlocked =
    draft.backend === 'modal' && (!modalReady || !probeOk)
  const imagePresets =
    draft.computeType === 'gpu' ? GPU_IMAGE_PRESETS : CPU_IMAGE_PRESETS
  const activeImage =
    draft.computeType === 'gpu' ? draft.gpuImage : draft.cpuImage

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
    // Keep Modal selection while parent sandboxSettings refresh (still builtin until Apply).
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
      await showDone('Tokens saved', 'Run a probe before enabling Modal.')
    } catch (err) {
      setOverlay(null)
      setError(err instanceof Error ? err.message : String(err))
      setErrorStack(err instanceof Error ? err.stack || null : null)
    } finally {
      setSavingTokens(false)
      // Clear after React has applied the sandboxSettings effect.
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
    if (!connected || busy || !dirty || unavailable || modalSaveBlocked) return
    setBusy(true)
    setError(null)
    setErrorStack(null)
    setOverlay({
      phase: 'working',
      message: 'Saving sandbox…',
      description: 'New sessions will use these settings.'
    })
    try {
      const next = await onUpdateSandboxSettings({
        backend: draft.backend,
        modalApp: draft.modalApp.trim() || 'sandwalk',
        cpuImage: draft.cpuImage.trim() || 'debian_slim',
        gpuImage: draft.gpuImage.trim() || 'debian_slim',
        pipPackages: draft.pipPackages.trim(),
        computeType: draft.computeType,
        gpuClass: draft.gpuClass.trim() || 'T4',
        cpuCores: clampNumber(draft.cpuCores, 0.25, 64, 1),
        ramGb: clampNumber(draft.ramGb, 0.5, 256, 4),
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
        'New sessions use this sandbox backend.'
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

  return (
    <ScrollArea className="flex-1">
      <BusyConfirmOverlay
        open={Boolean(overlay)}
        phase={overlay?.phase || 'working'}
        message={overlay?.message || ''}
        description={overlay?.description}
      />
      <div className="mx-auto max-w-3xl space-y-10 px-8 py-10">
        <div>
          <h2 className="text-2xl font-semibold">Sandbox</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Choose where the agent runs shell and filesystem tools. Domain tools
            and MCPs stay on this machine; Modal syncs the session workspace to
            a remote container.
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
          <div>
            <h3 className="text-base font-semibold">Backend</h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Built-in uses the local session workspace. Modal isolates{' '}
              <code className="text-xs">execute</code> and filesystem tools
              remotely.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <ChoiceCard
              selected={draft.backend === 'builtin'}
              disabled={formDisabled}
              title="Built-in"
              detail="Local FilesystemBackend (default)"
              icon={<HardDrive className="text-muted-foreground size-4" />}
              onClick={() =>
                setDraft(current => ({ ...current, backend: 'builtin' }))
              }
            />
            <ChoiceCard
              selected={draft.backend === 'modal'}
              disabled={formDisabled}
              title="Modal"
              detail="Remote ModalSandbox + workspace sync"
              icon={<ModalGlyph />}
              onClick={() =>
                setDraft(current => ({ ...current, backend: 'modal' }))
              }
            />
          </div>
        </section>

        {draft.backend === 'modal' ? (
          <>
            <section className="space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold">Modal credentials</h3>
                  <p className="text-muted-foreground mt-1 text-sm">
                    Same tokens as Integrations → Modal. Save them here, then
                    probe before enabling Modal.
                  </p>
                  {modalIntegration?.setupUrl ? (
                    <p className="text-muted-foreground mt-1 text-xs">
                      Get tokens at{' '}
                      <a
                        href={modalIntegration.setupUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="underline"
                      >
                        {modalIntegration.setupUrl}
                      </a>
                    </p>
                  ) : null}
                </div>
                <Link
                  to="/dashboard/integrations/modal"
                  className="text-muted-foreground hover:text-foreground shrink-0 text-xs underline underline-offset-4"
                >
                  Open Integrations
                </Link>
              </div>

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
                    formDisabled ||
                    savingTokens ||
                    !modalReady ||
                    !onProbeSandbox
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
              ) : modalReady ? (
                <p className="text-muted-foreground text-sm">
                  Run Test connection and wait for a healthy probe before saving
                  Modal as the backend.
                </p>
              ) : (
                <p className="text-amber-800 text-sm dark:text-amber-200">
                  Modal tokens are required before you can probe or save Modal
                  as the backend.
                </p>
              )}
            </section>

            <section className="space-y-4">
              <div>
                <h3 className="text-base font-semibold">Modal app</h3>
                <p className="text-muted-foreground mt-1 text-sm">
                  App name used with{' '}
                  <code className="text-xs">modal.App.lookup</code>.
                </p>
              </div>
              <label className="space-y-1.5 text-sm">
                <span className="text-muted-foreground">App name</span>
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
            </section>

            <section className="space-y-4">
              <div>
                <h3 className="text-base font-semibold">Compute</h3>
                <p className="text-muted-foreground mt-1 text-sm">
                  CPU or GPU for new Modal sandboxes. GPU class matches Modal’s
                  supported accelerator list.
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <ChoiceCard
                  selected={draft.computeType === 'cpu'}
                  disabled={formDisabled}
                  title="CPU"
                  detail="General scripts and data analysis"
                  onClick={() =>
                    setDraft(current => ({ ...current, computeType: 'cpu' }))
                  }
                />
                <ChoiceCard
                  selected={draft.computeType === 'gpu'}
                  disabled={formDisabled}
                  title="GPU"
                  detail="CUDA workloads and heavy models"
                  icon={
                    <img
                      src="/nvidia.svg"
                      alt=""
                      className="size-4 shrink-0 object-contain dark:invert"
                    />
                  }
                  onClick={() =>
                    setDraft(current => ({ ...current, computeType: 'gpu' }))
                  }
                />
              </div>

              {draft.computeType === 'gpu' ? (
                <div className="space-y-2">
                  <div className="text-muted-foreground text-sm">GPU class</div>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {GPU_CLASSES.map(option => (
                      <ChoiceCard
                        key={option.id}
                        selected={draft.gpuClass === option.id}
                        disabled={formDisabled}
                        title={option.label}
                        detail={option.detail}
                        onClick={() =>
                          setDraft(current => ({
                            ...current,
                            gpuClass: option.id
                          }))
                        }
                      />
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="grid gap-4 sm:grid-cols-2">
                <NumberField
                  label="CPU cores"
                  hint="0.25–64 (Modal cpu)"
                  value={draft.cpuCores}
                  min={0.25}
                  max={64}
                  step={0.25}
                  disabled={formDisabled}
                  onChange={value =>
                    setDraft(current => ({ ...current, cpuCores: value }))
                  }
                />
                <NumberField
                  label="RAM (GB)"
                  hint="0.5–256"
                  value={draft.ramGb}
                  min={0.5}
                  max={256}
                  step={0.5}
                  disabled={formDisabled}
                  onChange={value =>
                    setDraft(current => ({ ...current, ramGb: value }))
                  }
                />
              </div>
              <NumberField
                label="Idle TTL (seconds)"
                hint="Terminate after this many idle seconds (60–86400)."
                value={draft.idleTtlSeconds}
                min={60}
                max={86400}
                step={60}
                disabled={formDisabled}
                onChange={value =>
                  setDraft(current => ({ ...current, idleTtlSeconds: value }))
                }
              />
            </section>

            <section className="space-y-4">
              <div>
                <h3 className="text-base font-semibold">
                  {draft.computeType === 'gpu' ? 'GPU image' : 'CPU image'}
                </h3>
                <p className="text-muted-foreground mt-1 text-sm">
                  Container image for sandbox{' '}
                  <code className="text-xs">execute</code>. Pick a preset or
                  enter a custom image.
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {imagePresets.map(option => (
                  <ChoiceCard
                    key={option.id}
                    selected={activeImage === option.id}
                    disabled={formDisabled}
                    title={option.label}
                    detail={option.detail}
                    onClick={() =>
                      setDraft(current =>
                        current.computeType === 'gpu'
                          ? { ...current, gpuImage: option.id }
                          : { ...current, cpuImage: option.id }
                      )
                    }
                  />
                ))}
              </div>
              <label className="space-y-1.5 text-sm">
                <span className="text-muted-foreground">Custom image</span>
                <Input
                  value={activeImage}
                  disabled={formDisabled}
                  onChange={event => {
                    const value = event.target.value
                    setDraft(current =>
                      current.computeType === 'gpu'
                        ? { ...current, gpuImage: value }
                        : { ...current, cpuImage: value }
                    )
                  }}
                />
              </label>
            </section>

            <section className="space-y-4">
              <div>
                <h3 className="text-base font-semibold">Pip packages</h3>
                <p className="text-muted-foreground mt-1 text-sm">
                  Installed into the Modal image for sandbox execute / skill
                  scripts. Host Environment packages still serve domain tools.
                </p>
              </div>
              <Input
                value={draft.pipPackages}
                disabled={formDisabled}
                onChange={event =>
                  setDraft(current => ({
                    ...current,
                    pipPackages: event.target.value
                  }))
                }
              />
            </section>
          </>
        ) : null}

        {!loading && !unavailable ? (
          <div className="flex flex-col items-end gap-2 pt-2">
            {modalSaveBlocked ? (
              <p className="text-muted-foreground text-xs">
                {!modalReady
                  ? 'Save Modal tokens and run a healthy probe to enable Save.'
                  : 'Run Test connection until the probe is healthy to enable Save.'}
              </p>
            ) : null}
            <Button
              size="sm"
              disabled={formDisabled || !dirty || modalSaveBlocked}
              onClick={() => void apply()}
            >
              {busy && overlay?.message.startsWith('Saving') ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Check />
              )}
              Save
            </Button>
          </div>
        ) : null}
      </div>
    </ScrollArea>
  )
}
