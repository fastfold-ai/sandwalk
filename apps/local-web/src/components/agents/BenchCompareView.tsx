import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { ArrowLeft, Check, ChevronDown, ChevronRight, ExternalLink, Loader, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { DetailStickyNav } from '@/components/agents/detail-sticky-nav'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

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
  } | null
  tools_seen?: string[]
  toolsSeen?: string[]
}

type CompareFilter = 'disagreements' | 'all' | 'any_wrong'

type RunCol = {
  id: string
  letter: string
  detail: Record<string, unknown>
  modelId: string
  bench: string
  accuracy: number
  pct: number
  timeS: number
  questions: BenchQuestion[]
}

function asQuestions(detail: Record<string, unknown> | null): BenchQuestion[] {
  const rows = detail?.questions
  return Array.isArray(rows) ? (rows as BenchQuestion[]) : []
}

function shortModel(modelId: string) {
  const parts = modelId.split('/')
  return parts[parts.length - 1] || modelId || 'model'
}

function runLetter(index: number) {
  return index < 26 ? String.fromCharCode(65 + index) : `R${index + 1}`
}

function questionKey(q: BenchQuestion, index: number) {
  return String(q.questionId || q.question_id || q.id || `idx-${index}`)
}

function pctClass(pct: number) {
  if (pct >= 70) return 'text-emerald-600'
  if (pct >= 40) return 'text-amber-600'
  return 'text-red-600'
}

function parseCompareIds(params: URLSearchParams): string[] {
  const listed = params.getAll('id').map(id => id.trim()).filter(Boolean)
  if (listed.length) return [...new Set(listed)]
  const a = (params.get('a') || '').trim()
  const b = (params.get('b') || '').trim()
  return [a, b].filter(Boolean)
}

function Verdict({ ok, label }: { ok: boolean | null; label: string }) {
  if (ok == null) {
    return (
      <span className="bg-muted text-muted-foreground rounded-md px-1.5 py-0.5 text-[11px] font-medium">
        {label} —
      </span>
    )
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium',
        ok
          ? 'bg-emerald-500/15 text-emerald-600'
          : 'bg-red-500/15 text-red-600'
      )}
    >
      {ok ? <Check className="size-3" /> : <X className="size-3" />}
      {label} {ok ? 'pass' : 'fail'}
    </span>
  )
}

function SideAnswer({
  label,
  question,
  modelId
}: {
  label: string
  question: BenchQuestion | null
  modelId: string
}) {
  const navigate = useNavigate()
  if (!question) {
    return (
      <div className="border-border/60 min-w-[14rem] flex-1 rounded-md border px-3 py-2">
        <p className="text-muted-foreground text-[11px] font-medium">
          {label} · missing
        </p>
      </div>
    )
  }
  const sessionId = question.sessionId || question.session_id
  const raw = question.rawResponse || question.raw_response || ''
  const tools = question.toolsSeen || question.tools_seen || []
  return (
    <div className="border-border/60 min-w-[14rem] flex-1 space-y-2 rounded-md border px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium">
          {label}
          <span className="text-muted-foreground font-normal">
            {' '}
            · {shortModel(modelId)}
          </span>
        </p>
        <Verdict ok={question.correct ?? null} label={label} />
      </div>
      <p className="text-xs">
        <span className="text-muted-foreground">predicted </span>
        {String(question.predicted || '—')}
      </p>
      {raw ? (
        <pre className="bg-muted/40 text-muted-foreground max-h-40 overflow-auto rounded-md p-2 font-mono text-[10px] whitespace-pre-wrap">
          {raw.slice(0, 2500)}
          {raw.length > 2500 ? '…' : ''}
        </pre>
      ) : null}
      {tools.length ? (
        <div className="flex flex-wrap gap-1">
          {[...new Set(tools)].slice(0, 12).map(tool => (
            <span
              key={tool}
              className="bg-muted rounded px-1.5 py-0.5 font-mono text-[10px]"
            >
              {tool}
            </span>
          ))}
        </div>
      ) : null}
      {sessionId ? (
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-[11px]"
          onClick={() => navigate(`/agents/${sessionId}`)}
        >
          <ExternalLink className="size-3" />
          Open session
        </button>
      ) : null}
    </div>
  )
}

export function BenchCompareView({
  client
}: {
  client: LocalAgentClient
}) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const runIds = useMemo(() => parseCompareIds(params), [params])
  const [details, setDetails] = useState<Array<Record<string, unknown> | null>>(
    []
  )
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<CompareFilter>('disagreements')
  const [openId, setOpenId] = useState<string | null>(null)
  const [visibleCount, setVisibleCount] = useState(40)
  const PAGE = 40

  useEffect(() => {
    if (runIds.length < 2) {
      setError('Pick at least two runs to compare.')
      setLoading(false)
      setDetails([])
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    void Promise.all(runIds.map(id => client.getBenchResult(id)))
      .then(rows => {
        if (cancelled) return
        setDetails(rows)
      })
      .catch(err => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Unable to load runs')
        setDetails([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [client, runIds])

  const cols: RunCol[] = useMemo(
    () =>
      runIds.map((id, index) => {
        const detail = details[index] || {}
        const modelId = String(detail.model_id || detail.modelId || runLetter(index))
        const accuracy = Number(detail.accuracy ?? 0)
        return {
          id,
          letter: runLetter(index),
          detail,
          modelId,
          bench: String(detail.benchmark || ''),
          accuracy,
          pct: Math.round(accuracy * 1000) / 10,
          timeS: Number(detail.time_s ?? detail.timeS ?? 0),
          questions: asQuestions(detail)
        }
      }),
    [details, runIds]
  )

  const rows = useMemo(() => {
    const keys: string[] = []
    const seen = new Set<string>()
    for (const col of cols) {
      col.questions.forEach((q, index) => {
        const key = questionKey(q, index)
        if (seen.has(key)) return
        seen.add(key)
        keys.push(key)
      })
    }
    return keys.map(key => {
      const answers = cols.map(col => {
        const byId = col.questions.find((q, index) => questionKey(q, index) === key)
        return byId || null
      })
      const first = answers.find(Boolean)
      return {
        key,
        question: first?.question || '—',
        category: first?.category || key,
        expected: first?.expected || '—',
        answers
      }
    })
  }, [cols])

  const counts = useMemo(() => {
    let agreePass = 0
    let agreeFail = 0
    let disagree = 0
    let anyWrong = 0
    for (const row of rows) {
      const verdicts = row.answers
        .map(q => q?.correct)
        .filter((v): v is boolean => v != null)
      if (!verdicts.length) continue
      if (verdicts.some(v => !v)) anyWrong += 1
      const same = verdicts.every(v => v === verdicts[0])
      if (!same) disagree += 1
      else if (verdicts[0]) agreePass += 1
      else agreeFail += 1
    }
    return { agreePass, agreeFail, disagree, anyWrong }
  }, [rows])

  const filtered = useMemo(() => {
    return rows.filter(row => {
      const verdicts = row.answers.map(q => q?.correct ?? null)
      if (filter === 'all') return true
      const known = verdicts.filter((v): v is boolean => v != null)
      if (filter === 'any_wrong') return known.some(v => !v)
      if (known.length < 2) return true
      return !known.every(v => v === known[0])
    })
  }, [filter, rows])
  const visible = useMemo(
    () => filtered.slice(0, visibleCount),
    [filtered, visibleCount]
  )

  useEffect(() => {
    setVisibleCount(PAGE)
    setOpenId(null)
  }, [filter, runIds.join(',')])

  useEffect(() => {
    document.title = `Compare · Benchmarking · Sandwalk`
  }, [])

  const goBack = () => navigate('/dashboard/bench')
  const benches = [...new Set(cols.map(col => col.bench).filter(Boolean))]
  const sameSuite = benches.length <= 1
  const ready =
    !loading &&
    details.length === runIds.length &&
    details.every(row => row != null) &&
    cols.length >= 2

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
          <span className="text-foreground font-medium">
            Compare · {runIds.length}
          </span>
        </div>
        <div className="flex max-w-xl flex-wrap items-center justify-end gap-2">
          {cols.map(col => (
            <Button
              key={col.id}
              type="button"
              size="sm"
              variant="outline"
              onClick={() =>
                navigate(`/dashboard/bench/${encodeURIComponent(col.id)}`)
              }
            >
              Open {col.letter}
            </Button>
          ))}
        </div>
      </DetailStickyNav>

      <ScrollArea className="flex-1">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 md:px-6">
          {loading ? (
            <div className="text-muted-foreground flex items-center gap-2 text-sm">
              <Loader className="size-4 animate-spin" />
              Loading comparison…
            </div>
          ) : null}

          {error ? (
            <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
              {error}
            </div>
          ) : null}

          {ready ? (
            <>
              <header className="space-y-3">
                <div>
                  <h1 className="text-xl font-semibold tracking-tight">
                    {sameSuite
                      ? benches[0] || 'Compare'
                      : benches.join(' · ')}
                  </h1>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {cols.map(col => shortModel(col.modelId)).join(' · ')}
                    {!sameSuite ? (
                      <span className="text-amber-600">
                        {' '}
                        · different suites — join by question id
                      </span>
                    ) : null}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {cols.map(col => (
                    <div
                      key={col.id}
                      className="border-border/60 rounded-lg border px-4 py-3"
                    >
                      <p className="text-muted-foreground text-xs">
                        {col.letter} · {shortModel(col.modelId)}
                      </p>
                      <p
                        className={cn(
                          'mt-1 text-2xl font-semibold tabular-nums',
                          pctClass(col.pct)
                        )}
                      >
                        {col.pct.toFixed(1)}%
                      </p>
                      <p className="text-muted-foreground mt-0.5 text-xs tabular-nums">
                        {Number(col.detail.correct ?? 0)}/
                        {Number(col.detail.total ?? 0)}
                        {col.timeS ? ` · ${col.timeS}s` : ''}
                      </p>
                    </div>
                  ))}
                </div>

                <div className="flex flex-wrap gap-2 text-xs">
                  <span className="bg-muted rounded-md px-2 py-1">
                    All pass · {counts.agreePass}
                  </span>
                  <span className="bg-amber-500/10 text-amber-700 dark:text-amber-400 rounded-md px-2 py-1">
                    Disagree · {counts.disagree}
                  </span>
                  <span className="bg-red-500/10 text-red-700 dark:text-red-400 rounded-md px-2 py-1">
                    All fail · {counts.agreeFail}
                  </span>
                  <span className="bg-muted rounded-md px-2 py-1">
                    Any fail · {counts.anyWrong}
                  </span>
                </div>
              </header>

              <section className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-sm font-semibold">
                    Questions
                    <span className="text-muted-foreground font-normal">
                      {' '}
                      · {filtered.length}
                      {filter !== 'all' ? ` of ${rows.length}` : ''}
                    </span>
                  </h2>
                  <div className="bg-muted/50 inline-flex flex-wrap rounded-md p-0.5">
                    {(
                      [
                        ['disagreements', 'Disagreements'],
                        ['all', 'All'],
                        ['any_wrong', 'Any fail']
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
                  {visible.map(row => {
                    const open = openId === row.key
                    const verdicts = row.answers.map(q => q?.correct ?? null)
                    const known = verdicts.filter((v): v is boolean => v != null)
                    const disagree =
                      known.length >= 2 && !known.every(v => v === known[0])
                    return (
                      <div
                        key={row.key}
                        className={cn(
                          'border-border/70 overflow-hidden rounded-md border',
                          disagree && 'border-amber-500/30'
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => setOpenId(open ? null : row.key)}
                          className="hover:bg-muted/30 flex w-full items-start gap-3 px-3 py-3 text-left transition-colors"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="text-sm font-medium">
                                {row.category}
                              </span>
                              {cols.map((col, index) => (
                                <Verdict
                                  key={col.id}
                                  ok={verdicts[index]}
                                  label={col.letter}
                                />
                              ))}
                            </div>
                            <p className="text-muted-foreground mt-1 line-clamp-2 text-xs leading-relaxed">
                              {row.question}
                            </p>
                            <p className="text-muted-foreground mt-1 text-[11px]">
                              expected{' '}
                              <span className="text-foreground">
                                {row.expected}
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
                          <div className="border-border/60 flex gap-2 overflow-x-auto border-t px-3 py-3">
                            {cols.map((col, index) => (
                              <SideAnswer
                                key={col.id}
                                label={col.letter}
                                question={row.answers[index]}
                                modelId={col.modelId}
                              />
                            ))}
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
                      No questions match this filter.
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
