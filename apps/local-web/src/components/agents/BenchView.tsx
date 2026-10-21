import type {
  BenchActiveStatus,
  BenchProgress,
  BenchQueueItem,
  BenchSuiteCard,
  LocalAgentClient
} from '@sandwalk/agent-local-client'
import type { RuntimeSettings, Specialist } from '@sandwalk/agent-ui-core'
import { Check, Copy, Download, ExternalLink, Gauge, Loader, Pause, Play, ScrollText, Terminal, Trash2, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { matchPath, useLocation, useNavigate } from 'react-router-dom'

import { BenchCompareView } from '@/components/agents/BenchCompareView'
import { BenchResultDetail } from '@/components/agents/BenchResultDetail'
import { BenchResultsList } from '@/components/agents/BenchResultsList'
import { ComposerModelPicker } from '@/components/agents/composer/ComposerModelPicker'
import { ComposerSpecialistPicker } from '@/components/agents/composer/ComposerSpecialistPicker'
import { composerModelOptionKey } from '@/components/agents/composer/useComposerModelPickerNav'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { copyText } from '@/lib/clipboard'
import {
  type ComposerModelOption,
  patchComposerModelEffort,
  toComposerModelOptions
} from '@/lib/composer-models'
import { isTauri, openDesktopServerSettings } from '@/lib/desktop'
import { cn } from '@/lib/utils'

type Tab = 'new' | 'results'

function formatBytes(n: number): string {
  let value = Math.max(0, n)
  for (const unit of ['B', 'KB', 'MB', 'GB'] as const) {
    if (value < 1024 || unit === 'GB') {
      return unit === 'B' ? `${Math.round(value)} ${unit}` : `${value.toFixed(1)} ${unit}`
    }
    value /= 1024
  }
  return `${n} B`
}

/** Map stable pack ids to Dashboard card titles. */
const PACK_DISPLAY_TITLES: Record<string, string> = {
  'bio-capybara-full': 'Bio-Capybara-full',
  // Legacy pack id (pre-rename).
  'skills-mcp-bakeoff': 'Bio-Capybara-full'
}

function suiteDisplayName(
  id: string | null | undefined,
  suites: BenchSuiteCard[]
): string {
  if (!id) return ''
  const fromCard = suites.find(
    card => card.id === id || card.packId === id
  )?.title
  return fromCard || PACK_DISPLAY_TITLES[id] || id
}

function jobBarPct(progress?: BenchProgress | null): number {
  if (!progress?.benchTotal || progress.benchTotal <= 0) return 0
  return Math.min(
    100,
    Math.round(((progress.benchCurrent || 0) / progress.benchTotal) * 100)
  )
}

function jobSuitesLabel(
  item: Pick<BenchQueueItem, 'suites'>,
  suites: BenchSuiteCard[]
): string {
  return (item.suites || [])
    .map(id => suiteDisplayName(id, suites))
    .filter(Boolean)
    .join(', ')
}

function formatInstallApiError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err)
  const start = raw.indexOf('{')
  const end = raw.lastIndexOf('}')
  if (start >= 0 && end > start) {
    try {
      const parsed = JSON.parse(raw.slice(start, end + 1)) as {
        detail?: unknown
        message?: string
      }
      const detail = parsed.detail
      if (typeof detail === 'string' && detail.trim()) return detail.trim()
      if (detail && typeof detail === 'object') {
        const msg = (detail as { message?: unknown }).message
        if (typeof msg === 'string' && msg.trim()) return msg.trim()
      }
      if (typeof parsed.message === 'string' && parsed.message.trim()) {
        return parsed.message.trim()
      }
    } catch {
      /* keep raw */
    }
  }
  return raw.replace(/^FastFold Agent API \d+:\s*/i, '').split(' [')[0] || raw
}

function openServerLogs() {
  if (isTauri()) {
    void openDesktopServerSettings()
    const link = document.createElement('a')
    link.href = 'sandwalk://settings/logs'
    link.click()
  }
}

function BenchLogsHint() {
  return (
    <p className="text-destructive/90 text-xs">
      {isTauri() ? (
        <button
          type="button"
          className="hover:text-destructive inline-flex items-center gap-1 underline-offset-2 hover:underline"
          onClick={openServerLogs}
        >
          <ScrollText className="size-3" />
          Open Sandwalk Settings → Logs
        </button>
      ) : (
        <>
          Check the terminal running{' '}
          <span className="font-mono">sandwalk serve</span>.
        </>
      )}
    </p>
  )
}

function installButtonLabel(card: BenchSuiteCard, installing: boolean): string {
  if (installing) {
    // Server already formats "12.4 MB / 48 MB · 35.6 MB left · 26%" or
    // "1,200 / 14,042 questions · 12,842 left · 9%".
    return card.installProgress?.trim() || 'Installing…'
  }
  if (card.requiresHfToken && !card.hfTokenConfigured) {
    return 'Hugging Face required'
  }
  if (card.installError) return 'Retry install'
  return 'Install'
}

function sampleChoicesFor(card: BenchSuiteCard): number[] {
  const sizes = (card.sampleSizes || []).filter(
    n => !card.questionCount || n <= card.questionCount
  )
  if (sizes.length > 0) return sizes
  if (card.defaultSampleSize) return [card.defaultSampleSize]
  return []
}

/** Prefer the smallest offered sample size for first-time selection. */
function minSampleSize(card: BenchSuiteCard): number | null {
  const choices = sampleChoicesFor(card)
  if (!choices.length) return card.defaultSampleSize ?? null
  return Math.min(...choices)
}

export function BenchView({
  client,
  runtimeSettings,
  setRuntimeSettings
}: {
  client: LocalAgentClient
  runtimeSettings: RuntimeSettings | null
  setRuntimeSettings: (
    next:
      | RuntimeSettings
      | null
      | ((prev: RuntimeSettings | null) => RuntimeSettings | null)
  ) => void
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const isComparePath = location.pathname === '/dashboard/bench/compare'
  const detailMatch = isComparePath
    ? null
    : matchPath('/dashboard/bench/:runId', location.pathname)
  const detailRunId = detailMatch?.params.runId || null
  const [tab, setTab] = useState<Tab>('new')
  const [suites, setSuites] = useState<BenchSuiteCard[]>([])
  /** Suite ids currently checked for the next run. */
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  /** Sample sizes kept across select/deselect so re-check restores the choice. */
  const [sampleBySuite, setSampleBySuite] = useState<
    Record<string, number | null>
  >({})
  const [modelOptions, setModelOptions] = useState<ComposerModelOption[]>([])
  const [compareModels, setCompareModels] = useState<ComposerModelOption[]>([])
  const [specialists, setSpecialists] = useState<Specialist[]>([])
  const [specialistId, setSpecialistId] = useState<string | null>(null)
  const [active, setActive] = useState<BenchActiveStatus | null>(null)
  const [resultsTotal, setResultsTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [spawning, setSpawning] = useState(false)
  const [concurrency, setConcurrency] = useState(1)
  const [parallelRuns, setParallelRuns] = useState(4)
  const [cleanupSessions, setCleanupSessions] = useState(false)
  const [startingInstallId, setStartingInstallId] = useState<string | null>(
    null
  )
  const [cliMenuOpen, setCliMenuOpen] = useState(false)
  const [copiedCli, setCopiedCli] = useState(false)
  const [removingId, setRemovingId] = useState<string | null>(null)
  const [confirmRemoveId, setConfirmRemoveId] = useState<string | null>(null)
  const [brokenAvatars, setBrokenAvatars] = useState<Set<string>>(
    () => new Set()
  )
  const [resumingId, setResumingId] = useState<string | null>(null)
  const wasBusyRef = useRef(false)
  const prevOverlayRef = useRef(false)
  const cliCloseTimerRef = useRef<number | null>(null)

  const openCliMenu = () => {
    if (cliCloseTimerRef.current != null) {
      window.clearTimeout(cliCloseTimerRef.current)
      cliCloseTimerRef.current = null
    }
    setCliMenuOpen(true)
  }

  const scheduleCloseCliMenu = () => {
    if (cliCloseTimerRef.current != null) {
      window.clearTimeout(cliCloseTimerRef.current)
    }
    cliCloseTimerRef.current = window.setTimeout(() => {
      setCliMenuOpen(false)
      setCopiedCli(false)
      cliCloseTimerRef.current = null
    }, 160)
  }

  // After leaving a result detail / compare URL, show the Results tab.
  useEffect(() => {
    const overlay = Boolean(detailRunId) || isComparePath
    if (prevOverlayRef.current && !overlay) {
      setTab('results')
    }
    prevOverlayRef.current = overlay
  }, [detailRunId, isComparePath])

  const loadCatalog = useCallback(async () => {
    try {
      const [catalog, models, profiles, specialistRows] = await Promise.all([
        client.getBenchCatalog(),
        client.listModels({ enabledOnly: true, discover: true }).catch(() => []),
        client.listModelProfiles().catch(() => []),
        client.listSpecialists().catch(() => [])
      ])
      const backendsByProfileId = Object.fromEntries(
        (profiles || []).map(profile => [profile.id, profile.backend])
      )
      setSuites(catalog.suites)
      setSpecialists((specialistRows || []).filter(row => row.enabled !== false))
      setModelOptions(
        toComposerModelOptions(
          (models || []).map(model => ({
            ...model,
            backend:
              model.backend ??
              (model.profileId
                ? backendsByProfileId[model.profileId] || null
                : null)
          }))
        )
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load suites')
    }
  }, [client])

  const loadResults = useCallback(async () => {
    try {
      const page = await client.listBenchResults({ limit: 1 })
      setResultsTotal(page.total)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load results')
    }
  }, [client])

  const loadActive = useCallback(async () => {
    try {
      const status = await client.getBenchActive()
      setActive(status)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load bench')
    }
  }, [client])

  const loadStatus = useCallback(async () => {
    await Promise.all([loadResults(), loadActive()])
  }, [loadActive, loadResults])

  useEffect(() => {
    void loadCatalog()
    void loadStatus()
  }, [loadCatalog, loadStatus])

  // Detail unmounts the list UI but this view stays mounted. Refresh when
  // coming back so a retry started on the detail page is not still Interrupted.
  const prevDetailRunId = useRef<string | null>(null)
  useEffect(() => {
    const prev = prevDetailRunId.current
    prevDetailRunId.current = detailRunId
    if (prev && !detailRunId) {
      void loadStatus()
    }
  }, [detailRunId, loadStatus])

  const inflightJobs: BenchQueueItem[] = active?.inflight?.length
    ? active.inflight
    : active?.running && active.currentRunId
      ? [
          {
            runId: active.currentRunId,
            modelId: active.currentModel || '',
            suites: [],
            status: 'running',
            lastProgress: active.lastProgress
          }
        ]
      : []
  const queuedJobs = active?.queue ?? []
  const pausedJobs: BenchQueueItem[] = active?.paused?.length
    ? active.paused
    : active?.resumableRunId && inflightJobs.length === 0
      ? [
          {
            runId: active.resumableRunId,
            modelId: active.currentModel || '',
            suites: [],
            status: 'paused'
          }
        ]
      : []
  const paused = pausedJobs.length > 0 && inflightJobs.length === 0
  const busy = Boolean(
    inflightJobs.length > 0 || queuedJobs.length > 0 || spawning
  )
  const stacking = busy
  const showProgress = busy
  const installsInFlight = suites.some(card => card.installing)
  const catalogInstallError = suites.find(card => card.installError)?.installError

  useEffect(() => {
    if (catalogInstallError) setError(catalogInstallError)
  }, [catalogInstallError])

  // While a run is active (or we are watching a result), poll the live queue.
  useEffect(() => {
    if (!stacking && !detailRunId) return
    const activeTimer = window.setInterval(() => {
      void loadActive()
    }, 1500)
    const resultsTimer = window.setInterval(() => {
      void loadResults()
    }, 4000)
    return () => {
      window.clearInterval(activeTimer)
      window.clearInterval(resultsTimer)
    }
  }, [stacking, detailRunId, loadActive, loadResults])

  // Poll catalog while a background dataset install is running (survives navigation).
  useEffect(() => {
    if (!installsInFlight) return
    const timer = window.setInterval(() => {
      void loadCatalog()
    }, 1500)
    return () => window.clearInterval(timer)
  }, [installsInFlight, loadCatalog])

  // When a run finishes or pauses, refresh Results.
  useEffect(() => {
    if (wasBusyRef.current && !busy && pausedJobs.length === 0) {
      void loadStatus()
      setSelectedIds(new Set())
    }
    wasBusyRef.current = busy
  }, [busy, loadStatus, pausedJobs.length])

  useEffect(() => {
    if (paused && !busy) {
      void loadResults()
    }
  }, [paused, busy, loadResults])

  const selectedCount = selectedIds.size
  const primaryModel = runtimeSettings?.model || ''
  const compareQueue = useMemo(
    () =>
      compareModels.filter(
        option =>
          option.model !== primaryModel &&
          (option.profileId || null) !==
            (runtimeSettings?.openaiProfileId || null)
      ),
    [compareModels, primaryModel, runtimeSettings?.openaiProfileId]
  )
  const queuedCount = queuedJobs.length
  const inflightCount = inflightJobs.length

  const sampleFor = (card: BenchSuiteCard): number | null =>
    sampleBySuite[card.id] ?? minSampleSize(card)

  const toggleSuite = (card: BenchSuiteCard) => {
    if (!card.available) return
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(card.id)) next.delete(card.id)
      else next.add(card.id)
      return next
    })
    setSampleBySuite(samples => {
      if (card.id in samples) return samples
      return { ...samples, [card.id]: minSampleSize(card) }
    })
  }

  const openHuggingFaceIntegration = () => {
    setError(null)
    navigate('/dashboard/integrations/huggingface')
  }

  const installSuite = async (card: BenchSuiteCard) => {
    if (card.requiresHfToken && !card.hfTokenConfigured) {
      openHuggingFaceIntegration()
      return
    }
    if (card.installing || startingInstallId === card.id) return
    setStartingInstallId(card.id)
    setError(null)
    try {
      // Server starts a daemon thread and returns immediately.
      await client.installBenchSuite(card.id)
      await loadCatalog()
    } catch (err) {
      const message =
        formatInstallApiError(err) || `Unable to install ${card.title}`
      setError(message)
      const needsToken =
        card.requiresHfToken ||
        /hugging face|hf_token|needsHfToken/i.test(message)
      if (needsToken) {
        openHuggingFaceIntegration()
      }
    } finally {
      setStartingInstallId(null)
    }
  }

  const removeSuiteDataset = async (card: BenchSuiteCard) => {
    if (card.installing || removingId === card.id) return
    setRemovingId(card.id)
    setError(null)
    try {
      await client.uninstallBenchSuite(card.id)
      // Drop it from the next run so a removed suite cannot be spawned.
      setSelectedIds(prev => {
        if (!prev.has(card.id)) return prev
        const next = new Set(prev)
        next.delete(card.id)
        return next
      })
      await loadCatalog()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : `Unable to remove ${card.title}`
      )
    } finally {
      setRemovingId(null)
      setConfirmRemoveId(null)
    }
  }

  const runSelected = async () => {
    if (!selectedCount) {
      setError('Select at least one suite')
      return
    }
    if (!primaryModel) {
      setError('Select a model')
      return
    }
    setSpawning(true)
    setError(null)
    try {
      await client.spawnBench({
        suites: [...selectedIds].map(id => {
          const card = suites.find(row => row.id === id)
          return {
            suiteId: id,
            sampleSize: card ? sampleFor(card) : (sampleBySuite[id] ?? null)
          }
        }),
        model: primaryModel,
        models: compareQueue.map(option => option.model),
        specialistId,
        concurrency,
        parallelRuns,
        cleanupSessions
      })
      wasBusyRef.current = true
      setSelectedIds(new Set())
      setCompareModels([])
      await loadStatus()
      setTab('results')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Spawn failed')
    } finally {
      setSpawning(false)
    }
  }

  const dropActiveRun = (runId: string) => {
    setActive(prev => {
      if (!prev) return prev
      const inflight = (prev.inflight || []).filter(job => job.runId !== runId)
      const queue = prev.queue.filter(job => job.runId !== runId)
      const pausedRows = (prev.paused || []).filter(job => job.runId !== runId)
      const current = inflight[0]
      return {
        ...prev,
        inflight,
        queue,
        paused: pausedRows,
        running: inflight.length > 0,
        currentRunId: current?.runId ?? pausedRows[0]?.runId ?? null,
        currentModel: current?.modelId ?? pausedRows[0]?.modelId ?? null,
        lastProgress: current?.lastProgress ?? null,
        resumableRunId: pausedRows[0]?.runId ?? null,
        phase: inflight.length
          ? 'running'
          : queue.length
            ? 'loading'
            : pausedRows.length
              ? 'paused'
              : 'idle'
      }
    })
  }

  const cancelJob = async (runId: string) => {
    try {
      await client.cancelBenchRun(runId)
    } finally {
      dropActiveRun(runId)
      await loadStatus()
    }
  }

  const retryFailedJob = async (runId: string) => {
    setResumingId(runId)
    try {
      await client.retryFailedBenchRun(runId)
      await loadStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to retry failed questions')
    } finally {
      setResumingId(null)
    }
  }

  const resumeJob = async (runId: string) => {
    setResumingId(runId)
    try {
      await client.resumeBenchRun(runId)
      await loadStatus()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to resume bench'
      if (/nothing left to resume/i.test(message)) {
        await loadStatus()
      } else {
        setError(message)
      }
    } finally {
      setResumingId(null)
    }
  }

  const pauseJob = async (runId: string) => {
    try {
      await client.pauseBenchRun(runId)
      await loadStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to pause bench')
    }
  }

  const renderJobRow = (
    item: BenchQueueItem,
    kind: 'running' | 'paused' | 'queued'
  ) => {
    const progress = item.lastProgress
    const pct = jobBarPct(progress)
    const suitesLabel = jobSuitesLabel(item, suites)
    return (
      <div
        key={item.runId}
        className="border-border/60 space-y-2 rounded-md border px-3 py-2.5"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-foreground flex flex-wrap items-center gap-1.5 text-xs font-medium">
              {kind === 'running' ? (
                <Loader className="size-3 animate-spin" />
              ) : kind === 'paused' ? (
                <Pause className="size-3" />
              ) : null}
              <span className="truncate">{item.modelId || 'Queued run'}</span>
              {suitesLabel ? (
                <span className="text-muted-foreground font-normal">
                  · {suitesLabel}
                </span>
              ) : null}
              <span className="text-muted-foreground font-normal">
                {kind === 'queued'
                  ? 'queued'
                  : kind === 'paused'
                    ? 'paused'
                    : progress?.inFlight
                      ? `${progress.inFlight} in flight`
                      : 'running'}
              </span>
            </p>
            {kind !== 'queued' ? (
              <p className="text-muted-foreground mt-0.5 text-[11px]">
                {progress?.message ||
                  (kind === 'paused'
                    ? 'Paused — resume to continue'
                    : 'Working…')}
                {progress?.benchTotal
                  ? ` · ${progress.benchCurrent ?? 0}/${progress.benchTotal}`
                  : ''}
              </p>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1">
            {kind === 'paused' ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={resumingId === item.runId}
                onClick={() => void resumeJob(item.runId)}
              >
                {resumingId === item.runId ? (
                  <Loader className="size-3.5 animate-spin" />
                ) : (
                  <Play className="size-3.5" />
                )}
                Resume
              </Button>
            ) : kind === 'running' ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() =>
                  void client.pauseBenchRun(item.runId).then(loadStatus)
                }
              >
                <Pause className="size-3.5" />
                Pause
              </Button>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/40"
              onClick={() => void cancelJob(item.runId)}
            >
              {kind === 'queued' ? (
                <X className="size-3.5" />
              ) : (
                <Trash2 className="size-3.5" />
              )}
              Remove
            </Button>
          </div>
        </div>
        {kind === 'running' ? (
          <div className="bg-muted h-1.5 overflow-hidden rounded-full">
            <div
              className="bg-foreground h-full transition-all duration-500"
              style={{ width: `${Math.max(pct, 4)}%` }}
            />
          </div>
        ) : null}
      </div>
    )
  }

  const progressCard = showProgress ? (
    <section className="border-border/70 space-y-3 rounded-md border p-4">
      <div>
        <h3 className="text-sm font-semibold">
          {spawning && inflightCount === 0 ? 'Queuing…' : 'In progress'}
        </h3>
        <p className="text-muted-foreground mt-0.5 text-xs">
          {inflightCount ? `${inflightCount} running` : 'Waiting'}
          {queuedCount ? ` · ${queuedCount} queued` : ''}
          {parallelRuns > 1 ? ` · up to ${parallelRuns} in parallel` : ''}
        </p>
      </div>
      <div className="space-y-2">
        {inflightJobs.map(item => renderJobRow(item, 'running'))}
        {queuedJobs.map(item => renderJobRow(item, 'queued'))}
        {spawning && inflightCount === 0 && queuedCount === 0 ? (
          <p className="text-muted-foreground text-xs">Queuing run…</p>
        ) : null}
      </div>
    </section>
  ) : null

  const addCompareModel = (option: ComposerModelOption) => {
    if (option.model === primaryModel) return
    setCompareModels(prev => {
      const key = composerModelOptionKey(option)
      if (prev.some(row => composerModelOptionKey(row) === key)) return prev
      return [...prev, option]
    })
  }

  const removeCompareModel = (option: ComposerModelOption) => {
    const key = composerModelOptionKey(option)
    setCompareModels(prev =>
      prev.filter(row => composerModelOptionKey(row) !== key)
    )
  }

  const benchCliCommand = useMemo(() => {
    const parts = ['sandwalk eval run']
    const selected = suites.filter(card => selectedIds.has(card.id))
    for (const card of selected) {
      const n = sampleFor(card)
      parts.push(n != null ? `-s ${card.id}:${n}` : `-s ${card.id}`)
    }
    if (!selected.length) parts.push('-s <suite>')
    parts.push(`-m ${primaryModel || '<model>'}`)
    for (const option of compareQueue) {
      if (option.model) parts.push(`--compare ${option.model}`)
    }
    if (specialistId) parts.push(`--specialist ${specialistId}`)
    if (concurrency > 1) parts.push(`--workers ${concurrency}`)
    if (cleanupSessions) parts.push('--cleanup')
    const effort = runtimeSettings?.reasoningEffort
    if (effort) parts.push(`--effort ${effort}`)
    if (runtimeSettings?.reasoningFast) parts.push('--fast')
    return parts.join(' ')
  }, [
    cleanupSessions,
    compareQueue,
    concurrency,
    primaryModel,
    runtimeSettings?.reasoningEffort,
    runtimeSettings?.reasoningFast,
    sampleBySuite,
    selectedIds,
    specialistId,
    suites
  ])

  const modelCount = 1 + compareQueue.length
  const runLabel = [
    stacking ? 'Queue' : 'Run',
    selectedCount
      ? `${selectedCount} suite${selectedCount === 1 ? '' : 's'}`
      : null,
    selectedCount
      ? `${modelCount} model${modelCount === 1 ? '' : 's'}`
      : null
  ]
    .filter(Boolean)
    .join(' · ')

  if (isComparePath) {
    return <BenchCompareView client={client} />
  }

  if (detailRunId) {
    return <BenchResultDetail client={client} runId={detailRunId} suites={suites} />
  }

  const suiteAvatar = (card: BenchSuiteCard) => {
    const url = (card.authorAvatar || '').trim()
    const usable =
      Boolean(url) &&
      !url.includes('hendrycks') &&
      !brokenAvatars.has(url)
    if (!usable) {
      return (
        <span
          aria-hidden
          className="bg-muted text-muted-foreground flex size-8 shrink-0 items-center justify-center rounded-full"
        >
          <Gauge className="size-4" />
        </span>
      )
    }
    return (
      <img
        src={url}
        alt=""
        onError={() =>
          setBrokenAvatars(prev => {
            if (prev.has(url)) return prev
            const next = new Set(prev)
            next.add(url)
            return next
          })
        }
        className={cn(
          'size-8 shrink-0 rounded-full',
          url.endsWith('.jpg') || url.endsWith('.jpeg')
            ? 'bg-muted object-cover'
            : url.includes('sandwalk-mark')
              ? 'bg-white object-contain p-1.5'
              : 'bg-muted object-contain p-1'
        )}
      />
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold">Benchmarking</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Run suites through Sandwalk agent sessions — model, specialist,
              then results. Queue more while a run is in progress.
            </p>
          </div>
        </div>

        <div className="bg-muted/50 inline-flex w-fit rounded-md p-0.5">
          {(
            [
              ['new', 'New'],
              ['results', 'Results']
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                tab === id
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {label}
              {id === 'results'
                ? busy
                  ? resultsTotal
                    ? ` (${resultsTotal} · live)`
                    : ' (live)'
                  : resultsTotal
                    ? ` (${resultsTotal})`
                    : ''
                : ''}
            </button>
          ))}
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive space-y-1.5 rounded-md border px-3 py-2 text-sm">
            <p>{error}</p>
            <BenchLogsHint />
          </div>
        ) : null}

        {tab === 'new' ? (
          <>
            {progressCard}
            <div className="grid gap-2 sm:grid-cols-2">
              {suites.map(card => {
                const on = selectedIds.has(card.id)
                const sampleChoices = sampleChoicesFor(card)
                const installing =
                  Boolean(card.installing) || startingInstallId === card.id
                return (
                  <div
                    key={card.id}
                    role={card.available ? 'button' : undefined}
                    tabIndex={card.available ? 0 : undefined}
                    onClick={() => {
                      if (card.available) toggleSuite(card)
                    }}
                    onKeyDown={e => {
                      if (!card.available) return
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        toggleSuite(card)
                      }
                    }}
                    className={cn(
                      'rounded-md border p-3 text-left transition-colors',
                      on
                        ? 'border-border bg-muted/50'
                        : 'border-border/60',
                      card.available && 'hover:bg-muted/20 cursor-pointer',
                      !card.available && 'opacity-80'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex min-w-0 items-start gap-2.5">
                        {suiteAvatar(card)}
                        <div className="min-w-0">
                          <p className="text-sm font-semibold leading-tight">
                            {card.title}
                          </p>
                          {card.author ? (
                            <p className="text-muted-foreground mt-0.5 text-[11px]">
                              {card.author}
                            </p>
                          ) : null}
                        </div>
                      </div>
                      {on ? (
                        <Check className="text-foreground size-4 shrink-0" />
                      ) : null}
                    </div>
                    <p className="text-muted-foreground mt-1.5 line-clamp-2 text-xs leading-relaxed">
                      {card.description || card.runner}
                    </p>
                    {card.codeExec ? (
                      <span className="mt-1.5 inline-flex items-center gap-1 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 dark:text-amber-300">
                        Code exec
                      </span>
                    ) : null}
                    <div className="mt-2 flex items-end justify-between gap-2">
                      <span className="text-muted-foreground text-[11px]">
                        {card.questionCount.toLocaleString()} questions total
                        {card.id === 'mmlu'
                          ? ' · 57 subjects'
                          : card.id === 'mmlu-pro'
                            ? ' · 14 subjects'
                            : card.id === 'arc-challenge'
                              ? ' · science'
                              : card.id === 'mbpp'
                                ? ' · Python'
                                : card.id === 'livecodebench'
                                  ? ' · coding'
                                  : ''}
                      </span>
                      {card.available && sampleChoices.length ? (
                        <label
                          className="flex flex-col items-end gap-0.5"
                          onClick={e => e.stopPropagation()}
                        >
                          <span className="text-muted-foreground text-[10px]">
                            Sample size
                          </span>
                          <select
                            className="border-border/70 bg-background max-w-[11rem] rounded-md border px-1.5 py-0.5 text-[11px]"
                            aria-label="Sample size"
                            value={sampleFor(card) ?? sampleChoices[0]}
                            onChange={e => {
                              const n = Number(e.target.value)
                              setSampleBySuite(prev => ({
                                ...prev,
                                [card.id]: n
                              }))
                              setSelectedIds(prev => {
                                if (prev.has(card.id)) return prev
                                const next = new Set(prev)
                                next.add(card.id)
                                return next
                              })
                            }}
                          >
                            {sampleChoices.map(n => (
                              <option key={n} value={n}>
                                {n === card.questionCount
                                  ? `Full (${n.toLocaleString()})`
                                  : `${n.toLocaleString()} questions`}
                              </option>
                            ))}
                          </select>
                        </label>
                      ) : null}
                    </div>
                    {(card.missingSkills?.length ||
                      card.missingMcps?.length) ? (
                      <div
                        className="border-amber-500/30 bg-amber-500/10 mt-2 space-y-1.5 rounded-md border px-2.5 py-2"
                        onClick={e => e.stopPropagation()}
                      >
                        <p className="text-[11px] font-medium text-amber-700 dark:text-amber-300">
                          Missing skills/MCPs — matching questions will be
                          skipped
                        </p>
                        {card.unavailableReason ? (
                          <p className="text-[11px] text-amber-800/90 dark:text-amber-200/90">
                            {card.unavailableReason}
                          </p>
                        ) : null}
                        {card.missingSkills?.length ? (
                          <p className="text-[11px] text-amber-800/90 dark:text-amber-200/90">
                            Skills: {card.missingSkills.join(', ')}
                          </p>
                        ) : null}
                        {card.missingMcps?.length ? (
                          <p className="text-[11px] text-amber-800/90 dark:text-amber-200/90">
                            MCPs: {card.missingMcps.join(', ')}
                          </p>
                        ) : null}
                        <div className="flex flex-wrap gap-2 pt-0.5">
                          {card.missingSkills?.length ? (
                            <button
                              type="button"
                              className="text-muted-foreground hover:text-foreground text-[11px] underline-offset-2 hover:underline"
                              onClick={() => navigate('/dashboard/skills')}
                            >
                              Open Skills
                            </button>
                          ) : null}
                          {card.missingMcps?.length ? (
                            <button
                              type="button"
                              className="text-muted-foreground hover:text-foreground text-[11px] underline-offset-2 hover:underline"
                              onClick={() => navigate('/dashboard/mcp')}
                            >
                              Open MCP
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                    {card.installable && (!card.installed || installing) ? (
                      <div
                        className="mt-2"
                        onClick={e => e.stopPropagation()}
                      >
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-auto min-h-8 w-full whitespace-normal px-2 py-1.5 text-left text-[11px] leading-snug"
                          disabled={installing || Boolean(startingInstallId)}
                          onClick={() => void installSuite(card)}
                        >
                          {installing ? (
                            <Loader className="size-3.5 shrink-0 animate-spin" />
                          ) : (
                            <Download className="size-3.5 shrink-0" />
                          )}
                          <span className="min-w-0 flex-1">
                            {installButtonLabel(card, installing)}
                          </span>
                        </Button>
                        {card.installError ? (
                          <div className="border-destructive/30 bg-destructive/5 text-destructive mt-2 space-y-1 rounded-md border px-2.5 py-2 text-[11px] leading-snug">
                            <p>{card.installError}</p>
                            <BenchLogsHint />
                            {card.requiresHfToken ? (
                              <button
                                type="button"
                                className="inline-flex items-center gap-1 underline-offset-2 hover:underline"
                                onClick={openHuggingFaceIntegration}
                              >
                                <ExternalLink className="size-3" />
                                Hugging Face
                              </button>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    {card.installed && !installing ? (
                      <div
                        className="text-muted-foreground mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]"
                        onClick={e => e.stopPropagation()}
                      >
                        <span>
                          Cached
                          {card.installedBytes
                            ? ` · ${formatBytes(card.installedBytes)}`
                            : ''}
                          {card.installedCount
                            ? ` · ${card.installedCount.toLocaleString()} questions`
                            : ''}
                        </span>
                        {confirmRemoveId === card.id ? (
                          <span className="inline-flex items-center gap-2">
                            <span className="text-foreground">Remove data?</span>
                            <button
                              type="button"
                              className="text-destructive underline-offset-2 hover:underline disabled:opacity-60"
                              disabled={removingId === card.id}
                              onClick={() => void removeSuiteDataset(card)}
                            >
                              {removingId === card.id
                                ? 'Removing…'
                                : 'Yes, remove'}
                            </button>
                            <button
                              type="button"
                              className="hover:text-foreground underline-offset-2 hover:underline"
                              onClick={() => setConfirmRemoveId(null)}
                            >
                              Cancel
                            </button>
                          </span>
                        ) : (
                          <button
                            type="button"
                            className="hover:text-foreground inline-flex items-center gap-1 underline-offset-2 hover:underline"
                            onClick={() => setConfirmRemoveId(card.id)}
                          >
                            <Trash2 className="size-3" />
                            Remove
                          </button>
                        )}
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </>
        ) : null}

        {tab === 'results' ? (
          <BenchResultsList
            client={client}
            suites={suites}
            inflightJobs={inflightJobs}
            queuedJobs={queuedJobs}
            pausedJobs={pausedJobs}
            busy={busy}
            resumingId={resumingId}
            onResume={runId => void resumeJob(runId)}
            onRetryFailed={runId => void retryFailedJob(runId)}
            onPause={runId => void pauseJob(runId)}
            onCancel={runId => void cancelJob(runId)}
          />
        ) : null}
        </div>
      </ScrollArea>

      {tab === 'new' ? (
        <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 shrink-0 border-t px-4 py-3 backdrop-blur md:px-6">
          <div className="mx-auto flex w-full max-w-7xl flex-col gap-2">
            {compareQueue.length ? (
              <div className="flex flex-wrap gap-1.5">
                {compareQueue.map(option => (
                  <span
                    key={composerModelOptionKey(option)}
                    className="bg-muted text-foreground inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px]"
                  >
                    {option.label || option.model}
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground"
                      aria-label={`Remove ${option.label || option.model}`}
                      onClick={() => removeCompareModel(option)}
                    >
                      <X className="size-3" />
                    </button>
                  </span>
                ))}
              </div>
            ) : null}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <ComposerModelPicker
                  modelOptions={modelOptions}
                  runtimeSettings={runtimeSettings}
                  onModelSelect={async (provider, model, profileId) => {
                    if (profileId) {
                      try {
                        await client.updateModelProfile(profileId, {
                          setActive: true
                        })
                      } catch {
                        // Profile activation is best-effort for local models.
                      }
                    }
                    const runtimeProvider =
                      provider === 'local' || profileId ? 'openai' : provider
                    setRuntimeSettings(
                      await client.updateRuntimeSettings({
                        provider: runtimeProvider,
                        model
                      })
                    )
                  }}
                  onReasoningSettingsChange={async changes => {
                    const runtimeProvider =
                      changes.provider === 'local' ? 'openai' : changes.provider
                    // Optimistic paint — picker reads effort from runtimeSettings.
                    setRuntimeSettings(prev =>
                      prev
                        ? {
                            ...prev,
                            ...(typeof changes.reasoningEffort === 'string'
                              ? { reasoningEffort: changes.reasoningEffort }
                              : {}),
                            ...(typeof changes.reasoningFast === 'boolean'
                              ? { reasoningFast: changes.reasoningFast }
                              : {})
                          }
                        : prev
                    )
                    setModelOptions(prev =>
                      patchComposerModelEffort(prev, changes)
                    )
                    setRuntimeSettings(
                      await client.updateRuntimeSettings({
                        provider: runtimeProvider,
                        model: changes.model,
                        reasoningEffort: changes.reasoningEffort,
                        reasoningFast: changes.reasoningFast
                      })
                    )
                  }}
                  onAddModels={() => navigate('/dashboard/models')}
                  onLoadModelPreferences={() => client.getModelPreferences()}
                  onToggleModelFavorite={option =>
                    client.toggleModelFavorite({
                      provider: option.provider,
                      model: option.model,
                      profileId: option.profileId
                    })
                  }
                />
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground text-[11px] whitespace-nowrap">
                    Run on
                  </span>
                  <ComposerSpecialistPicker
                    specialists={specialists}
                    selectedSpecialistId={specialistId}
                    onSpecialistSelect={id => setSpecialistId(id)}
                    onCreateSpecialist={() =>
                      navigate('/dashboard/specialists/new')
                    }
                    onManageSpecialists={() =>
                      navigate('/dashboard/specialists')
                    }
                  />
                </div>
                <ComposerModelPicker
                  modelOptions={modelOptions}
                  runtimeSettings={runtimeSettings}
                  triggerLabel={
                    compareQueue.length
                      ? `Compare +${compareQueue.length}`
                      : 'Compare'
                  }
                  onModelSelect={async (provider, model, profileId) => {
                    const option =
                      modelOptions.find(
                        row =>
                          row.model === model &&
                          row.provider === provider &&
                          (row.profileId || null) === (profileId || null)
                      ) ||
                      modelOptions.find(row => row.model === model) || {
                        provider,
                        model,
                        label: model,
                        speed: '',
                        profileId: profileId || null,
                        contextWindow: null
                      }
                    addCompareModel(option)
                  }}
                  onAddModels={() => navigate('/dashboard/models')}
                  onLoadModelPreferences={() => client.getModelPreferences()}
                  onToggleModelFavorite={option =>
                    client.toggleModelFavorite({
                      provider: option.provider,
                      model: option.model,
                      profileId: option.profileId
                    })
                  }
                />
                <label
                  className="text-muted-foreground flex items-center gap-1.5 text-[11px]"
                  title="Parallel questions inside one suite"
                >
                  Workers
                  <select
                    className="border-border bg-background text-foreground rounded-md border px-1.5 py-1 text-xs"
                    value={concurrency}
                    onChange={e =>
                      setConcurrency(
                        Math.max(1, Math.min(16, Number(e.target.value) || 1))
                      )
                    }
                  >
                    {[1, 2, 3, 4, 6, 8, 12, 16].map(n => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <label
                  className="text-muted-foreground flex items-center gap-1.5 text-[11px]"
                  title="How many independent stacks run at once. Separate from Workers."
                >
                  Parallel runs
                  <select
                    className="border-border bg-background text-foreground rounded-md border px-1.5 py-1 text-xs"
                    value={parallelRuns}
                    onChange={e =>
                      setParallelRuns(
                        Math.max(1, Math.min(16, Number(e.target.value) || 1))
                      )
                    }
                  >
                    {[1, 2, 3, 4, 6, 8, 12, 16].map(n => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <label
                  className="text-muted-foreground flex items-center gap-1.5 text-[11px]"
                  title="After a successful run, delete the bench project and its chats. Results JSON is kept."
                >
                  <input
                    type="checkbox"
                    className="size-3.5 accent-foreground"
                    checked={cleanupSessions}
                    onChange={e => setCleanupSessions(e.target.checked)}
                  />
                  Delete chats after run
                </label>
              </div>
              <div className="flex items-center gap-1.5">
                <DropdownMenu
                  open={cliMenuOpen}
                  onOpenChange={open => {
                    setCliMenuOpen(open)
                    if (!open) setCopiedCli(false)
                  }}
                  modal={false}
                >
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="size-8 shrink-0"
                      aria-label="Show CLI command"
                      title="Show CLI command"
                      disabled={!selectedCount || !primaryModel}
                      onMouseEnter={() => {
                        if (selectedCount && primaryModel) openCliMenu()
                      }}
                      onMouseLeave={scheduleCloseCliMenu}
                    >
                      <Terminal className="size-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    side="top"
                    sideOffset={8}
                    className="w-[min(36rem,calc(100vw-2rem))] overflow-hidden rounded-xl p-0"
                    onCloseAutoFocus={event => event.preventDefault()}
                    onMouseEnter={openCliMenu}
                    onMouseLeave={scheduleCloseCliMenu}
                  >
                    <div className="px-4 pt-3">
                      <p className="text-foreground text-sm font-semibold">
                        Run in Agent CLI
                      </p>
                    </div>
                    <div className="px-4 pb-3 pt-2">
                      <div className="border-border/80 bg-muted/35 flex items-start gap-2 rounded-lg border p-2.5">
                        <Terminal className="text-muted-foreground mt-0.5 size-4 shrink-0" />
                        <code className="min-w-0 flex-1 whitespace-pre-wrap break-all font-mono text-[12px] leading-relaxed">
                          {benchCliCommand}
                        </code>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="size-7 shrink-0 rounded-md"
                          onClick={event => {
                            event.preventDefault()
                            event.stopPropagation()
                            void copyText(benchCliCommand).then(ok => {
                              if (!ok) {
                                setError('Could not copy CLI command')
                                return
                              }
                              setCopiedCli(true)
                              window.setTimeout(() => setCopiedCli(false), 2000)
                            })
                          }}
                          aria-label="Copy CLI command"
                          title="Copy CLI command"
                        >
                          {copiedCli ? (
                            <Check className="size-3.5" />
                          ) : (
                            <Copy className="size-3.5" />
                          )}
                        </Button>
                      </div>
                      <p className="text-muted-foreground mt-2 text-xs">
                        Paste into a terminal while Sandwalk is running. Results
                        show under Dashboard → Benchmarking → Results.
                      </p>
                    </div>
                  </DropdownMenuContent>
                </DropdownMenu>
                <Button
                  type="button"
                  size="sm"
                  disabled={spawning || !selectedCount || !primaryModel}
                  onClick={() => void runSelected()}
                >
                  {spawning ? (
                    <Loader className="size-3.5 animate-spin" />
                  ) : (
                    <Play className="size-3.5" />
                  )}
                  {runLabel}
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
