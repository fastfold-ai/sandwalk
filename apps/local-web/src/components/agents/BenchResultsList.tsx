import type {
  BenchProgress,
  BenchQueueItem,
  BenchResultSummary,
  BenchSuiteCard,
  LocalAgentClient
} from '@sandwalk/agent-local-client'
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronsUpDown,
  Clock,
  Columns2,
  Cpu,
  Download,
  ExternalLink,
  Gauge,
  Loader,
  MoreHorizontal,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Tag,
  Target,
  Trash2
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { formatTokenCount } from '@/components/agents/usage-overview-utils'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList
} from '@/components/ui/command'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { TooltipProvider } from '@/components/ui/tooltip'
import { benchExportFilename } from '@/lib/bench-export-name'
import { formatModelEffortBadge } from '@/lib/composer-models'
import { cn } from '@/lib/utils'
import { buildZipStore } from '@/lib/zip-store'

const ROW_GRID =
  'grid grid-cols-[24px_minmax(0,1fr)_10.75rem_6.25rem_4.75rem_10.5rem_2rem] items-center gap-x-3'

const PACK_DISPLAY_TITLES: Record<string, string> = {
  'bio-capybara-full': 'Bio-Capybara-full',
  'skills-mcp-bakeoff': 'Bio-Capybara-full'
}

const STATUS_OPTIONS = [
  { id: 'running', label: 'Running', tone: 'bg-blue-500', preview: 'bg-blue-500/70' },
  { id: 'queued', label: 'Queued', tone: 'bg-yellow-500', preview: 'bg-yellow-500/70' },
  { id: 'paused', label: 'Paused', tone: 'bg-muted-foreground/40', preview: 'bg-muted-foreground/35' },
  { id: 'completed', label: 'Completed', tone: 'bg-emerald-500', preview: 'bg-emerald-500/70' },
  { id: 'interrupted', label: 'Interrupted', tone: 'bg-amber-500', preview: 'bg-amber-500/70' }
] as const

type StatusId = (typeof STATUS_OPTIONS)[number]['id']
type SortId = 'date_desc' | 'date_asc' | 'usage_desc' | 'usage_asc'

const SORT_OPTIONS: { id: SortId; label: string }[] = [
  { id: 'date_desc', label: 'Newest' },
  { id: 'date_asc', label: 'Oldest' },
  { id: 'usage_desc', label: 'Usage high → low' },
  { id: 'usage_asc', label: 'Usage low → high' }
]

const ALL_STATUS_IDS: StatusId[] = STATUS_OPTIONS.map(item => item.id)

function statusTone(status: string): string {
  const key = status.toLowerCase()
  if (key === 'running') return 'bg-blue-500'
  if (key === 'queued') return 'bg-yellow-500'
  if (key === 'paused') return 'bg-muted-foreground/40'
  if (key === 'interrupted') return 'bg-amber-500'
  if (key === 'completed' || !key) return 'bg-emerald-500'
  return 'bg-amber-500'
}

function SuiteMark({
  card,
  className
}: {
  card?: BenchSuiteCard
  className?: string
}) {
  const url = (card?.authorAvatar || '').trim()
  if (!url) {
    return (
      <span
        className={cn(
          'bg-muted text-muted-foreground flex size-4 shrink-0 items-center justify-center rounded-sm',
          className
        )}
      >
        <Gauge className="size-3" />
      </span>
    )
  }
  return (
    <img
      src={url}
      alt=""
      className={cn('size-4 shrink-0 rounded-sm object-contain', className)}
    />
  )
}

type ResultRow = BenchResultSummary & {
  lastProgress?: BenchProgress | null
  startedAt?: string | null
  elapsedS?: number | null
}

function suiteTitle(id: string | null | undefined, suites: BenchSuiteCard[]): string {
  if (!id) return ''
  const fromCard = suites.find(card => card.id === id || card.packId === id)?.title
  return fromCard || PACK_DISPLAY_TITLES[id] || id
}

function useNow(active: boolean): number {
  const [nowMs, setNowMs] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    setNowMs(Date.now())
    const id = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [active])
  return nowMs
}

function displayRunSeconds(row: ResultRow, nowMs: number): number {
  const reported = Number(row.timeS) || 0
  const status = (row.status || '').toLowerCase()
  if (status === 'queued') return 0
  if (status === 'running') {
    const base = Number(row.elapsedS)
    const start = row.startedAt ? Date.parse(row.startedAt) : Number.NaN
    if (Number.isFinite(base) && !Number.isNaN(start)) {
      return Math.max(0, base + (nowMs - start) / 1000)
    }
    if (row.createdAt) {
      const created = Date.parse(row.createdAt)
      if (!Number.isNaN(created)) {
        return Math.max(reported, (nowMs - created) / 1000)
      }
    }
  }
  if (status === 'paused' || status === 'interrupted') {
    const frozen = Number(row.elapsedS)
    if (Number.isFinite(frozen) && frozen > 0) return frozen
  }
  return reported
}

function formatRunDuration(seconds: number): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0))
  if (total < 60) return `${total}s`
  const days = Math.floor(total / 86_400)
  const hours = Math.floor((total % 86_400) / 3_600)
  const minutes = Math.floor((total % 3_600) / 60)
  const secs = total % 60
  if (days > 0) return hours > 0 ? `${days}d ${hours}h` : `${days}d`
  if (hours > 0) return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`
  return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`
}

function formatBenchTimestamp(iso?: string | null): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  })
}

function providerLabel(row: ResultRow): string {
  const raw = (row.provider || '').trim()
  if (raw) return prettyProvider(raw)
  const model = row.modelId || ''
  if (model.includes('/')) return prettyProvider(model.split('/')[0])
  return ''
}

function isCompleted(status?: string | null): boolean {
  const value = (status || '').toLowerCase()
  return !value || value === 'completed'
}

function canResumeRow(row: ResultRow): boolean {
  const status = (row.status || '').toLowerCase()
  // Finished runs can still have Retry failed — that is not "interrupted".
  return status === 'paused' || status === 'interrupted'
}

function canSelectRow(row: ResultRow): boolean {
  return (row.status || '').toLowerCase() !== 'queued'
}

function jobBarPct(progress?: BenchProgress | null): number {
  if (!progress?.benchTotal || progress.benchTotal <= 0) return 0
  return Math.min(
    100,
    Math.round(((progress.benchCurrent || 0) / progress.benchTotal) * 100)
  )
}

function queueItemToRow(
  job: BenchQueueItem,
  status: 'queued' | 'running' | 'paused',
  existing?: BenchResultSummary
): ResultRow {
  const progress = job.lastProgress
  return {
    runId: job.runId,
    modelId: job.modelId || existing?.modelId || '',
    benchmark: job.suites?.[0] || existing?.benchmark || '',
    accuracy: existing?.accuracy ?? 0,
    correct: progress?.benchCurrent ?? existing?.correct ?? 0,
    total: progress?.benchTotal ?? existing?.total ?? 0,
    timeS: existing?.timeS ?? job.elapsedS ?? 0,
    startedAt: job.startedAt || null,
    elapsedS: job.elapsedS ?? existing?.timeS ?? 0,
    thinkingUsed: existing?.thinkingUsed,
    projectId: existing?.projectId,
    createdAt: existing?.createdAt || job.startedAt || null,
    status,
    reasoningEffort: existing?.reasoningEffort,
    reasoningFast: existing?.reasoningFast,
    name: existing?.name,
    provider: job.provider || existing?.provider || null,
    lifetimeTokens: existing?.lifetimeTokens,
    failedCount: existing?.failedCount,
    lastProgress: progress ?? null
  }
}

function mergeResultRows(
  results: BenchResultSummary[],
  inflight: BenchQueueItem[],
  queued: BenchQueueItem[],
  paused: BenchQueueItem[]
): ResultRow[] {
  const byId = new Map(results.map(row => [row.runId, row]))
  const seen = new Set<string>()
  const live: ResultRow[] = []
  const push = (
    job: BenchQueueItem,
    status: 'queued' | 'running' | 'paused'
  ) => {
    if (seen.has(job.runId)) return
    seen.add(job.runId)
    live.push(queueItemToRow(job, status, byId.get(job.runId)))
  }
  for (const job of inflight) push(job, 'running')
  for (const job of queued) push(job, 'queued')
  for (const job of paused) push(job, 'paused')
  // Trust the API for stored rows. Remapping leftover `running` → interrupted
  // here raced the live overlay and showed Interrupted while the detail page
  // (which polls /active itself) still said Running.
  const rest = results.filter(row => !seen.has(row.runId))
  return [...live, ...rest]
}

function matchesFilters(
  row: ResultRow,
  q: string,
  suite: string,
  statuses: Set<string>,
  providers: Set<string>
): boolean {
  if (suite && row.benchmark !== suite) return false
  const statusKey = (row.status || '').toLowerCase()
  const normalized = isCompleted(statusKey) ? 'completed' : statusKey
  if (statuses.size && statuses.size < ALL_STATUS_IDS.length) {
    if (!statuses.has(normalized)) return false
  }
  if (providers.size) {
    const have = (row.provider || '').trim().toLowerCase()
    if (!have || !providers.has(have)) return false
  }
  if (q) {
    const hay = [
      row.name,
      row.modelId,
      row.provider,
      row.benchmark,
      row.runId
    ]
      .join(' ')
      .toLowerCase()
    if (!hay.includes(q.toLowerCase())) return false
  }
  return true
}

function createdMs(row: ResultRow): number {
  const raw = Date.parse(row.createdAt || '')
  return Number.isFinite(raw) ? raw : 0
}

function liveRank(row: ResultRow): number {
  const status = (row.status || '').toLowerCase()
  // Only pin the active queue so Newest/Oldest stay chronological.
  // Paused leftovers would otherwise sit above newer completed runs.
  if (status === 'running') return 0
  if (status === 'queued') return 1
  return 2
}

function rowDateMs(row: ResultRow): number {
  return createdMs(row) || Date.parse(row.startedAt || '') || 0
}

function sortResultRows(rows: ResultRow[], sort: SortId): ResultRow[] {
  const copy = [...rows]
  copy.sort((a, b) => {
    const live = liveRank(a) - liveRank(b)
    if (live !== 0) return live
    if (sort === 'usage_desc' || sort === 'usage_asc') {
      const delta = (b.lifetimeTokens || 0) - (a.lifetimeTokens || 0)
      return sort === 'usage_desc' ? delta : -delta
    }
    const delta = rowDateMs(b) - rowDateMs(a)
    return sort === 'date_asc' ? -delta : delta
  })
  return copy
}

function prettyProvider(id: string): string {
  const raw = id.trim()
  if (!raw) return 'Unknown'
  const key = raw.toLowerCase()
  if (key === 'openai') return 'OpenAI'
  if (key === 'openai-chatgpt') return 'ChatGPT plan'
  if (key === 'openai_compatible' || key === 'openai-compatible') {
    return 'OpenAI-compatible'
  }
  if (key === 'omlx') return 'oMLX'
  if (key === 'unsloth') return 'Unsloth'
  if (key === 'ollama') return 'Ollama'
  if (key === 'llama_cpp' || key === 'llamacpp') return 'llama.cpp'
  if (key === 'lm_studio' || key === 'lmstudio') return 'LM Studio'
  if (key === 'ds4') return 'DS4'
  if (key === 'openrouter') return 'OpenRouter'
  if (key === 'cerebras') return 'Cerebras'
  if (key === 'groq') return 'Groq'
  if (key === 'fireworks') return 'Fireworks AI'
  if (key === 'meta') return 'Meta (Muse)'
  if (key === 'bedrock') return 'Amazon Bedrock'
  if (key === 'deepseek') return 'DeepSeek'
  return raw.charAt(0).toUpperCase() + raw.slice(1)
}

export function BenchResultsList({
  client,
  suites,
  inflightJobs,
  queuedJobs,
  pausedJobs,
  busy,
  resumingId,
  onResume,
  onRetryFailed,
  onPause,
  onCancel
}: {
  client: LocalAgentClient
  suites: BenchSuiteCard[]
  inflightJobs: BenchQueueItem[]
  queuedJobs: BenchQueueItem[]
  pausedJobs: BenchQueueItem[]
  busy: boolean
  resumingId: string | null
  onResume: (runId: string) => void
  onRetryFailed: (runId: string) => void
  onPause: (runId: string) => void
  onCancel: (runId: string) => void
}) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [suite, setSuite] = useState('all')
  const [suiteOpen, setSuiteOpen] = useState(false)
  const [selectedStatuses, setSelectedStatuses] = useState<Set<StatusId>>(
    () => new Set(ALL_STATUS_IDS)
  )
  const [selectedProviders, setSelectedProviders] = useState<Set<string>>(
    () => new Set()
  )
  const [knownProviders, setKnownProviders] = useState<string[]>([])
  const [sort, setSort] = useState<SortId>('date_desc')
  const [rows, setRows] = useState<BenchResultSummary[]>([])
  const [total, setTotal] = useState(0)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [batchBusy, setBatchBusy] = useState(false)
  const debounceRef = useRef<number | null>(null)
  const lastSelectRef = useRef<string | null>(null)

  useEffect(() => {
    if (debounceRef.current != null) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => {
      setDebouncedQuery(query.trim())
    }, 250)
    return () => {
      if (debounceRef.current != null) window.clearTimeout(debounceRef.current)
    }
  }, [query])

  const fetchPage = useCallback(
    async (cursor?: string | null, append = false) => {
      if (append) setLoadingMore(true)
      else setLoading(true)
      try {
        const page = await client.listBenchResults({
          q: debouncedQuery || undefined,
          suite: suite === 'all' ? undefined : suite,
          status:
            selectedStatuses.size && selectedStatuses.size < ALL_STATUS_IDS.length
              ? [...selectedStatuses].join(',')
              : undefined,
          provider: selectedProviders.size
            ? [...selectedProviders].join(',')
            : undefined,
          sort,
          cursor: cursor || undefined,
          limit: 25
        })
        setRows(prev => (append ? [...prev, ...page.data] : page.data))
        setNextCursor(page.nextCursor || null)
        setTotal(page.total)
        if (page.providers.length) {
          setKnownProviders(page.providers)
        }
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [client, debouncedQuery, suite, selectedStatuses, selectedProviders, sort]
  )

  useEffect(() => {
    void fetchPage(null, false)
  }, [fetchPage])

  useEffect(() => {
    if (!busy) return
    const timer = window.setInterval(() => {
      void fetchPage(null, false)
    }, 4000)
    return () => window.clearInterval(timer)
  }, [busy, fetchPage])

  const listRows = useMemo(() => {
    const merged = mergeResultRows(rows, inflightJobs, queuedJobs, pausedJobs)
    return sortResultRows(
      merged.filter(row =>
        matchesFilters(
          row,
          debouncedQuery,
          suite === 'all' ? '' : suite,
          selectedStatuses,
          selectedProviders
        )
      ),
      sort
    )
  }, [
    rows,
    inflightJobs,
    queuedJobs,
    pausedJobs,
    debouncedQuery,
    suite,
    selectedStatuses,
    selectedProviders,
    sort
  ])

  const liveExtra = Math.max(0, listRows.length - rows.length)
  const shownTotal = total + liveExtra
  const nowMs = useNow(listRows.some(row => (row.status || '').toLowerCase() === 'running'))

  const selectableRows = listRows.filter(canSelectRow)
  const selectedRows = listRows.filter(row => selectedIds.includes(row.runId))

  const toggleSelected = (
    runId: string,
    selectable: boolean,
    opts?: { shift?: boolean; additive?: boolean }
  ) => {
    if (!selectable) return
    const ids = selectableRows.map(row => row.runId)
    if (opts?.shift && lastSelectRef.current) {
      const from = ids.indexOf(lastSelectRef.current)
      const to = ids.indexOf(runId)
      if (from >= 0 && to >= 0) {
        const [lo, hi] = from < to ? [from, to] : [to, from]
        const range = ids.slice(lo, hi + 1)
        setSelectedIds(current => {
          const next = new Set(opts.additive ? current : [])
          for (const id of range) next.add(id)
          return [...next]
        })
        lastSelectRef.current = runId
        return
      }
    }
    setSelectedIds(current =>
      current.includes(runId)
        ? current.filter(id => id !== runId)
        : [...current, runId]
    )
    lastSelectRef.current = runId
  }

  const openCompare = () => {
    if (selectedIds.length < 2) return
    const query = selectedIds
      .map(id => `id=${encodeURIComponent(id)}`)
      .join('&')
    navigate(`/dashboard/bench/compare?${query}`)
  }

  const triggerDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadSelectedZip = async () => {
    const ids = selectedIds
    if (!ids.length) return
    setBatchBusy(true)
    try {
      const files = []
      for (const id of ids) {
        const row = selectedRows.find(item => item.runId === id)
        const file = await client.downloadBenchExport(id)
        files.push({
          name: benchExportFilename(row?.modelId, row?.benchmark),
          data: new Uint8Array(await file.blob.arrayBuffer())
        })
      }
      triggerDownload(
        buildZipStore(files),
        `bench-results-${ids.length}.zip`
      )
      toast.success(`Downloaded ${ids.length} result${ids.length === 1 ? '' : 's'}`)
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Unable to download results'
      )
    } finally {
      setBatchBusy(false)
    }
  }

  const retrySelected = async () => {
    const ids = selectedRows
      .filter(row => {
        const status = (row.status || '').toLowerCase()
        return status !== 'running' && status !== 'queued'
      })
      .map(row => row.runId)
    if (!ids.length) return
    setBatchBusy(true)
    try {
      for (const id of ids) onRetryFailed(id)
      toast.success(`Retry queued for ${ids.length} run${ids.length === 1 ? '' : 's'}`)
    } finally {
      setBatchBusy(false)
    }
  }

  const resumeSelected = () => {
    const ids = selectedRows.filter(canResumeRow).map(row => row.runId)
    for (const id of ids) onResume(id)
  }

  const pauseSelected = () => {
    const ids = selectedRows
      .filter(row => (row.status || '').toLowerCase() === 'running')
      .map(row => row.runId)
    for (const id of ids) onPause(id)
  }

  const removeSelected = async () => {
    const ids = [...selectedIds]
    if (!ids.length) return
    setBatchBusy(true)
    try {
      for (const id of ids) {
        const row = selectedRows.find(item => item.runId === id)
        const status = (row?.status || '').toLowerCase()
        if (status === 'running' || status === 'queued' || status === 'paused') {
          onCancel(id)
        } else {
          await client.deleteBenchResult(id)
        }
      }
      setSelectedIds([])
      void fetchPage(null, false)
      toast.success(`Removed ${ids.length} run${ids.length === 1 ? '' : 's'}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Unable to remove runs')
    } finally {
      setBatchBusy(false)
    }
  }

  const selectedSuite = suites.find(
    card => card.id === suite || card.packId === suite
  )
  const statusSelectedCount = selectedStatuses.size
  const statusTotalCount = ALL_STATUS_IDS.length

  const toggleStatus = (id: StatusId) => {
    setSelectedStatuses(prev => {
      if (prev.size === ALL_STATUS_IDS.length && prev.has(id)) {
        return new Set([id])
      }
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      if (next.size === 0) return new Set(ALL_STATUS_IDS)
      return next
    })
  }

  const toggleProvider = (id: string) => {
    setSelectedProviders(prev => {
      const current = prev.size ? prev : new Set(knownProviders)
      if (current.size === knownProviders.length && current.has(id)) {
        return new Set([id])
      }
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      if (!next.size || next.size === knownProviders.length) return new Set()
      return next
    })
  }

  const providerSelectedCount = selectedProviders.size || knownProviders.length
  const sortLabel =
    SORT_OPTIONS.find(item => item.id === sort)?.label || 'Newest'

  const headerSortButton = (
    column: 'usage' | 'date',
    label: string
  ) => {
    const active =
      column === 'usage'
        ? sort === 'usage_desc' || sort === 'usage_asc'
        : sort === 'date_desc' || sort === 'date_asc'
    const Icon =
      column === 'usage'
        ? sort === 'usage_asc'
          ? ArrowUp
          : ArrowDown
        : sort === 'date_asc'
          ? ArrowUp
          : ArrowDown
    return (
      <button
        type="button"
        className={cn(
          'inline-flex items-center gap-1 hover:text-foreground',
          active ? 'text-foreground' : ''
        )}
        onClick={() => {
          if (column === 'usage') {
            setSort(sort === 'usage_desc' ? 'usage_asc' : 'usage_desc')
            return
          }
          setSort(sort === 'date_desc' ? 'date_asc' : 'date_desc')
        }}
      >
        {label}
        {active ? <Icon className="size-3" /> : null}
      </button>
    )
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto">
        <div className="relative min-w-32 max-w-44 flex-1">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
          <Input
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Search"
            className="h-9 pl-9"
          />
        </div>
        <Popover open={suiteOpen} onOpenChange={setSuiteOpen}>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              role="combobox"
              aria-expanded={suiteOpen}
              className="h-9 max-w-[180px] shrink-0 justify-between"
            >
              <span className="inline-flex min-w-0 items-center gap-2">
                {suite === 'all' ? (
                  <Tag className="text-muted-foreground size-4 shrink-0" />
                ) : (
                  <SuiteMark card={selectedSuite} />
                )}
                <span className="truncate">
                  {suite === 'all'
                    ? 'All suites'
                    : suiteTitle(suite, suites) || suite}
                </span>
              </span>
              <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[320px] p-0" align="start">
            <Command loop>
              <CommandInput placeholder="Search suites..." />
              <CommandList className="max-h-[320px]">
                <CommandEmpty>No suites found.</CommandEmpty>
                <CommandGroup>
                  <CommandItem
                    value="all suites"
                    onSelect={() => {
                      setSuite('all')
                      setSuiteOpen(false)
                    }}
                  >
                    <span className="inline-flex items-center gap-2">
                      <Tag className="text-muted-foreground size-4" />
                      All suites
                    </span>
                    <Check
                      className={cn(
                        'ml-auto size-4',
                        suite === 'all' ? 'opacity-100' : 'opacity-0'
                      )}
                    />
                  </CommandItem>
                  {suites.map(card => (
                    <CommandItem
                      key={card.id}
                      value={`${card.title || card.id} ${card.id}`}
                      onSelect={() => {
                        setSuite(card.id)
                        setSuiteOpen(false)
                      }}
                    >
                      <span className="inline-flex min-w-0 items-center gap-2">
                        <SuiteMark card={card} />
                        <span className="truncate">{card.title || card.id}</span>
                      </span>
                      <Check
                        className={cn(
                          'ml-auto size-4',
                          suite === card.id ? 'opacity-100' : 'opacity-0'
                        )}
                      />
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className="h-9 shrink-0 justify-between px-3"
            >
              <span className="flex min-w-0 items-center gap-2">
                <span className="flex items-center">
                  {STATUS_OPTIONS.map((opt, idx) => (
                    <span
                      key={opt.id}
                      className={cn(
                        'h-2.5 w-2.5 rounded-full border border-muted-foreground/30',
                        idx === 0 ? '' : '-ml-1',
                        selectedStatuses.has(opt.id) ? opt.preview : 'bg-muted'
                      )}
                    />
                  ))}
                </span>
                <span className="text-muted-foreground">Status</span>
                <span className="bg-muted rounded-full px-2 py-0.5 text-xs font-normal">
                  {statusSelectedCount}/{statusTotalCount}
                </span>
              </span>
              <ChevronDown className="ml-2 size-4 shrink-0 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-[240px] p-2">
            <DropdownMenuLabel className="px-2 py-1.5">
              <div className="flex items-center justify-between gap-3">
                <span>Status</span>
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground text-xs"
                  onClick={event => {
                    event.preventDefault()
                    setSelectedStatuses(new Set(ALL_STATUS_IDS))
                  }}
                >
                  Check All
                </button>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {STATUS_OPTIONS.map(opt => (
              <DropdownMenuCheckboxItem
                key={opt.id}
                checked={selectedStatuses.has(opt.id)}
                onSelect={event => event.preventDefault()}
                onCheckedChange={() => toggleStatus(opt.id)}
                className="flex items-center"
              >
                <span
                  className={cn(
                    'mr-2 inline-block h-3 w-3 rounded-full',
                    opt.tone
                  )}
                />
                <span>{opt.label}</span>
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        {knownProviders.length ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="outline"
                className="h-9 shrink-0 justify-between px-3"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <Cpu className="text-muted-foreground size-4 shrink-0" />
                  <span className="text-muted-foreground">Provider</span>
                  <span className="bg-muted rounded-full px-2 py-0.5 text-xs font-normal">
                    {providerSelectedCount}/{knownProviders.length}
                  </span>
                </span>
                <ChevronDown className="ml-2 size-4 shrink-0 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-[240px] p-2">
              <DropdownMenuLabel className="px-2 py-1.5">
                <div className="flex items-center justify-between gap-3">
                  <span>Provider</span>
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground text-xs"
                    onClick={event => {
                      event.preventDefault()
                      setSelectedProviders(new Set())
                    }}
                  >
                    Check All
                  </button>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {knownProviders.map(id => (
                <DropdownMenuCheckboxItem
                  key={id}
                  checked={!selectedProviders.size || selectedProviders.has(id)}
                  onSelect={event => event.preventDefault()}
                  onCheckedChange={() => toggleProvider(id)}
                >
                  {prettyProvider(id)}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className="h-9 shrink-0 justify-between px-3"
            >
              <span className="flex min-w-0 items-center gap-2">
                <ArrowUpDown className="text-muted-foreground size-4 shrink-0" />
                <span className="truncate">{sortLabel}</span>
              </span>
              <ChevronDown className="ml-2 size-4 shrink-0 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-[220px] p-1">
            {SORT_OPTIONS.map(opt => (
              <DropdownMenuItem
                key={opt.id}
                onSelect={() => setSort(opt.id)}
              >
                {opt.label}
                <Check
                  className={cn(
                    'ml-auto size-4',
                    sort === opt.id ? 'opacity-100' : 'opacity-0'
                  )}
                />
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        </div>
        <div className="flex shrink-0 items-center justify-end gap-1.5">
          {selectedIds.length ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={batchBusy}
                  className="tabular-nums"
                >
                  {batchBusy ? (
                    <Loader className="size-3.5 animate-spin" />
                  ) : (
                    <MoreHorizontal className="size-3.5" />
                  )}
                  {selectedIds.length}
                  <ChevronDown className="size-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem
                  disabled={!selectedIds.length}
                  onSelect={() => void downloadSelectedZip()}
                >
                  <Download className="size-3.5" />
                  Download zip
                </DropdownMenuItem>
                {selectedRows.some(
                  row =>
                    (row.status || '').toLowerCase() !== 'running' &&
                    (row.status || '').toLowerCase() !== 'queued'
                ) ? (
                  <DropdownMenuItem onSelect={() => void retrySelected()}>
                    <RotateCcw className="size-3.5" />
                    Retry failed
                  </DropdownMenuItem>
                ) : null}
                {selectedRows.some(canResumeRow) ? (
                  <DropdownMenuItem onSelect={resumeSelected}>
                    <Play className="size-3.5" />
                    Resume
                  </DropdownMenuItem>
                ) : null}
                {selectedRows.some(
                  row => (row.status || '').toLowerCase() === 'running'
                ) ? (
                  <DropdownMenuItem onSelect={pauseSelected}>
                    <Pause className="size-3.5" />
                    Pause
                  </DropdownMenuItem>
                ) : null}
                <DropdownMenuItem onSelect={() => setSelectedIds([])}>
                  Clear selection
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-red-600"
                  onSelect={() => void removeSelected()}
                >
                  <Trash2 className="size-3.5" />
                  Remove
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={loading}
            aria-label="Refresh"
            onClick={() => void fetchPage(null, false)}
          >
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={selectedIds.length < 2}
            onClick={openCompare}
          >
            <Columns2 className="size-3.5" />
            Compare
          </Button>
        </div>
      </div>
      <TooltipProvider delayDuration={250}>
      <div className="divide-border/70 border-border/70 divide-y rounded-md border">
        {listRows.length ? (
          <div
            className={cn(
              ROW_GRID,
              'text-muted-foreground px-3 py-1.5 text-[11px] font-medium md:px-4'
            )}
          >
            <span />
            <span>Run</span>
            <span>Status</span>
            <span>Provider</span>
            <span>{headerSortButton('usage', 'Usage')}</span>
            <span>{headerSortButton('date', 'Date')}</span>
            <span />
          </div>
        ) : null}
        {listRows.map(row => (
          <ResultRowView
            key={row.runId}
            row={row}
            nowMs={nowMs}
            suites={suites}
            picked={selectedIds.includes(row.runId)}
            resuming={resumingId === row.runId}
            onToggleSelect={(opts) =>
              toggleSelected(row.runId, canSelectRow(row), opts)
            }
            onResume={() => onResume(row.runId)}
            onRetryFailed={() => onRetryFailed(row.runId)}
            onPause={() => onPause(row.runId)}
            onRemove={() => {
              const statusKey = (row.status || '').toLowerCase()
              const live =
                statusKey === 'running' ||
                statusKey === 'queued' ||
                statusKey === 'paused'
              const done = () => {
                setSelectedIds(current =>
                  current.filter(id => id !== row.runId)
                )
                void fetchPage(null, false)
              }
              if (live) {
                onCancel(row.runId)
                done()
                return
              }
              void client.deleteBenchResult(row.runId).then(done).catch(() => {
                /* keep row */
              })
            }}
            onOpen={() =>
              navigate(`/dashboard/bench/${encodeURIComponent(row.runId)}`)
            }
            onDownload={() =>
              void client.downloadBenchExport(row.runId).then(file => {
                const url = URL.createObjectURL(file.blob)
                const a = document.createElement('a')
                a.href = url
                a.download = benchExportFilename(row.modelId, row.benchmark)
                a.click()
                URL.revokeObjectURL(url)
              })
            }
            onOpenProject={
              row.projectId
                ? () => navigate(`/projects/${row.projectId}`)
                : undefined
            }
          />
        ))}
        {!listRows.length && !loading ? (
          <div className="text-muted-foreground px-4 py-8 text-center text-sm">
            No runs match these filters.
          </div>
        ) : null}
        {loading && !listRows.length ? (
          <div className="text-muted-foreground flex items-center gap-2 px-4 py-8 text-sm">
            <Loader className="size-3.5 animate-spin" />
            Loading runs…
          </div>
        ) : null}
      </div>
      </TooltipProvider>
      <div className="flex items-center justify-end gap-3">
        {nextCursor ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mr-auto"
            disabled={loadingMore}
            onClick={() => void fetchPage(nextCursor, true)}
          >
            {loadingMore ? (
              <Loader className="size-3.5 animate-spin" />
            ) : null}
            Load more
          </Button>
        ) : null}
        <p className="text-muted-foreground text-xs tabular-nums">
          {shownTotal
            ? `${shownTotal} run${shownTotal === 1 ? '' : 's'}`
            : loading
              ? 'Loading…'
              : 'No runs yet'}
        </p>
      </div>
    </section>
  )
}

function ResultRowView({
  row,
  nowMs,
  suites,
  picked,
  resuming,
  onToggleSelect,
  onResume,
  onRetryFailed,
  onPause,
  onRemove,
  onOpen,
  onDownload,
  onOpenProject
}: {
  row: ResultRow
  nowMs: number
  suites: BenchSuiteCard[]
  picked: boolean
  resuming: boolean
  onToggleSelect: (opts?: { shift?: boolean; additive?: boolean }) => void
  onResume: () => void
  onRetryFailed: () => void
  onPause: () => void
  onRemove: () => void
  onOpen: () => void
  onDownload: () => void
  onOpenProject?: () => void
}) {
  const statusKey = (row.status || '').toLowerCase()
  const paused = canResumeRow(row)
  const running = statusKey === 'running'
  const queued = statusKey === 'queued'
  const completed = isCompleted(statusKey) && !paused
  const pct = Math.round((row.accuracy || 0) * 1000) / 10
  const title = row.name?.trim() || suiteTitle(row.benchmark, suites) || 'Untitled run'
  const provider = providerLabel(row)
  const statusLabel = queued
    ? 'Queued'
    : statusKey === 'paused'
      ? 'Paused'
      : paused
        ? 'Interrupted'
        : running
          ? 'Running'
          : completed
            ? `${pct.toFixed(1)}%`
            : 'Running'
  const barPct = jobBarPct(row.lastProgress)
  const graded = row.lastProgress?.benchCurrent ?? 0
  const total = row.lastProgress?.benchTotal ?? row.total ?? 0
  const inFlight = row.lastProgress?.inFlight || 0
  const done = graded || row.answered || 0
  const progressLabel = running || paused || queued
    ? total
      ? `${done}/${total}`
      : '0/0'
    : completed && row.total
      ? `${row.correct ?? 0}/${row.total}`
      : ''

  return (
    <div
      role={queued ? undefined : 'button'}
      tabIndex={queued ? undefined : 0}
      className={cn(
        'px-3 py-2.5 md:px-4',
        queued ? undefined : 'cursor-pointer',
        picked ? 'bg-primary/[0.04]' : 'hover:bg-muted/30'
      )}
      onClick={event => {
        if (queued) return
        if (event.shiftKey || event.metaKey || event.ctrlKey) {
          event.preventDefault()
          onToggleSelect({
            shift: event.shiftKey,
            additive: event.metaKey || event.ctrlKey || event.shiftKey
          })
          return
        }
        onOpen()
      }}
      onKeyDown={event => {
        if (queued) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen()
        }
      }}
    >
      <div className={ROW_GRID}>
        <button
          type="button"
          disabled={queued}
          aria-label={
            queued
              ? 'Queued runs cannot be selected'
              : picked
                ? 'Deselect run'
                : 'Select run'
          }
          aria-pressed={picked}
          title={
            queued
              ? undefined
              : 'Select · Shift-click a range'
          }
          className="group flex size-6 shrink-0 items-center justify-center"
          onClick={event => {
            event.stopPropagation()
            onToggleSelect({
              shift: event.shiftKey,
              additive: event.metaKey || event.ctrlKey || event.shiftKey
            })
          }}
          onPointerDown={event => event.stopPropagation()}
        >
          <span
            className={cn(
              'flex size-5 items-center justify-center rounded-[5px] transition-transform duration-150 ease-out',
              !queued &&
                'group-hover:scale-110 group-hover:ring-2 group-hover:ring-primary/45 group-hover:ring-offset-1 group-hover:ring-offset-background',
              picked
                ? 'bg-primary text-primary-foreground'
                : queued
                  ? 'bg-muted text-muted-foreground'
                  : running
                    ? 'bg-sky-500/15 text-sky-600 group-hover:bg-primary/15 group-hover:text-primary'
                    : paused
                      ? 'bg-muted text-muted-foreground group-hover:bg-primary/15 group-hover:text-primary'
                      : pct >= 70
                        ? 'bg-emerald-500/15 text-emerald-600 group-hover:bg-primary/15 group-hover:text-primary'
                        : pct >= 40
                          ? 'bg-amber-500/15 text-amber-600 group-hover:bg-primary/15 group-hover:text-primary'
                          : 'bg-red-500/15 text-red-600 group-hover:bg-primary/15 group-hover:text-primary'
            )}
          >
            {picked ? (
              <Check className="size-3" strokeWidth={2.75} />
            ) : queued ? (
              <Clock className="size-3" />
            ) : (
              <>
                <span className="flex group-hover:hidden">
                  {running ? (
                    <Loader className="size-3 animate-spin" />
                  ) : paused ? (
                    <Pause className="size-3" />
                  ) : (
                    <Target className="size-3" />
                  )}
                </span>
                <span
                  aria-hidden
                  className="hidden size-3 rounded-[3px] border-2 border-current group-hover:block"
                />
              </>
            )}
          </span>
        </button>
        <div className="min-w-0">
          <span className="block truncate text-sm font-medium" title={title}>
            {title}
          </span>
          <p className="text-muted-foreground mt-0.5 truncate text-[11px]">
            {row.modelId}
            {row.reasoningEffort || row.reasoningFast != null
              ? ` · ${formatModelEffortBadge({
                  reasoningEffort: row.reasoningEffort || 'medium',
                  reasoningFast: Boolean(row.reasoningFast)
                })}`
              : ''}
            {row.benchmark ? ` · ${suiteTitle(row.benchmark, suites)}` : ''}
          </p>
        </div>
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <span
              className={cn(
                'h-2 w-2 shrink-0 rounded-full',
                statusTone(statusKey)
              )}
            />
            {paused ? (
              <span className="text-foreground/80 text-[13px] font-medium">
                {statusLabel}
              </span>
            ) : running ? (
              <span className="text-foreground/80 text-[13px] font-medium">
                Running
              </span>
            ) : queued ? (
              <span className="text-foreground/80 text-[13px] font-medium">
                Queued
              </span>
            ) : (
              <span
                className={cn(
                  'text-[13px] font-semibold tabular-nums',
                  pct >= 70
                    ? 'text-emerald-600'
                    : pct >= 40
                      ? 'text-amber-600'
                      : 'text-red-600'
                )}
              >
                {statusLabel}
              </span>
            )}
            <span className="text-muted-foreground truncate text-[13px] tabular-nums">
              {formatRunDuration(displayRunSeconds(row, nowMs))}
            </span>
          </div>
          {queued ? (
            <p className="text-muted-foreground mt-0.5 pl-3.5 text-[11px]">
              waiting to start
            </p>
          ) : progressLabel ? (
            <p className="text-muted-foreground mt-0.5 pl-3.5 text-[11px] tabular-nums">
              {progressLabel}
              {inFlight ? ` · ${inFlight} in flight` : ''}
            </p>
          ) : null}
        </div>
        <div className="text-muted-foreground min-w-0 truncate text-left text-[12px]">
          {provider || '—'}
        </div>
        <div
          className="text-muted-foreground min-w-0 truncate text-left text-[12px] tabular-nums"
          title={
            row.lifetimeTokens != null
              ? `${row.lifetimeTokens.toLocaleString()} lifetime usage`
              : undefined
          }
        >
          {row.lifetimeTokens != null
            ? formatTokenCount(row.lifetimeTokens)
            : '—'}
        </div>
        <div className="text-muted-foreground min-w-0 truncate text-left text-[12px] tabular-nums">
          {formatBenchTimestamp(row.createdAt) || '—'}
        </div>
        <div
          className="flex items-center justify-end"
          onClick={event => event.stopPropagation()}
          onPointerDown={event => event.stopPropagation()}
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="size-8 p-0"
                aria-label="Run actions"
              >
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {!queued ? (
                <DropdownMenuItem onClick={onOpen}>View details</DropdownMenuItem>
              ) : null}
              {!running && !queued ? (
                <DropdownMenuItem disabled={resuming} onClick={onRetryFailed}>
                  {resuming ? (
                    <Loader className="size-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="size-3.5" />
                  )}
                  Retry failed
                  {(row.failedCount || 0) > 0 ? ` (${row.failedCount})` : ''}
                </DropdownMenuItem>
              ) : null}
              {onOpenProject ? (
                <DropdownMenuItem onClick={onOpenProject}>
                  <ExternalLink className="size-3.5" />
                  Open project
                </DropdownMenuItem>
              ) : null}
              {!queued ? (
                <DropdownMenuItem onClick={onDownload}>
                  <Download className="size-3.5" />
                  Download
                </DropdownMenuItem>
              ) : null}
              {running ? (
                <DropdownMenuItem onClick={onPause}>
                  <Pause className="size-3.5" />
                  Pause
                </DropdownMenuItem>
              ) : null}
              {paused ? (
                <DropdownMenuItem disabled={resuming} onClick={onResume}>
                  {resuming ? (
                    <Loader className="size-3.5 animate-spin" />
                  ) : (
                    <Play className="size-3.5" />
                  )}
                  Resume
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuItem className="text-red-600" onClick={onRemove}>
                <Trash2 className="size-3.5" />
                Remove
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      {running ? (
        <div className="bg-muted mt-2 h-1 overflow-hidden rounded-full">
          <div
            className="bg-foreground h-full transition-all duration-500"
            style={{ width: `${Math.max(barPct, 4)}%` }}
          />
        </div>
      ) : null}
    </div>
  )
}
