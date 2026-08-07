import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  Loader2,
  Target,
  X
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { DetailStickyNav } from '@/components/agents/detail-sticky-nav'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type BenchQuestion = {
  id?: string
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

export function BenchResultDetail({
  client,
  runId
}: {
  client: LocalAgentClient
  runId: string
}) {
  const navigate = useNavigate()
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [openId, setOpenId] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'pass' | 'fail'>('all')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    void client
      .getBenchResult(runId)
      .then(row => {
        if (cancelled) return
        setDetail(row)
      })
      .catch(err => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Unable to load result')
        setDetail(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [client, runId])

  const questions = useMemo(() => asQuestions(detail), [detail])
  const categories = useMemo(() => categoryScores(detail), [detail])
  const filtered = useMemo(() => {
    if (filter === 'pass') return questions.filter(q => q.correct)
    if (filter === 'fail') return questions.filter(q => !q.correct)
    return questions
  }, [filter, questions])

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

  useEffect(() => {
    if (!detail) return
    document.title = `${benchmark} · Bench · Sandwalk`
  }, [benchmark, detail])

  const goBack = () => navigate('/dashboard/bench')

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
            {benchmark}
          </span>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
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
                a.download = file.filename
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
              <Loader2 className="size-4 animate-spin" />
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
                      pctBg(pct)
                    )}
                  >
                    <Target className="size-4" />
                  </div>
                  <div className="min-w-0">
                    <h1 className="text-xl font-semibold tracking-tight">
                      {benchmark}
                    </h1>
                    <p className="text-muted-foreground mt-1 text-sm">
                      {modelId}
                      {timeS ? ` · ${timeS}s` : ''}
                      {detail.thinking_used || detail.thinkingUsed
                        ? ' · thinking'
                        : ''}
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
                </div>
              </header>

              {categories.length ? (
                <section className="space-y-2">
                  <h2 className="text-sm font-semibold">Categories</h2>
                  <div className="grid gap-1.5 sm:grid-cols-2">
                    {categories.map(([cat, score]) => (
                      <div
                        key={cat}
                        className="border-border/60 flex items-center justify-between rounded-md border px-3 py-2 text-sm"
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
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}

              <section className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-sm font-semibold">
                    Questions
                    {questions.length ? (
                      <span className="text-muted-foreground font-normal">
                        {' '}
                        · {filtered.length}
                        {filter !== 'all' ? ` of ${questions.length}` : ''}
                      </span>
                    ) : null}
                  </h2>
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
                        onClick={() => setFilter(id)}
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

                <div className="space-y-2">
                  {filtered.map((q, index) => {
                    const qid = String(q.id ?? index)
                    const open = openId === qid
                    const sessionId = q.sessionId || q.session_id
                    const evalMode = q.evalMode || q.eval_mode || '—'
                    const tools = q.toolsSeen || q.tools_seen || []
                    const raw = q.rawResponse || q.raw_response || ''
                    const judge = q.judge
                    const judgePass =
                      judge?.overallPass ?? judge?.overall_pass ?? null
                    const uniqueTools = [...new Set(tools)]
                    return (
                      <div
                        key={qid}
                        className="border-border/70 overflow-hidden rounded-md border"
                      >
                        <button
                          type="button"
                          onClick={() => setOpenId(open ? null : qid)}
                          className="hover:bg-muted/30 flex w-full items-start gap-3 px-3 py-3 text-left transition-colors"
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
