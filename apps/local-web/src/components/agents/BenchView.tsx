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
  Gauge,
  Loader2,
  Play,
  Square,
  Target,
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
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  type ComposerModelOption,
  toComposerModelOptions
} from '@/lib/composer-models'
import { cn } from '@/lib/utils'

type Tab = 'new' | 'results'

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
  const [selected, setSelected] = useState<Record<string, number | null>>({})
  const [modelOptions, setModelOptions] = useState<ComposerModelOption[]>([])
  const [compareModels, setCompareModels] = useState<ComposerModelOption[]>([])
  const [specialists, setSpecialists] = useState<Specialist[]>([])
  const [specialistId, setSpecialistId] = useState<string | null>(null)
  const [active, setActive] = useState<BenchActiveStatus | null>(null)
  const [results, setResults] = useState<BenchResultSummary[]>([])
  const [compareSelection, setCompareSelection] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [spawning, setSpawning] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [brokenAvatars, setBrokenAvatars] = useState<Set<string>>(
    () => new Set()
  )
  const wasBusyRef = useRef(false)
  const prevOverlayRef = useRef(false)

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
      const [cards, models, profiles, specialistRows] = await Promise.all([
        client.listBenchSuites(),
        client.listModels({ enabledOnly: true, discover: true }).catch(() => []),
        client.listModelProfiles().catch(() => []),
        client.listSpecialists().catch(() => [])
      ])
      const backendsByProfileId = Object.fromEntries(
        (profiles || []).map(profile => [profile.id, profile.backend])
      )
      setSuites(cards)
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

  const loadStatus = useCallback(async () => {
    try {
      const [res, status] = await Promise.all([
        client.listBenchResults(),
        client.getBenchActive()
      ])
      setResults(res)
      setActive(status)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load bench')
    }
  }, [client])

  useEffect(() => {
    void loadCatalog()
    void loadStatus()
  }, [loadCatalog, loadStatus])

  const busy = Boolean(active?.running || (active?.queue?.length ?? 0) > 0)

  useEffect(() => {
    if (!busy) return
    const timer = window.setInterval(() => {
      void loadStatus()
    }, 1500)
    return () => window.clearInterval(timer)
  }, [busy, loadStatus])

  // When a run finishes, refresh Results (stay on whatever tab the user chose).
  useEffect(() => {
    if (wasBusyRef.current && !busy) {
      void loadStatus()
      setSelected({})
    }
    wasBusyRef.current = busy
  }, [busy, loadStatus])

  const selectedCount = Object.keys(selected).length
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

  const toggleSuite = (card: BenchSuiteCard) => {
    setSelected(prev => {
      const next = { ...prev }
      if (card.id in next) {
        delete next[card.id]
      } else {
        next[card.id] = card.defaultSampleSize ?? card.sampleSizes[0] ?? null
      }
      return next
    })
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
        suites: Object.keys(selected).map(id => ({
          suiteId: id,
          sampleSize: selected[id]
        })),
        model: primaryModel,
        models: compareQueue.map(option => option.model),
        specialistId
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

  const progressCard = busy || spawning ? (
    <section className="border-border/70 space-y-3 rounded-md border p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">
            {spawning && !busy ? 'Queuing…' : 'In progress'}
          </h3>
          <p className="text-muted-foreground mt-0.5 text-xs">
            {active?.currentModel || primaryModel}
            {progress?.benchmark ? ` · ${progress.benchmark}` : ''}
            {queuedCount ? ` · ${queuedCount} queued` : ''}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() =>
            void client
              .cancelBenchRun(active?.currentRunId || 'active')
              .then(loadStatus)
          }
        >
          <Square className="size-3.5" />
          Cancel
        </Button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {active?.currentModel ? (
          <span className="bg-muted text-foreground inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs">
            <Loader2 className="size-3 animate-spin" />
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
        {progress?.message || (spawning ? 'Queuing run…' : 'Working…')}
        {' · '}
        {progress?.current ?? 0}/{progress?.total ?? 0}
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

  const cliCommandFor = (card: BenchSuiteCard) => {
    const n =
      (card.id in selected ? selected[card.id] : null) ??
      card.defaultSampleSize ??
      card.sampleSizes[0] ??
      null
    const model = primaryModel || '<model>'
    const parts = [
      'sandwalk eval run',
      `-s ${card.id}`,
      ...(n != null ? [`-n ${n}`] : []),
      `-m ${model}`
    ]
    if (specialistId) parts.push(`--specialist ${specialistId}`)
    return parts.join(' ')
  }

  const copyCli = async (card: BenchSuiteCard) => {
    const cmd = cliCommandFor(card)
    try {
      await navigator.clipboard.writeText(cmd)
      setCopiedId(card.id)
      window.setTimeout(() => {
        setCopiedId(prev => (prev === card.id ? null : prev))
      }, 1500)
    } catch {
      setError('Could not copy CLI command')
    }
  }

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
            {busy ? (
              <button
                type="button"
                onClick={() => setTab('results')}
                className="border-border/70 bg-muted/30 text-muted-foreground hover:text-foreground flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-xs transition-colors"
              >
                <span className="inline-flex items-center gap-1.5">
                  <Loader2 className="size-3 animate-spin" />
                  Run in progress
                  {progress?.benchmark ? ` · ${progress.benchmark}` : ''}
                  {queuedCount ? ` · ${queuedCount} queued` : ''}
                </span>
                <span>View on Results →</span>
              </button>
            ) : null}
            <div className="grid gap-2 sm:grid-cols-2">
              {suites.map(card => {
                const on = card.id in selected
                const sizes = (card.sampleSizes || []).filter(
                  n => !card.questionCount || n <= card.questionCount
                )
                const sampleChoices =
                  sizes.length > 0
                    ? sizes
                    : card.defaultSampleSize
                      ? [card.defaultSampleSize]
                      : []
                return (
                  <button
                    key={card.id}
                    type="button"
                    disabled={!card.available}
                    onClick={() => toggleSuite(card)}
                    className={cn(
                      'rounded-md border p-3 text-left transition-colors',
                      on
                        ? 'border-border bg-muted/50'
                        : 'border-border/60 hover:bg-muted/20',
                      !card.available && 'opacity-50'
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
                      <div className="flex shrink-0 items-center gap-1">
                        <button
                          type="button"
                          title="Copy CLI command"
                          aria-label={`Copy CLI for ${card.title}`}
                          disabled={!card.available}
                          onClick={e => {
                            e.stopPropagation()
                            void copyCli(card)
                          }}
                          className="text-muted-foreground hover:text-foreground hover:bg-muted inline-flex size-7 items-center justify-center rounded-md"
                        >
                          {copiedId === card.id ? (
                            <Check className="size-3.5 text-emerald-600" />
                          ) : (
                            <Copy className="size-3.5" />
                          )}
                        </button>
                        {on ? (
                          <Check className="text-foreground size-4" />
                        ) : null}
                      </div>
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
                      {sampleChoices.length ? (
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
                            value={
                              selected[card.id] ??
                              card.defaultSampleSize ??
                              sampleChoices[0]
                            }
                            onChange={e => {
                              const n = Number(e.target.value)
                              setSelected(prev => ({ ...prev, [card.id]: n }))
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
                    {!card.available && card.unavailableReason ? (
                      <p className="text-destructive mt-1.5 text-[11px]">
                        {card.unavailableReason}
                      </p>
                    ) : null}
                  </button>
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
                              {r.benchmark}
                            </h4>
                            <span className="bg-muted text-muted-foreground rounded-md px-1.5 py-0.5 text-[11px]">
                              {r.modelId}
                            </span>
                          </div>
                          <p className="text-muted-foreground mt-0.5 text-xs">
                            {r.correct}/{r.total} · {r.timeS}s
                            {r.thinkingUsed ? ' · thinking' : ''}
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
                          className="text-muted-foreground hover:text-foreground"
                          onClick={() => navigate(`/projects/${r.projectId}`)}
                        >
                          Open project
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
              </div>
              <Button
                type="button"
                size="sm"
                disabled={spawning || !selectedCount || !primaryModel}
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
      ) : null}
    </div>
  )
}
