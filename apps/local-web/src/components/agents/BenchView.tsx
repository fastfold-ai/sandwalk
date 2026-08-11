import type {
  BenchActiveStatus,
  BenchResultSummary,
  BenchSuiteCard,
  LocalAgentClient
} from '@sandwalk/agent-local-client'
import type { RuntimeSettings, Specialist } from '@sandwalk/agent-ui-core'
import {
  Check,
  Columns2,
  Copy,
  Download,
  ExternalLink,
  Gauge,
  Loader2,
  Pause,
  Play,
  Target,
  Terminal,
  Trash2,
  X
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { matchPath, useLocation, useNavigate } from 'react-router-dom'

import { BenchCompareView } from '@/components/agents/BenchCompareView'
import { BenchResultDetail } from '@/components/agents/BenchResultDetail'
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
  formatModelEffortBadge,
  patchComposerModelEffort,
  toComposerModelOptions
} from '@/lib/composer-models'
import { relativeDayLabel } from '@/lib/sessions'
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

/** Compact run duration: `39s`, `11m 12s`, `2h 35m`, `1d 2h`. */
function formatRunDuration(seconds: number): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0))
  if (total < 60) return `${total}s`
  const days = Math.floor(total / 86_400)
  const hours = Math.floor((total % 86_400) / 3_600)
  const minutes = Math.floor((total % 3_600) / 60)
  const secs = total % 60
  if (days > 0) {
    return hours > 0 ? `${days}d ${hours}h` : `${days}d`
  }
  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`
  }
  return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`
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

function installPercent(card: BenchSuiteCard): number {
  const done = card.installBytesDone
  const total = card.installBytesTotal
  if (done != null && total != null && total > 0) {
    return Math.max(2, Math.min(100, Math.round((100 * done) / total)))
  }
  // Indeterminate-ish pulse when size unknown — keep a visible sliver.
  if (card.installing || (done != null && done > 0)) return 35
  return 8
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
  const [results, setResults] = useState<BenchResultSummary[]>([])
  const [compareSelection, setCompareSelection] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [spawning, setSpawning] = useState(false)
  const [concurrency, setConcurrency] = useState(1)
  const [cleanupSessions, setCleanupSessions] = useState(false)
  const [startingInstallId, setStartingInstallId] = useState<string | null>(
    null
  )
  const [cliMenuOpen, setCliMenuOpen] = useState(false)
  const [copiedCli, setCopiedCli] = useState(false)
  const [removingId, setRemovingId] = useState<string | null>(null)
  const [confirmRemoveId, setConfirmRemoveId] = useState<string | null>(null)
  const [cacheBytes, setCacheBytes] = useState(0)
  const [brokenAvatars, setBrokenAvatars] = useState<Set<string>>(
    () => new Set()
  )
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
      setCacheBytes(catalog.cacheBytes)
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
      const res = await client.listBenchResults()
      setResults(res)
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

  const paused = active?.phase === 'paused' || Boolean(active?.resumableRunId)
  const busy = Boolean(
    active?.running || (active?.queue?.length ?? 0) > 0 || spawning
  )
  const showProgress = busy || paused
  const installsInFlight = suites.some(card => card.installing)

  // While a run is active, poll only /runs/active (skip heavy results list).
  useEffect(() => {
    if (!busy) return
    const timer = window.setInterval(() => {
      void loadActive()
    }, 1500)
    return () => window.clearInterval(timer)
  }, [busy, loadActive])

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
    if (wasBusyRef.current && !busy) {
      void loadStatus()
      setSelectedIds(new Set())
    }
    wasBusyRef.current = busy
  }, [busy, loadStatus])

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
  const progress = active?.lastProgress
  const barPct =
    progress?.benchTotal && progress.benchTotal > 0
      ? Math.min(
          100,
          Math.round(((progress.benchCurrent || 0) / progress.benchTotal) * 100)
        )
      : 0
  const queuedCount = active?.queue?.length ?? 0

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

  const installSuite = async (card: BenchSuiteCard) => {
    if (card.requiresHfToken && !card.hfTokenConfigured) {
      setError(
        'Set a Hugging Face token under Integrations → Hugging Face, accept the dataset terms, then Install.'
      )
      navigate('/dashboard/integrations/huggingface')
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
        err instanceof Error ? err.message : `Unable to install ${card.title}`
      const needsToken =
        card.requiresHfToken ||
        /hugging face|hf_token|needsHfToken/i.test(message)
      if (needsToken) {
        setError(
          'Hugging Face token required. Save it under Integrations → Hugging Face, then try Install again.'
        )
        navigate('/dashboard/integrations/huggingface')
      } else {
        setError(message)
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
        cleanupSessions
      })
      wasBusyRef.current = true
      await loadStatus()
      setTab('results')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Spawn failed')
    } finally {
      setSpawning(false)
    }
  }

  const runIdForActions =
    active?.currentRunId || active?.resumableRunId || 'active'

  const progressCard = showProgress ? (
    <section className="border-border/70 space-y-3 rounded-md border p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">
            {paused
              ? 'Paused'
              : spawning && !active?.running
                ? 'Queuing…'
                : 'In progress'}
          </h3>
          <p className="text-muted-foreground mt-0.5 text-xs">
            {active?.currentModel || primaryModel}
            {progress?.benchmark
              ? ` · ${suiteDisplayName(progress.benchmark, suites)}`
              : ''}
            {queuedCount ? ` · ${queuedCount} queued` : ''}
            {progress?.inFlight
              ? ` · ${progress.inFlight} in flight`
              : ''}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-1.5">
          {active?.projectId ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => navigate(`/projects/${active.projectId}`)}
            >
              <ExternalLink className="size-3.5" />
              View
            </Button>
          ) : null}
          {paused ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() =>
                void client.resumeBenchRun(runIdForActions).then(loadStatus)
              }
            >
              <Play className="size-3.5" />
              Resume
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={!active?.running}
              onClick={() =>
                void client.pauseBenchRun(runIdForActions).then(loadActive)
              }
            >
              <Pause className="size-3.5" />
              Pause
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/40"
            onClick={() =>
              void (async () => {
                try {
                  await client.cancelBenchRun(runIdForActions)
                } finally {
                  // Drop the paused card immediately even if the server
                  // already had a stale resumable pointer.
                  setActive(prev =>
                    prev
                      ? {
                          ...prev,
                          running: false,
                          phase: 'idle',
                          resumableRunId: null,
                          currentRunId: null,
                          lastProgress: null,
                          queue: [],
                          projectId: null
                        }
                      : prev
                  )
                  await loadStatus()
                }
              })()
            }
          >
            <Trash2 className="size-3.5" />
            Remove
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {active?.currentModel ? (
          <span className="bg-muted text-foreground inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs">
            {paused ? (
              <Pause className="size-3" />
            ) : (
              <Loader2 className="size-3 animate-spin" />
            )}
            {active.currentModel}
          </span>
        ) : spawning ? (
          <span className="bg-muted text-foreground inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs">
            <Loader2 className="size-3 animate-spin" />
            Starting…
          </span>
        ) : null}
        {active?.queue?.map(item => (
          <span
            key={item.runId}
            className="border-border/70 text-muted-foreground inline-flex rounded-md border px-2 py-1 text-xs"
          >
            {item.modelId}
          </span>
        ))}
      </div>
      <p className="text-muted-foreground text-sm">
        {progress?.message ||
          (paused
            ? 'Paused — resume to continue'
            : spawning
              ? 'Queuing run…'
              : 'Working…')}
        {' · '}
        {progress?.benchCurrent ?? progress?.current ?? 0}/
        {progress?.benchTotal ?? progress?.total ?? 0}
      </p>
      <div className="bg-muted h-1.5 overflow-hidden rounded-full">
        <div
          className="bg-foreground h-full transition-all duration-500"
          style={{ width: `${Math.max(barPct, spawning ? 4 : 0)}%` }}
        />
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
    busy ? 'Queue' : 'Run',
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
    return <BenchResultDetail client={client} runId={detailRunId} />
  }

  const toggleCompareSelection = (runId: string) => {
    setCompareSelection(current => {
      if (current.includes(runId)) {
        return current.filter(id => id !== runId)
      }
      if (current.length >= 2) {
        return [current[1], runId]
      }
      return [...current, runId]
    })
  }

  const openCompare = () => {
    if (compareSelection.length !== 2) return
    const [a, b] = compareSelection
    navigate(
      `/dashboard/bench/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`
    )
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
                  ? results.length
                    ? ` (${results.length} · live)`
                    : ' (live)'
                  : results.length
                    ? ` (${results.length})`
                    : ''
                : ''}
            </button>
          ))}
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        {tab === 'new' ? (
          <>
            {showProgress ? (
              <button
                type="button"
                onClick={() => setTab('results')}
                className="border-border/70 bg-muted/30 text-muted-foreground hover:text-foreground flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-xs transition-colors"
              >
                <span className="inline-flex items-center gap-1.5">
                  {paused ? (
                    <Pause className="size-3" />
                  ) : (
                    <Loader2 className="size-3 animate-spin" />
                  )}
                  {paused ? 'Run paused' : 'Run in progress'}
                  {progress?.benchmark
                    ? ` · ${suiteDisplayName(progress.benchmark, suites)}`
                    : ''}
                  {queuedCount ? ` · ${queuedCount} queued` : ''}
                </span>
                <span>View on Results →</span>
              </button>
            ) : null}
            {cacheBytes > 0 ? (
              <p className="text-muted-foreground text-[11px]">
                Dataset cache: {formatBytes(cacheBytes)} · remove a suite below to
                free space
              </p>
            ) : null}
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
                    {!card.available || installing ? (
                      <div
                        className="mt-2 space-y-2"
                        onClick={e => e.stopPropagation()}
                      >
                        {installing ? (
                          <div className="border-border/60 bg-muted/30 space-y-1.5 rounded-md border px-2.5 py-2">
                            <p className="text-foreground text-[11px] font-medium">
                              Downloading in the background…
                            </p>
                            <p className="text-muted-foreground font-mono text-[11px]">
                              {card.installProgress ||
                                card.unavailableReason ||
                                'Starting download…'}
                            </p>
                            <div className="bg-muted h-1.5 overflow-hidden rounded-full">
                              <div
                                className="bg-foreground/70 h-full rounded-full transition-[width] duration-300"
                                style={{
                                  width: `${installPercent(card)}%`
                                }}
                              />
                            </div>
                            {card.installBytesDone != null ? (
                              <p className="text-muted-foreground text-[10px]">
                                {formatBytes(card.installBytesDone)}
                                {card.installBytesTotal
                                  ? ` / ${formatBytes(card.installBytesTotal)}`
                                  : ' downloaded'}
                              </p>
                            ) : null}
                          </div>
                        ) : card.unavailableReason &&
                          !(
                            card.missingSkills?.length ||
                            card.missingMcps?.length
                          ) ? (
                          <p className="text-destructive text-[11px]">
                            {card.unavailableReason}
                          </p>
                        ) : null}
                        {card.installable ? (
                          <div className="flex flex-wrap items-center gap-2">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={
                                installing || Boolean(startingInstallId)
                              }
                              onClick={() => void installSuite(card)}
                            >
                              {installing ? (
                                <Loader2 className="size-3.5 animate-spin" />
                              ) : (
                                <Download className="size-3.5" />
                              )}
                              {installing
                                ? 'Installing…'
                                : card.requiresHfToken && !card.hfTokenConfigured
                                  ? 'Set HF token'
                                  : 'Install'}
                            </Button>                            {card.requiresHfToken && !card.hfTokenConfigured ? (
                              <button
                                type="button"
                                className="text-muted-foreground hover:text-foreground text-[11px] underline-offset-2 hover:underline"
                                onClick={() =>
                                  navigate('/dashboard/integrations/huggingface')
                                }
                              >
                                Open Hugging Face integration
                              </button>
                            ) : null}
                          </div>
                        ) : null}
                        {card.installable && card.missingDependency ? (
                          <p className="text-muted-foreground text-[11px]">
                            {card.missingDependency}
                          </p>
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
          <section className="space-y-3">
            {progressCard}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-muted-foreground text-sm">
                {results.length
                  ? `${results.length} run${results.length === 1 ? '' : 's'}`
                  : busy
                    ? 'Waiting for the first finished run…'
                    : 'No runs yet'}
                {compareSelection.length ? (
                  <span>
                    {' '}
                    · {compareSelection.length}/2 selected for compare
                  </span>
                ) : results.length >= 2 ? (
                  <span> · select 2 to compare</span>
                ) : null}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                {compareSelection.length ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setCompareSelection([])}
                  >
                    Clear selection
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  disabled={compareSelection.length !== 2}
                  onClick={openCompare}
                >
                  <Columns2 className="size-3.5" />
                  Compare
                  {compareSelection.length === 2 ? '' : ` · ${compareSelection.length}/2`}
                </Button>
                {results.length ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      void client.resetBenchResults().then(loadStatus)
                    }
                  >
                    <Trash2 className="size-3.5" />
                    Clear
                  </Button>
                ) : null}
              </div>
            </div>
            <div className="space-y-2">
              {results.map(r => {
                const pct = Math.round((r.accuracy || 0) * 1000) / 10
                const picked = compareSelection.includes(r.runId)
                return (
                  <div
                    key={r.runId}
                    className={cn(
                      'group border-border/70 rounded-md border px-3 py-3 transition-colors',
                      picked
                        ? 'border-primary/35 bg-primary/[0.04]'
                        : 'hover:bg-muted/30'
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 items-start gap-2.5">
                        <button
                          type="button"
                          aria-label={
                            picked
                              ? 'Deselect for compare'
                              : 'Select for compare'
                          }
                          aria-pressed={picked}
                          title={picked ? 'Selected for compare' : 'Select to compare'}
                          className="relative size-8 shrink-0"
                          onClick={() => toggleCompareSelection(r.runId)}
                        >
                          <span
                            className={cn(
                              'flex size-8 items-center justify-center rounded-md transition-opacity',
                              pct >= 70
                                ? 'bg-emerald-500/15 text-emerald-600'
                                : pct >= 40
                                  ? 'bg-amber-500/15 text-amber-600'
                                  : 'bg-red-500/15 text-red-600',
                              picked
                                ? 'opacity-30'
                                : 'group-hover:opacity-30'
                            )}
                          >
                            <Target className="size-3.5" />
                          </span>
                          <span
                            className={cn(
                              'absolute inset-0 m-auto flex size-4 items-center justify-center rounded-full border shadow-sm transition-opacity',
                              picked
                                ? 'border-primary bg-primary text-primary-foreground opacity-100'
                                : 'border-border/80 bg-background/95 text-muted-foreground opacity-0 group-hover:opacity-100'
                            )}
                          >
                            {picked ? (
                              <Check className="size-2.5" strokeWidth={3} />
                            ) : null}
                          </span>
                        </button>
                        <button
                          type="button"
                          className="min-w-0 flex-1 text-left"
                          onClick={() => {
                            setTab('results')
                            navigate(
                              `/dashboard/bench/${encodeURIComponent(r.runId)}`
                            )
                          }}
                        >
                          <div className="flex flex-wrap items-center gap-1.5">
                            <h4 className="text-sm font-semibold">
                              {suiteDisplayName(r.benchmark, suites)}
                            </h4>
                            <span className="bg-muted text-muted-foreground rounded-md px-1.5 py-0.5 text-[11px]">
                              {r.modelId}
                              {r.reasoningEffort ||
                              r.reasoningFast != null
                                ? ` · ${formatModelEffortBadge({
                                    reasoningEffort:
                                      r.reasoningEffort || 'medium',
                                    reasoningFast: Boolean(r.reasoningFast)
                                  })}`
                                : r.thinkingUsed
                                  ? ' · thinking'
                                  : ''}
                            </span>
                          </div>
                          <p className="text-muted-foreground mt-0.5 text-xs">
                            {r.correct}/{r.total} · {formatRunDuration(r.timeS)}
                            {r.createdAt
                              ? ` · ${relativeDayLabel(r.createdAt)}`
                              : ''}
                          </p>
                        </button>
                      </div>
                      <p
                        className={cn(
                          'text-lg font-semibold tabular-nums',
                          pct >= 70
                            ? 'text-emerald-600'
                            : pct >= 40
                              ? 'text-amber-600'
                              : 'text-red-600'
                        )}
                      >
                        {pct.toFixed(1)}%
                      </p>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs">
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground"
                        onClick={() =>
                          navigate(
                            `/dashboard/bench/${encodeURIComponent(r.runId)}`
                          )
                        }
                      >
                        View details
                      </button>
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
                        onClick={() =>
                          void client
                            .downloadBenchExport(r.runId)
                            .then(file => {
                              const url = URL.createObjectURL(file.blob)
                              const a = document.createElement('a')
                              a.href = url
                              a.download = file.filename
                              a.click()
                              URL.revokeObjectURL(url)
                            })
                        }
                      >
                        <Download className="size-3" />
                        Download
                      </button>
                      {r.projectId ? (
                        <button
                          type="button"
                          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
                          onClick={() => navigate(`/projects/${r.projectId}`)}
                        >
                          <ExternalLink className="size-3" />
                          View
                        </button>
                      ) : null}
                    </div>
                  </div>
                )
              })}
              {!results.length ? (
                <div className="border-border/60 rounded-md border border-dashed px-4 py-8 text-center">
                  <p className="text-muted-foreground text-sm">
                    No results yet. Start a run from New.
                  </p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="mt-3"
                    onClick={() => setTab('new')}
                  >
                    New bench
                  </Button>
                </div>
              ) : null}
            </div>
          </section>
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
                <label className="text-muted-foreground flex items-center gap-1.5 text-[11px]">
                  Workers
                  <select
                    className="border-border bg-background text-foreground rounded-md border px-1.5 py-1 text-xs"
                    value={concurrency}
                    onChange={e =>
                      setConcurrency(
                        Math.max(1, Math.min(8, Number(e.target.value) || 1))
                      )
                    }
                  >
                    {[1, 2, 3, 4, 6, 8].map(n => (
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
                  disabled={
                    spawning || busy || paused || !selectedCount || !primaryModel
                  }
                  onClick={() => void runSelected()}
                >
                  {spawning ? (
                    <Loader2 className="size-3.5 animate-spin" />
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
