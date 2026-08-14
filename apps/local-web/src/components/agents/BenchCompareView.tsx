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

type CompareFilter = 'disagreements' | 'all' | 'a_wrong' | 'b_wrong'

function asQuestions(detail: Record<string, unknown> | null): BenchQuestion[] {
  const rows = detail?.questions
  return Array.isArray(rows) ? (rows as BenchQuestion[]) : []
}

function shortModel(modelId: string) {
  const parts = modelId.split('/')
  return parts[parts.length - 1] || modelId || 'model'
}

function pctClass(pct: number) {
  if (pct >= 70) return 'text-emerald-600'
  if (pct >= 40) return 'text-amber-600'
  return 'text-red-600'
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
      <div className="border-border/60 min-w-0 flex-1 rounded-md border px-3 py-2">
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
    <div className="border-border/60 min-w-0 flex-1 space-y-2 rounded-md border px-3 py-2">
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
  const runA = params.get('a') || ''
  const runB = params.get('b') || ''
  const [detailA, setDetailA] = useState<Record<string, unknown> | null>(null)
  const [detailB, setDetailB] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<CompareFilter>('disagreements')
  const [openId, setOpenId] = useState<string | null>(null)
  const [visibleCount, setVisibleCount] = useState(40)
  const PAGE = 40

  useEffect(() => {
    if (!runA || !runB) {
      setError('Pick two runs to compare.')
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    void Promise.all([client.getBenchResult(runA), client.getBenchResult(runB)])
      .then(([a, b]) => {
        if (cancelled) return
        setDetailA(a)
        setDetailB(b)
      })
      .catch(err => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Unable to load runs')
        setDetailA(null)
        setDetailB(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [client, runA, runB])

  const modelA = String(detailA?.model_id || detailA?.modelId || 'A')
  const modelB = String(detailB?.model_id || detailB?.modelId || 'B')
  const benchA = String(detailA?.benchmark || '')
  const benchB = String(detailB?.benchmark || '')
  const accuracyA = Number(detailA?.accuracy ?? 0)
  const accuracyB = Number(detailB?.accuracy ?? 0)
  const pctA = Math.round(accuracyA * 1000) / 10
  const pctB = Math.round(accuracyB * 1000) / 10
  const delta = Math.round((pctA - pctB) * 10) / 10
  const timeA = Number(detailA?.time_s ?? detailA?.timeS ?? 0)
  const timeB = Number(detailB?.time_s ?? detailB?.timeS ?? 0)

  const rows = useMemo(() => {
    const qsA = asQuestions(detailA)
    const qsB = asQuestions(detailB)
    const byIdB = new Map(
      qsB.map((q, index) => [String(q.id ?? `idx-${index}`), q] as const)
    )
    const usedB = new Set<string>()
    const joined: Array<{
      key: string
      question: string
      category: string
      expected: string
      a: BenchQuestion | null
      b: BenchQuestion | null
    }> = []

    qsA.forEach((q, index) => {
      const key = String(q.id ?? `idx-${index}`)
      let match = byIdB.get(key) || null
      let matchKey = key
      if (!match && qsB[index]) {
        match = qsB[index]
        matchKey = String(match.id ?? `idx-${index}`)
      }
      if (match) usedB.add(matchKey)
      joined.push({
        key,
        question: q.question || match?.question || '—',
        category: q.category || match?.category || key,
        expected: q.expected || match?.expected || '—',
        a: q,
        b: match
      })
    })

    qsB.forEach((q, index) => {
      const key = String(q.id ?? `idx-${index}`)
      if (usedB.has(key)) return
      joined.push({
        key: `b-${key}`,
        question: q.question || '—',
        category: q.category || key,
        expected: q.expected || '—',
        a: null,
        b: q
      })
    })
    return joined
  }, [detailA, detailB])

  const counts = useMemo(() => {
    let bothPass = 0
    let bothFail = 0
    let aOnly = 0
    let bOnly = 0
    for (const row of rows) {
      const aOk = row.a?.correct
      const bOk = row.b?.correct
      if (aOk == null || bOk == null) continue
      if (aOk && bOk) bothPass += 1
      else if (!aOk && !bOk) bothFail += 1
      else if (aOk && !bOk) aOnly += 1
      else bOnly += 1
    }
    return { bothPass, bothFail, aOnly, bOnly }
  }, [rows])

  const filtered = useMemo(() => {
    return rows.filter(row => {
      const aOk = row.a?.correct
      const bOk = row.b?.correct
      if (filter === 'all') return true
      if (aOk == null || bOk == null) return filter === 'disagreements'
      if (filter === 'disagreements') return aOk !== bOk
      if (filter === 'a_wrong') return !aOk
      if (filter === 'b_wrong') return !bOk
      return true
    })
  }, [filter, rows])
  const visible = useMemo(
    () => filtered.slice(0, visibleCount),
    [filtered, visibleCount]
  )

  useEffect(() => {
    setVisibleCount(PAGE)
    setOpenId(null)
  }, [filter, runA, runB])

  useEffect(() => {
    document.title = `Compare · Benchmarking · Sandwalk`
  }, [])

  const goBack = () => navigate('/dashboard/bench')
  const sameSuite = Boolean(benchA && benchA === benchB)

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
          <span className="text-foreground font-medium">Compare</span>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {runA ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() =>
                navigate(`/dashboard/bench/${encodeURIComponent(runA)}`)
              }
            >
              Open A
            </Button>
          ) : null}
          {runB ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() =>
                navigate(`/dashboard/bench/${encodeURIComponent(runB)}`)
              }
            >
              Open B
            </Button>
          ) : null}
        </div>
      </DetailStickyNav>

      <ScrollArea className="flex-1">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6 md:px-6">
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

          {!loading && detailA && detailB ? (
            <>
              <header className="space-y-3">
                <div>
                  <h1 className="text-xl font-semibold tracking-tight">
                    {sameSuite ? benchA : `${benchA || 'A'} vs ${benchB || 'B'}`}
                  </h1>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {shortModel(modelA)} vs {shortModel(modelB)}
                    {!sameSuite ? (
                      <span className="text-amber-600">
                        {' '}
                        · different suites — join by question id
                      </span>
                    ) : null}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="border-border/60 rounded-lg border px-4 py-3">
                    <p className="text-muted-foreground text-xs">A · {shortModel(modelA)}</p>
                    <p className={cn('mt-1 text-2xl font-semibold tabular-nums', pctClass(pctA))}>
                      {pctA.toFixed(1)}%
                    </p>
                    <p className="text-muted-foreground mt-0.5 text-xs tabular-nums">
                      {Number(detailA.correct ?? 0)}/{Number(detailA.total ?? 0)}
                      {timeA ? ` · ${timeA}s` : ''}
                    </p>
                  </div>
                  <div className="border-border/60 rounded-lg border px-4 py-3">
                    <p className="text-muted-foreground text-xs">Δ accuracy</p>
                    <p
                      className={cn(
                        'mt-1 text-2xl font-semibold tabular-nums',
                        delta > 0
                          ? 'text-emerald-600'
                          : delta < 0
                            ? 'text-red-600'
                            : 'text-muted-foreground'
                      )}
                    >
                      {delta > 0 ? '+' : ''}
                      {delta.toFixed(1)} pp
                    </p>
                    <p className="text-muted-foreground mt-0.5 text-xs tabular-nums">
                      time {timeA || '—'}s vs {timeB || '—'}s
                    </p>
                  </div>
                  <div className="border-border/60 rounded-lg border px-4 py-3">
                    <p className="text-muted-foreground text-xs">B · {shortModel(modelB)}</p>
                    <p className={cn('mt-1 text-2xl font-semibold tabular-nums', pctClass(pctB))}>
                      {pctB.toFixed(1)}%
                    </p>
                    <p className="text-muted-foreground mt-0.5 text-xs tabular-nums">
                      {Number(detailB.correct ?? 0)}/{Number(detailB.total ?? 0)}
                      {timeB ? ` · ${timeB}s` : ''}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 text-xs">
                  <span className="bg-muted rounded-md px-2 py-1">
                    Both pass · {counts.bothPass}
                  </span>
                  <span className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 rounded-md px-2 py-1">
                    A only · {counts.aOnly}
                  </span>
                  <span className="bg-sky-500/10 text-sky-700 dark:text-sky-400 rounded-md px-2 py-1">
                    B only · {counts.bOnly}
                  </span>
                  <span className="bg-red-500/10 text-red-700 dark:text-red-400 rounded-md px-2 py-1">
                    Both fail · {counts.bothFail}
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
                        ['a_wrong', 'A wrong'],
                        ['b_wrong', 'B wrong']
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
                    const aOk = row.a?.correct ?? null
                    const bOk = row.b?.correct ?? null
                    const disagree = aOk != null && bOk != null && aOk !== bOk
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
                              <Verdict ok={aOk} label="A" />
                              <Verdict ok={bOk} label="B" />
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
                          <div className="border-border/60 flex flex-col gap-2 border-t px-3 py-3 sm:flex-row">
                            <SideAnswer
                              label="A"
                              question={row.a}
                              modelId={modelA}
                            />
                            <SideAnswer
                              label="B"
                              question={row.b}
                              modelId={modelB}
                            />
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
