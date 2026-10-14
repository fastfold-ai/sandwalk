import type {
  BenchActiveStatus,
  BenchSuiteCard,
  LocalAgentClient
} from '@sandwalk/agent-local-client'
import { ArrowLeft, Check, ChevronDown, ChevronRight, Download, ExternalLink, Loader, Pencil, Play, RotateCcw, Target, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { DetailStickyNav } from '@/components/agents/detail-sticky-nav'
import { formatTokenCount } from '@/components/agents/usage-overview-utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { benchExportFilename } from '@/lib/bench-export-name'
import { cn } from '@/lib/utils'

const PACK_DISPLAY_TITLES: Record<string, string> = {
  'bio-capybara-full': 'Bio-Capybara-full',
  'skills-mcp-bakeoff': 'Bio-Capybara-full'
}

function suiteTitle(id: string | null | undefined, suites: BenchSuiteCard[]): string {
  if (!id) return ''
  const fromCard = suites.find(card => card.id === id || card.packId === id)?.title
  return fromCard || PACK_DISPLAY_TITLES[id] || id
}

function prettyProvider(id: string): string {
  const raw = id.trim()
  if (!raw) return ''
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

type BenchQuestion = {
  id?: string
  question_id?: string
  questionId?: string
  correct?: boolean
  expected?: string
  predicted?: string
  question?: string
  raw_response?: string
  rawResponse?: string
  category?: string
  session_id?: string
  sessionId?: string
  eval_mode?: string
  evalMode?: string
  judge?: {
    overall_pass?: boolean
    overallPass?: boolean
    error?: string
    predicted?: string
    items?: Array<{
      id?: string
      pass?: boolean
      reason?: string
    }>
  } | null
  tools_seen?: string[]
  toolsSeen?: string[]
  heuristics?: Record<string, boolean>
  skipped?: boolean
  terminal?: boolean
}

function isRetryableFailure(q: BenchQuestion): boolean {
  if (q.skipped || q.terminal) return true
  const mode = String(q.eval_mode || q.evalMode || '')
  if (mode === 'error') return true
  const err = String(q.judge?.error || '').trim()
  if (err) return true
  const blob = `${err} ${q.raw_response || q.rawResponse || ''} ${q.predicted || ''}`.toLowerCase()
  return (
    blob.includes('rate limit') ||
    blob.includes('429') ||
    blob.includes('overloaded') ||
    blob.includes('stalled') ||
    blob.includes('timed out') ||
    blob.includes('nodename nor servname')
  )
}

function pctClass(pct: number) {
  if (pct >= 70) return 'text-emerald-600'
  if (pct >= 40) return 'text-amber-600'
  return 'text-red-600'
}

function pctBg(pct: number) {
  if (pct >= 70) return 'bg-emerald-500/15 text-emerald-600'
  if (pct >= 40) return 'bg-amber-500/15 text-amber-600'
  return 'bg-red-500/15 text-red-600'
}

function asQuestions(detail: Record<string, unknown> | null): BenchQuestion[] {
  const rows = detail?.questions
  return Array.isArray(rows) ? (rows as BenchQuestion[]) : []
}

function categoryScores(
  detail: Record<string, unknown> | null
): Array<[string, number]> {
  const raw =
    (detail?.categoryScores as Record<string, number> | undefined) ||
    (detail?.category_scores as Record<string, number> | undefined) ||
    {}
  return Object.entries(raw).sort((a, b) => a[0].localeCompare(b[0]))
}

type BenchEnvironment = {
  captured_at?: string
  started_at?: string
  sandwalk_version?: string
  python_version?: string
  python_implementation?: string
  platform?: string
  arch?: string
  os_version?: string
  packages?: Record<string, string>
  model?: {
    provider?: string | null
    model_id?: string | null
    specialist_id?: string | null
    thinking?: boolean
  }
  runtime?: Record<string, unknown>
  sandbox?: Record<string, unknown>
  skills?: Array<{
    name?: string
    version?: string | null
    source?: string
    enabled?: boolean
    commit?: string | null
  }>
  mcp_servers?: Array<{
    id?: string
    name?: string
    transport?: string
    catalog_id?: string | null
    enabled?: boolean
  }>
  suite?: {
    suite_id?: string | null
    sample_size?: number | null
    pack_id?: string | null
    matrix?: string | null
  }
  error?: string
}

function asEnvironment(
  detail: Record<string, unknown> | null
): BenchEnvironment | null {
  const raw = detail?.environment
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  return raw as BenchEnvironment
}

function formatStartedAt(value: string | undefined | null) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
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

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-3 text-sm">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="truncate text-right font-medium">{value}</span>
    </div>
  )
}

function BenchEnvironmentPanel({ env }: { env: BenchEnvironment }) {
  const [open, setOpen] = useState(false)
  const skills = env.skills || []
  const mcps = env.mcp_servers || []
  const packages = Object.entries(env.packages || {})
  const enabledSkills = skills.filter(s => s.enabled !== false)
  const enabledMcps = mcps.filter(m => m.enabled !== false)
  const started =
    formatStartedAt(env.started_at || env.captured_at) ||
    env.started_at ||
    env.captured_at
  const platformLabel = [env.platform, env.arch].filter(Boolean).join(' ')
  const runtime = env.runtime || {}
  const sandbox = env.sandbox || {}
  const model = env.model || {}

  return (
    <section className="border-border/60 rounded-lg border">
      <button
        type="button"
        className="hover:bg-muted/30 flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors"
        onClick={() => setOpen(current => !current)}
      >
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">Environment</h2>
          <p className="text-muted-foreground mt-0.5 truncate text-xs">
            {[
              started ? `Started ${started}` : null,
              env.sandwalk_version ? `sandwalk ${env.sandwalk_version}` : null,
              env.python_version ? `Python ${env.python_version}` : null,
              model.provider || null,
              runtime.tool_mode ? `tool_mode=${String(runtime.tool_mode)}` : null,
              sandbox.backend ? `sandbox=${String(sandbox.backend)}` : null,
              `${enabledSkills.length} skills`,
              `${enabledMcps.length} MCPs`
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
        {open ? (
          <ChevronDown className="text-muted-foreground size-4 shrink-0" />
        ) : (
          <ChevronRight className="text-muted-foreground size-4 shrink-0" />
        )}
      </button>
      {open ? (
        <div className="border-border/60 space-y-4 border-t px-4 py-4">
          {env.error ? (
            <p className="text-destructive text-xs">{env.error}</p>
          ) : null}
          <div className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
            {started ? <MetaRow label="Started" value={started} /> : null}
            {env.sandwalk_version ? (
              <MetaRow label="Sandwalk" value={env.sandwalk_version} />
            ) : null}
            {env.python_version ? (
              <MetaRow
                label="Python"
                value={[env.python_implementation, env.python_version]
                  .filter(Boolean)
                  .join(' ')}
              />
            ) : null}
            {platformLabel ? (
              <MetaRow
                label="Platform"
                value={[platformLabel, env.os_version].filter(Boolean).join(' · ')}
              />
            ) : null}
            {model.provider || model.model_id ? (
              <MetaRow
                label="Model"
                value={[model.provider, model.model_id].filter(Boolean).join(' / ')}
              />
            ) : null}
            {model.specialist_id ? (
              <MetaRow label="Specialist" value={String(model.specialist_id)} />
            ) : null}
            {typeof model.thinking === 'boolean' ? (
              <MetaRow label="Thinking" value={model.thinking ? 'on' : 'off'} />
            ) : null}
            {runtime.tool_mode != null ? (
              <MetaRow label="Tool mode" value={String(runtime.tool_mode)} />
            ) : null}
            {runtime.knowledge_level != null ? (
              <MetaRow
                label="Knowledge"
                value={String(runtime.knowledge_level)}
              />
            ) : null}
            {runtime.reasoning_effort != null ? (
              <MetaRow
                label="Reasoning"
                value={String(runtime.reasoning_effort)}
              />
            ) : null}
            {runtime.file_access != null ? (
              <MetaRow label="File access" value={String(runtime.file_access)} />
            ) : null}
            {runtime.max_sdk_turns != null ? (
              <MetaRow
                label="Max turns"
                value={String(runtime.max_sdk_turns)}
              />
            ) : null}
            {sandbox.backend != null ? (
              <MetaRow
                label="Sandbox"
                value={[sandbox.backend, sandbox.compute_type]
                  .filter(Boolean)
                  .join(' / ')}
              />
            ) : null}
            {env.suite?.suite_id ? (
              <MetaRow
                label="Suite"
                value={[
                  env.suite.suite_id,
                  env.suite.sample_size != null
                    ? `n=${env.suite.sample_size}`
                    : null
                ]
                  .filter(Boolean)
                  .join(' · ')}
              />
            ) : null}
          </div>

          {packages.length ? (
            <div>
              <h3 className="mb-2 text-xs font-medium tracking-wide uppercase">
                Packages
              </h3>
              <div className="grid gap-1 sm:grid-cols-2">
                {packages.map(([name, version]) => (
                  <div
                    key={name}
                    className="text-muted-foreground flex justify-between gap-2 font-mono text-[11px]"
                  >
                    <span className="truncate">{name}</span>
                    <span className="shrink-0 tabular-nums">{version}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {skills.length ? (
            <div>
              <h3 className="mb-2 text-xs font-medium tracking-wide uppercase">
                Skills · {enabledSkills.length} enabled / {skills.length}
              </h3>
              <div className="max-h-40 space-y-1 overflow-y-auto">
                {skills.map(skill => (
                  <div
                    key={`${skill.name}-${skill.source}`}
                    className="flex items-center justify-between gap-2 text-xs"
                  >
                    <span
                      className={cn(
                        'truncate',
                        skill.enabled === false && 'text-muted-foreground line-through'
                      )}
                    >
                      {skill.name}
                      {skill.version ? (
                        <span className="text-muted-foreground">
                          {' '}
                          {skill.version}
                        </span>
                      ) : null}
                    </span>
                    <span className="text-muted-foreground shrink-0">
                      {skill.source || '—'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {mcps.length ? (
            <div>
              <h3 className="mb-2 text-xs font-medium tracking-wide uppercase">
                MCPs · {enabledMcps.length} enabled / {mcps.length}
              </h3>
              <div className="max-h-40 space-y-1 overflow-y-auto">
                {mcps.map(server => (
                  <div
                    key={server.id || server.name}
                    className="flex items-center justify-between gap-2 text-xs"
                  >
                    <span
                      className={cn(
                        'truncate',
                        server.enabled === false &&
                          'text-muted-foreground line-through'
                      )}
                    >
                      {server.name}
                    </span>
                    <span className="text-muted-foreground shrink-0">
                      {server.transport || '—'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

function liveStatusForRun(
  runId: string,
  active: BenchActiveStatus | null
): string | null {
  if (!active) return null
  if (
    (active.inflight ?? []).some(job => job.runId === runId) ||
    (active.running && active.currentRunId === runId)
  ) {
    return 'running'
  }
  if ((active.queue ?? []).some(job => job.runId === runId)) return 'queued'
  if ((active.paused ?? []).some(job => job.runId === runId)) return 'paused'
  return null
}

export function BenchResultDetail({
  client,
  runId,
  suites = []
}: {
  client: LocalAgentClient
  runId: string
  suites?: BenchSuiteCard[]
}) {
  const navigate = useNavigate()
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [liveStatus, setLiveStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [openId, setOpenId] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'pass' | 'fail'>('all')
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [visibleCount, setVisibleCount] = useState(40)
  const [resuming, setResuming] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draftName, setDraftName] = useState('')
  const editingRef = useRef(false)
  const PAGE = 40

  useEffect(() => {
    editingRef.current = editing
  }, [editing])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setVisibleCount(PAGE)
    setOpenId(null)
    const load = (initial: boolean) => {
      void Promise.all([
        client.getBenchResult(runId),
        client.getBenchActive().catch(() => null)
      ])
        .then(([row, active]) => {
          if (cancelled) return
          setDetail(current => {
            if (editingRef.current && current) {
              return { ...row, name: current.name }
            }
            return row
          })
          setLiveStatus(liveStatusForRun(runId, active))
        })
        .catch(err => {
          if (cancelled) return
          if (initial) {
            setError(
              err instanceof Error ? err.message : 'Unable to load result'
            )
            setDetail(null)
          }
        })
        .finally(() => {
          if (!cancelled && initial) setLoading(false)
        })
    }
    load(true)
    const id = window.setInterval(() => load(false), 1500)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [client, runId])

  const questions = useMemo(() => asQuestions(detail), [detail])
  const failedCount = useMemo(
    () => questions.filter(isRetryableFailure).length,
    [questions]
  )
  const categories = useMemo(() => categoryScores(detail), [detail])
  const environment = useMemo(() => asEnvironment(detail), [detail])
  const filtered = useMemo(() => {
    const byCategory = categoryFilter
      ? questions.filter(q => (q.category || '') === categoryFilter)
      : questions
    if (filter === 'pass') return byCategory.filter(q => q.correct)
    if (filter === 'fail') return byCategory.filter(q => !q.correct)
    return byCategory
  }, [categoryFilter, filter, questions])
  const visible = useMemo(
    () => filtered.slice(0, visibleCount),
    [filtered, visibleCount]
  )

  useEffect(() => {
    setVisibleCount(PAGE)
    setOpenId(null)
  }, [categoryFilter, filter])
  const accuracy = Number(detail?.accuracy ?? 0)
  const pct = Math.round(accuracy * 1000) / 10
  const correct = Number(detail?.correct ?? 0)
  const total = Number(detail?.total ?? 0)
  const benchmark = String(detail?.benchmark || 'bench')
  const modelId = String(detail?.model_id || detail?.modelId || '')
  const timeS = Number(detail?.time_s ?? detail?.timeS ?? 0)
  const projectId = (detail?.project_id || detail?.projectId || null) as
    | string
    | null
  const displayName =
    String(detail?.name || '').trim() || suiteTitle(benchmark, suites) || benchmark
  const suiteLabel = suiteTitle(benchmark, suites) || benchmark
  const providerRaw = String(
    detail?.provider ||
      environment?.model?.provider ||
      (environment?.runtime?.provider ?? '') ||
      ''
  ).trim()
  const provider = prettyProvider(providerRaw)
  const lifetimeTokens = Number(
    detail?.lifetimeTokens ?? detail?.lifetime_tokens
  )
  const usageLabel = Number.isFinite(lifetimeTokens)
    ? formatTokenCount(lifetimeTokens)
    : null
  const startedLabel = formatStartedAt(
    environment?.started_at ||
      environment?.captured_at ||
      (detail?.created_at as string | undefined) ||
      (detail?.createdAt as string | undefined)
  )

  useEffect(() => {
    if (!detail) return
    document.title = `${displayName} · Benchmarking · Sandwalk`
  }, [displayName, detail])

  const goBack = () => navigate('/dashboard/bench')
  const storedStatus = String(detail?.status || '').toLowerCase()
  const statusKey = (liveStatus || storedStatus).toLowerCase()
  const paused = statusKey === 'paused' || statusKey === 'interrupted'
  const running = statusKey === 'running'
  const isPartial =
    Boolean(statusKey) &&
    statusKey !== 'completed' &&
    statusKey !== 'queued'

  const startEdit = () => {
    setDraftName(String(detail?.name || '').trim() || displayName)
    setEditing(true)
  }

  const saveName = async (name: string) => {
    const next = name.trim()
    setEditing(false)
    try {
      await client.patchBenchRun(runId, { name: next })
      setDetail(current =>
        current ? { ...current, name: next || null } : current
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to rename run')
    }
  }

  const retryFailed = async (questionIds?: string[]) => {
    setResuming(true)
    try {
      await client.retryFailedBenchRun(
        runId,
        questionIds?.length ? { questionIds } : undefined
      )
      setLiveStatus('running')
      if (!questionIds?.length && !running) {
        navigate('/dashboard/bench')
        return
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to retry failed questions')
    } finally {
      setResuming(false)
    }
  }

  const resumeRun = async () => {
    setResuming(true)
    try {
      await client.resumeBenchRun(runId)
      navigate('/dashboard/bench')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to resume bench'
      if (/nothing left to resume/i.test(message)) {
        navigate('/dashboard/bench')
      } else {
        setError(message)
        setResuming(false)
      }
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <DetailStickyNav>
        <div className="flex items-center gap-2 text-sm">
          <button
            type="button"
            onClick={goBack}
            className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <span className="text-muted-foreground/40">/</span>
          <button
            type="button"
            onClick={goBack}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            Results
          </button>
          <span className="text-muted-foreground/40">/</span>
          <span className="text-foreground truncate font-medium">
            {displayName}
          </span>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {paused ? (
            <Button
              type="button"
              size="sm"
              disabled={resuming}
              onClick={() => void resumeRun()}
            >
              {resuming ? (
                <Loader className="size-3.5 animate-spin" />
              ) : (
                <Play className="size-3.5" />
              )}
              Resume
            </Button>
          ) : null}
          {failedCount > 0 ? (
            <Button
              type="button"
              size="sm"
              variant={paused ? 'outline' : 'default'}
              disabled={resuming}
              onClick={() => void retryFailed()}
            >
              {resuming ? (
                <Loader className="size-3.5 animate-spin" />
              ) : (
                <RotateCcw className="size-3.5" />
              )}
              Retry failed ({failedCount})
            </Button>
          ) : null}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={startEdit}
          >
            <Pencil className="size-3.5" />
            Rename
          </Button>
          {projectId ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => navigate(`/projects/${projectId}`)}
            >
              <ExternalLink className="size-3.5" />
              Project
            </Button>
          ) : null}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() =>
              void client.downloadBenchExport(runId).then(file => {
                const url = URL.createObjectURL(file.blob)
                const a = document.createElement('a')
                a.href = url
                a.download = benchExportFilename(modelId, benchmark)
                a.click()
                URL.revokeObjectURL(url)
              })
            }
          >
            <Download className="size-3.5" />
            Download
          </Button>
        </div>
      </DetailStickyNav>

      <ScrollArea className="flex-1">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6 md:px-6">
          {loading ? (
            <div className="text-muted-foreground flex items-center gap-2 text-sm">
              <Loader className="size-4 animate-spin" />
              Loading result…
            </div>
          ) : null}

          {error ? (
            <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
              {error}
            </div>
          ) : null}

          {!loading && detail ? (
            <>
              <header className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex min-w-0 items-start gap-3">
                  <div
                    className={cn(
                      'flex size-10 shrink-0 items-center justify-center rounded-md',
                      running
                        ? 'bg-sky-500/15 text-sky-600'
                        : paused
                          ? 'bg-muted text-muted-foreground'
                          : pctBg(pct)
                    )}
                  >
                    {running ? (
                      <Loader className="size-4 animate-spin" />
                    ) : (
                      <Target className="size-4" />
                    )}
                  </div>
                  <div className="min-w-0">
                    {editing ? (
                      <Input
                        autoFocus
                        value={draftName}
                        onChange={event => setDraftName(event.target.value)}
                        onBlur={() => void saveName(draftName)}
                        onKeyDown={event => {
                          if (event.key === 'Enter') void saveName(draftName)
                          if (event.key === 'Escape') setEditing(false)
                        }}
                        className="h-9 max-w-md text-xl font-semibold"
                      />
                    ) : (
                      <div className="flex min-w-0 items-center gap-2">
                        <h1 className="truncate text-xl font-semibold tracking-tight">
                          {displayName}
                        </h1>
                        <button
                          type="button"
                          className="text-muted-foreground hover:text-foreground shrink-0"
                          aria-label="Rename run"
                          onClick={startEdit}
                        >
                          <Pencil className="size-3.5" />
                        </button>
                      </div>
                    )}
                    <p className="text-muted-foreground mt-1 text-sm">
                      {modelId}
                      {timeS ? ` · ${formatRunDuration(timeS)}` : ''}
                      {startedLabel ? ` · ${startedLabel}` : ''}
                      {detail.thinking_used || detail.thinkingUsed
                        ? ' · thinking'
                        : ''}
                    </p>
                    <p className="text-muted-foreground mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                      <span>
                        Provider{' '}
                        <span className="text-foreground font-medium">
                          {provider || '—'}
                        </span>
                      </span>
                      <span>
                        Usage{' '}
                        <span className="text-foreground font-medium tabular-nums">
                          {usageLabel || '—'}
                        </span>
                      </span>
                      <span>
                        Suite{' '}
                        <span className="text-foreground font-medium">
                          {suiteLabel}
                        </span>
                      </span>
                    </p>
                    <p className="text-muted-foreground mt-0.5 font-mono text-[11px]">
                      {runId}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p
                    className={cn(
                      'text-3xl font-semibold tabular-nums',
                      pctClass(pct)
                    )}
                  >
                    {pct.toFixed(1)}%
                  </p>
                  <p className="text-muted-foreground text-sm tabular-nums">
                    {correct}/{total} correct
                  </p>
                  {running ? (
                    <p className="text-sky-600 mt-1 inline-flex items-center justify-end gap-1.5 text-xs font-medium">
                      <Loader className="size-3.5 animate-spin" />
                      Running
                      <span className="text-muted-foreground font-normal">
                        · Partial results
                      </span>
                    </p>
                  ) : isPartial ? (
                    <p className="text-muted-foreground mt-1 text-xs font-medium">
                      Partial results
                      {paused ? ' · paused' : ''}
                    </p>
                  ) : null}
                </div>
              </header>

              {environment ? <BenchEnvironmentPanel env={environment} /> : null}

              {categories.length ? (
                <section className="space-y-2">
                  <h2 className="text-sm font-semibold">Categories</h2>
                  <div className="grid gap-1.5 sm:grid-cols-2">
                    {categories.map(([cat, score]) => (
                      <button
                        key={cat}
                        type="button"
                        className={cn(
                          'border-border/60 flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors',
                          categoryFilter === cat
                            ? 'border-primary/40 bg-primary/[0.04]'
                            : 'hover:bg-muted/40'
                        )}
                        onClick={() => {
                          setCategoryFilter(current =>
                            current === cat ? null : cat
                          )
                          document
                            .getElementById('bench-questions')
                            ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                        }}
                      >
                        <span className="text-muted-foreground truncate">
                          {cat.replace(/_/g, ' ')}
                        </span>
                        <span
                          className={cn(
                            'tabular-nums font-medium',
                            pctClass(Number(score) * 100)
                          )}
                        >
                          {(Number(score) * 100).toFixed(1)}%
                        </span>
                      </button>
                    ))}
                  </div>
                </section>
              ) : null}

              <section id="bench-questions" className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-sm font-semibold">
                    Questions
                    {questions.length ? (
                      <span className="text-muted-foreground font-normal">
                        {' '}
                        · {filtered.length}
                        {filter !== 'all' || categoryFilter
                          ? ` of ${questions.length}`
                          : ''}
                        {categoryFilter
                          ? ` · ${categoryFilter.replace(/_/g, ' ')}`
                          : ''}
                      </span>
                    ) : null}
                  </h2>
                  <div className="flex flex-wrap items-center gap-2">
                  {categoryFilter ? (
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground text-xs"
                      onClick={() => setCategoryFilter(null)}
                    >
                      Clear category
                    </button>
                  ) : null}
                  <div className="bg-muted/50 inline-flex rounded-md p-0.5">
                    {(
                      [
                        ['all', 'All'],
                        ['pass', 'Pass'],
                        ['fail', 'Fail']
                      ] as const
                    ).map(([id, label]) => (
                      <button
                        key={id}
                        type="button"
                        onClick={() => {
                          setFilter(id)
                        }}
                        className={cn(
                          'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                          filter === id
                            ? 'bg-background text-foreground shadow-sm'
                            : 'text-muted-foreground hover:text-foreground'
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  </div>
                </div>

                <div className="space-y-2">
                  {visible.map((q, index) => {
                    const qid = String(q.id ?? index)
                    const benchQid = String(
                      q.questionId || q.question_id || q.category || ''
                    ).trim()
                    const open = openId === qid
                    const sessionId = q.sessionId || q.session_id
                    const evalMode = q.evalMode || q.eval_mode || '—'
                    const tools = q.toolsSeen || q.tools_seen || []
                    const raw = open
                      ? q.rawResponse || q.raw_response || ''
                      : ''
                    const judge = q.judge
                    const judgePass =
                      judge?.overallPass ?? judge?.overall_pass ?? null
                    const uniqueTools = open
                      ? [...new Set(tools)]
                      : []
                    return (
                      <div
                        key={qid}
                        className="border-border/70 overflow-hidden rounded-md border"
                      >
                        <div className="flex items-start gap-1">
                        <button
                          type="button"
                          onClick={() => setOpenId(open ? null : qid)}
                          className="hover:bg-muted/30 flex min-w-0 flex-1 items-start gap-3 px-3 py-3 text-left transition-colors"
                        >
                          <span
                            className={cn(
                              'mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md',
                              q.correct
                                ? 'bg-emerald-500/15 text-emerald-600'
                                : 'bg-red-500/15 text-red-600'
                            )}
                          >
                            {q.correct ? (
                              <Check className="size-3.5" />
                            ) : (
                              <X className="size-3.5" />
                            )}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="text-sm font-medium">
                                {q.category || qid}
                              </span>
                              <span className="bg-muted text-muted-foreground rounded px-1.5 py-0.5 text-[10px]">
                                {evalMode}
                              </span>
                              {judgePass != null ? (
                                <span
                                  className={cn(
                                    'rounded px-1.5 py-0.5 text-[10px]',
                                    judgePass
                                      ? 'bg-emerald-500/15 text-emerald-600'
                                      : 'bg-red-500/15 text-red-600'
                                  )}
                                >
                                  judge {judgePass ? 'pass' : 'fail'}
                                </span>
                              ) : null}
                            </div>
                            <p className="text-muted-foreground mt-1 line-clamp-2 text-xs leading-relaxed">
                              {q.question || '—'}
                            </p>
                            <p className="text-muted-foreground mt-1 text-[11px] tabular-nums">
                              expected{' '}
                              <span className="text-foreground">
                                {q.expected || '—'}
                              </span>
                              {' · '}
                              predicted{' '}
                              <span className="text-foreground">
                                {String(q.predicted || '—').slice(0, 80)}
                              </span>
                            </p>
                          </div>
                          {open ? (
                            <ChevronDown className="text-muted-foreground mt-1 size-4 shrink-0" />
                          ) : (
                            <ChevronRight className="text-muted-foreground mt-1 size-4 shrink-0" />
                          )}
                        </button>
                        {benchQid ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            className="mt-2 mr-2 shrink-0"
                            disabled={resuming}
                            onClick={() => void retryFailed([benchQid])}
                          >
                            <RotateCcw className="size-3.5" />
                            Retry
                          </Button>
                        ) : null}
                        </div>

                        {open ? (
                          <div className="border-border/60 space-y-3 border-t px-3 py-3 text-xs">
                            {sessionId ? (
                              <button
                                type="button"
                                className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
                                onClick={() =>
                                  navigate(`/agents/${sessionId}`)
                                }
                              >
                                <ExternalLink className="size-3" />
                                Open session
                              </button>
                            ) : null}

                            {uniqueTools.length ? (
                              <div>
                                <p className="text-muted-foreground mb-1 font-medium">
                                  Tools ({uniqueTools.length})
                                </p>
                                <div className="flex flex-wrap gap-1">
                                  {uniqueTools.map(tool => (
                                    <span
                                      key={tool}
                                      className="bg-muted rounded px-1.5 py-0.5 font-mono text-[10px]"
                                    >
                                      {tool}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ) : null}

                            {q.heuristics &&
                            Object.keys(q.heuristics).length ? (
                              <div>
                                <p className="text-muted-foreground mb-1 font-medium">
                                  Heuristics
                                </p>
                                <div className="space-y-1">
                                  {Object.entries(q.heuristics).map(
                                    ([key, ok]) => (
                                      <div
                                        key={key}
                                        className="flex items-center justify-between gap-2"
                                      >
                                        <span>{key}</span>
                                        <span
                                          className={
                                            ok
                                              ? 'text-emerald-600'
                                              : 'text-red-600'
                                          }
                                        >
                                          {ok ? 'pass' : 'fail'}
                                        </span>
                                      </div>
                                    )
                                  )}
                                </div>
                              </div>
                            ) : null}

                            {judge?.items?.length ? (
                              <div>
                                <p className="text-muted-foreground mb-1 font-medium">
                                  Judge items
                                </p>
                                <div className="space-y-2">
                                  {judge.items.map((item, i) => (
                                    <div
                                      key={`${item.id || i}`}
                                      className="border-border/50 rounded-md border px-2 py-1.5"
                                    >
                                      <div className="flex items-center justify-between gap-2">
                                        <span className="font-medium">
                                          {item.id || `item-${i + 1}`}
                                        </span>
                                        <span
                                          className={
                                            item.pass
                                              ? 'text-emerald-600'
                                              : 'text-red-600'
                                          }
                                        >
                                          {item.pass ? 'pass' : 'fail'}
                                        </span>
                                      </div>
                                      {item.reason ? (
                                        <p className="text-muted-foreground mt-1 leading-relaxed">
                                          {item.reason}
                                        </p>
                                      ) : null}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : null}

                            {judge?.error ? (
                              <p className="text-destructive">
                                Judge error: {judge.error}
                              </p>
                            ) : null}

                            {raw ? (
                              <div>
                                <p className="text-muted-foreground mb-1 font-medium">
                                  Raw response
                                </p>
                                <pre className="bg-muted/40 max-h-56 overflow-auto rounded-md p-2 whitespace-pre-wrap font-mono text-[11px] leading-relaxed">
                                  {raw}
                                </pre>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    )
                  })}

                  {visibleCount < filtered.length ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="w-full"
                      onClick={() =>
                        setVisibleCount(n => Math.min(filtered.length, n + PAGE))
                      }
                    >
                      Show more · {visible.length} of {filtered.length}
                    </Button>
                  ) : null}

                  {!filtered.length ? (
                    <div className="border-border/60 text-muted-foreground rounded-md border border-dashed px-4 py-8 text-center text-sm">
                      No questions in this filter.
                    </div>
                  ) : null}
                </div>
              </section>
            </>
          ) : null}
        </div>
      </ScrollArea>
    </div>
  )
}
