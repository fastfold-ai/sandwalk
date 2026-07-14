import type {
  PromptBudgetBucket,
  PromptBudgetResponse,
  Specialist
} from '@sandwalk/agent-ui-core'
import { AlertTriangle, Check, ChevronDown, Loader2, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { SpecialistAvatar } from '@/components/agents/SpecialistsView'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

const BUCKET_COLORS = [
  'bg-sky-500',
  'bg-violet-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-rose-500',
  'bg-cyan-500',
  'bg-indigo-500',
  'bg-teal-500'
]

/** Survive route unmount so switching dashboard tabs does not force a full re-estimate. */
type PromptBudgetCache = {
  specialistId: string
  specialists: Specialist[]
  budget: PromptBudgetResponse
  at: number
}

let promptBudgetCache: PromptBudgetCache | null = null
const PROMPT_BUDGET_CACHE_TTL_MS = 5 * 60 * 1000

function formatTokens(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 10_000) return `${Math.round(value / 1000)}k`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
  return String(value)
}

function BucketRow({
  bucket,
  totalTokens,
  depth = 0,
  colorIndex = 0
}: {
  bucket: PromptBudgetBucket
  totalTokens: number
  depth?: number
  colorIndex?: number
}) {
  const [open, setOpen] = useState(depth === 0)
  const hasChildren = (bucket.children?.length || 0) > 0
  const share =
    totalTokens > 0 ? Math.max(0, (bucket.tokens / totalTokens) * 100) : 0
  const color = BUCKET_COLORS[colorIndex % BUCKET_COLORS.length]

  return (
    <div className="space-y-1">
      <button
        type="button"
        className={cn(
          'hover:bg-muted/40 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors',
          depth > 0 && 'opacity-90'
        )}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={() => {
          if (hasChildren) setOpen(current => !current)
        }}
        disabled={!hasChildren}
      >
        {hasChildren ? (
          <ChevronDown
            className={cn(
              'text-muted-foreground size-3.5 shrink-0 transition-transform',
              !open && '-rotate-90'
            )}
          />
        ) : (
          <span className="size-3.5 shrink-0" />
        )}
        <span className={cn('size-2 shrink-0 rounded-full', color)} />
        <span className="min-w-0 flex-1 truncate text-sm">{bucket.label}</span>
        {bucket.count != null ? (
          <span className="text-muted-foreground shrink-0 text-xs">
            ×{bucket.count}
          </span>
        ) : null}
        <span className="text-muted-foreground shrink-0 font-mono text-xs">
          {formatTokens(bucket.tokens)}
        </span>
        <span className="text-muted-foreground/70 w-10 shrink-0 text-right text-xs">
          {share.toFixed(0)}%
        </span>
      </button>
      {hasChildren && open
        ? bucket.children.map(child => (
            <BucketRow
              key={child.id}
              bucket={child}
              totalTokens={totalTokens}
              depth={depth + 1}
              colorIndex={colorIndex}
            />
          ))
        : null}
    </div>
  )
}

export function AgentPromptsView({
  connected,
  onGetPromptBudget,
  onListSpecialists
}: {
  connected: boolean
  onGetPromptBudget: (
    options?: {
      specialistId?: string | null
      projectId?: string | null
      sampleQuery?: string | null
    },
    signal?: AbortSignal
  ) => Promise<PromptBudgetResponse>
  onListSpecialists: (signal?: AbortSignal) => Promise<Specialist[]>
}) {
  const [specialists, setSpecialists] = useState<Specialist[]>(
    () => promptBudgetCache?.specialists || []
  )
  const [specialistId, setSpecialistId] = useState(
    () => promptBudgetCache?.specialistId || ''
  )
  const [budget, setBudget] = useState<PromptBudgetResponse | null>(() => {
    const cached = promptBudgetCache
    if (!cached) return null
    if (Date.now() - cached.at > PROMPT_BUDGET_CACHE_TTL_MS) return null
    return cached.budget
  })
  const [loading, setLoading] = useState(() => budget == null)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const budgetRef = useRef(budget)
  budgetRef.current = budget
  const specialistsRef = useRef(specialists)
  specialistsRef.current = specialists
  const skipNextFetchRef = useRef(budget != null)

  const selectedSpecialist =
    specialists.find(item => item.id === specialistId) || null
  const isEstimating = loading || refreshing

  useEffect(() => {
    if (!connected) return
    const controller = new AbortController()
    void onListSpecialists(controller.signal)
      .then(rows => {
        if (!controller.signal.aborted) {
          const next = rows.filter(item => item.enabled !== false)
          setSpecialists(next)
          if (promptBudgetCache) {
            promptBudgetCache = { ...promptBudgetCache, specialists: next }
          }
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setSpecialists([])
      })
    return () => controller.abort()
  }, [connected, onListSpecialists])

  const fetchBudget = useCallback(
    async (signal?: AbortSignal, soft = false) => {
      if (!connected) return
      if (soft) setRefreshing(true)
      else setLoading(true)
      setError(null)
      try {
        const next = await onGetPromptBudget(
          {
            specialistId: specialistId || null
          },
          signal
        )
        if (!signal?.aborted) {
          setBudget(next)
          promptBudgetCache = {
            specialistId,
            specialists: specialistsRef.current,
            budget: next,
            at: Date.now()
          }
        }
      } catch (err) {
        if (!signal?.aborted) {
          setError(err instanceof Error ? err.message : String(err))
        }
      } finally {
        if (!signal?.aborted) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    },
    [connected, onGetPromptBudget, specialistId]
  )

  useEffect(() => {
    // Remount with a warm cache for the same specialist — keep it, no recalculate.
    if (skipNextFetchRef.current) {
      skipNextFetchRef.current = false
      const cached = promptBudgetCache
      if (
        cached &&
        cached.specialistId === specialistId &&
        Date.now() - cached.at <= PROMPT_BUDGET_CACHE_TTL_MS
      ) {
        return
      }
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void fetchBudget(controller.signal, budgetRef.current != null)
    }, 300)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [fetchBudget, specialistId])

  const toolCounts = budget?.toolCounts
  const cap = toolCounts?.openaiCap || 128
  const totalTools = toolCounts?.total || 0
  const toolShare = Math.min(100, (totalTools / Math.max(cap, 1)) * 100)

  const stacked = useMemo(() => {
    const buckets = budget?.buckets || []
    const total = Math.max(budget?.totalTokens || 0, 1)
    return buckets.map((bucket, index) => ({
      id: bucket.id,
      label: bucket.label,
      tokens: bucket.tokens,
      share: (bucket.tokens / total) * 100,
      color: BUCKET_COLORS[index % BUCKET_COLORS.length]
    }))
  }, [budget])

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-3xl space-y-8 px-8 py-10">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold">Prompts</h2>
            <p className="text-muted-foreground mt-2 text-sm">
              Live estimate of input token context for the current runtime and
              specialist allowlist.
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-9 shrink-0"
            disabled={!connected || isEstimating}
            onClick={() => void fetchBudget(undefined, true)}
            aria-label="Refresh prompt budget"
          >
            <RefreshCw />
          </Button>
        </div>

        <section className="max-w-md space-y-1.5">
          <span className="text-muted-foreground text-sm">Specialist</span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild disabled={!connected}>
              <Button
                variant="outline"
                className="h-11 w-full justify-between gap-2 px-3 font-normal"
              >
                <span className="flex min-w-0 items-center gap-2.5">
                  {selectedSpecialist ? (
                    <SpecialistAvatar
                      color={selectedSpecialist.color}
                      icon={selectedSpecialist.icon}
                      className="size-7 rounded-lg"
                    />
                  ) : (
                    <span className="bg-muted flex size-7 shrink-0 items-center justify-center rounded-lg">
                      <span className="bg-muted-foreground/40 size-2 rounded-full" />
                    </span>
                  )}
                  <span className="truncate text-sm">
                    {selectedSpecialist?.name || 'None (defaults)'}
                  </span>
                </span>
                <ChevronDown className="text-muted-foreground size-4 shrink-0" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-72 p-1">
              <DropdownMenuLabel className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                Experiment with specialist
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="gap-2.5"
                onSelect={() => setSpecialistId('')}
              >
                <span className="bg-muted flex size-7 shrink-0 items-center justify-center rounded-lg">
                  <span className="bg-muted-foreground/40 size-2 rounded-full" />
                </span>
                <span className="min-w-0 flex-1 truncate">None (defaults)</span>
                {!specialistId ? (
                  <Check className="text-foreground ml-auto size-4 shrink-0" />
                ) : null}
              </DropdownMenuItem>
              {specialists.map(item => {
                const isSelected = item.id === specialistId
                return (
                  <DropdownMenuItem
                    key={item.id}
                    className="gap-2.5"
                    onSelect={() => setSpecialistId(item.id)}
                  >
                    <SpecialistAvatar
                      color={item.color}
                      icon={item.icon}
                      className="size-7 rounded-lg"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm">{item.name}</span>
                      <span className="text-muted-foreground block truncate text-[11px]">
                        {item.slug}
                      </span>
                    </span>
                    {isSelected ? (
                      <Check className="text-foreground ml-auto size-4 shrink-0" />
                    ) : null}
                  </DropdownMenuItem>
                )
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </section>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        {isEstimating && !budget ? (
          <div className="bg-muted/20 flex min-h-40 flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-4 py-10">
            <Loader2 className="text-muted-foreground size-5 animate-spin" />
            <div className="text-center">
              <p className="text-sm font-medium">Estimating input token context</p>
              <p className="text-muted-foreground mt-1 text-xs">
                Building the runtime prompt and tool schemas…
              </p>
            </div>
          </div>
        ) : budget ? (
          <div className="relative space-y-8">
            {isEstimating ? (
              <div className="bg-background/70 absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 rounded-xl backdrop-blur-[2px]">
                <Loader2 className="size-5 animate-spin" />
                <div className="text-center">
                  <p className="text-sm font-medium">
                    Recalculating input token estimate
                  </p>
                  <p className="text-muted-foreground mt-1 text-xs">
                    {selectedSpecialist
                      ? `Updating for ${selectedSpecialist.name}…`
                      : 'Updating for default runtime…'}
                  </p>
                </div>
              </div>
            ) : null}

            <div
              className={cn(
                'space-y-8 transition-opacity',
                isEstimating && 'pointer-events-none opacity-40'
              )}
              aria-busy={isEstimating}
            >
              <section className="space-y-4">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="text-muted-foreground text-xs uppercase tracking-wide">
                      Input token context
                    </p>
                    <p className="mt-1 text-3xl font-semibold tabular-nums">
                      {formatTokens(budget.totalTokens)}
                    </p>
                    <p className="text-muted-foreground mt-1 text-xs">
                      {budget.totalChars.toLocaleString()} chars ·{' '}
                      {budget.tokenizer}
                      {budget.toolMode ? ` · ${budget.toolMode}` : ''}
                      {budget.model ? ` · ${budget.model}` : ''}
                    </p>
                  </div>
                  {selectedSpecialist ? (
                    <div className="text-muted-foreground flex items-center gap-2 text-xs">
                      <SpecialistAvatar
                        color={selectedSpecialist.color}
                        icon={selectedSpecialist.icon}
                        className="size-6 rounded-md"
                      />
                      <span className="truncate">{selectedSpecialist.name}</span>
                    </div>
                  ) : null}
                </div>

                <div className="bg-muted/40 flex h-3 overflow-hidden rounded-full">
                  {stacked.map(slice => (
                    <div
                      key={slice.id}
                      className={cn(slice.color, 'h-full')}
                      style={{ width: `${Math.max(slice.share, 0.4)}%` }}
                      title={`${slice.label}: ${formatTokens(slice.tokens)}`}
                    />
                  ))}
                </div>
                <div className="flex flex-wrap gap-x-3 gap-y-1">
                  {stacked.map(slice => (
                    <div
                      key={slice.id}
                      className="text-muted-foreground flex items-center gap-1.5 text-xs"
                    >
                      <span
                        className={cn('size-2 rounded-full', slice.color)}
                      />
                      {slice.label}
                    </div>
                  ))}
                </div>
              </section>

              {toolCounts ? (
                <section className="space-y-3 rounded-xl border px-4 py-4">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold">Tool counts</h3>
                    <span
                      className={cn(
                        'font-mono text-xs',
                        totalTools > cap
                          ? 'text-amber-600 dark:text-amber-300'
                          : 'text-muted-foreground'
                      )}
                    >
                      {totalTools} / {cap}
                    </span>
                  </div>
                  <div className="bg-muted h-2 overflow-hidden rounded-full">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all',
                        totalTools > cap ? 'bg-amber-500' : 'bg-sky-500'
                      )}
                      style={{ width: `${toolShare}%` }}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {(
                      [
                        ['Domain', toolCounts.domain],
                        ['MCP', toolCounts.mcp],
                        ['DeepAgents', toolCounts.deepagents],
                        ['Total', toolCounts.total]
                      ] as const
                    ).map(([label, value]) => (
                      <div
                        key={label}
                        className="bg-muted/30 rounded-lg px-3 py-2"
                      >
                        <p className="text-muted-foreground text-[11px]">
                          {label}
                        </p>
                        <p className="mt-0.5 font-mono text-sm font-medium">
                          {value}
                        </p>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}

              <section className="space-y-2">
                <h3 className="text-sm font-semibold">Distribution</h3>
                <div className="divide-border/50 divide-y rounded-xl border">
                  {(budget.buckets || []).map((bucket, index) => (
                    <BucketRow
                      key={bucket.id}
                      bucket={bucket}
                      totalTokens={budget.totalTokens}
                      colorIndex={index}
                    />
                  ))}
                </div>
              </section>

              {budget.warnings.length > 0 ? (
                <section className="border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100 space-y-2 rounded-xl border px-4 py-3">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <AlertTriangle className="size-4 shrink-0" />
                    Warnings
                  </div>
                  <ul className="text-amber-800/90 dark:text-amber-200/90 list-disc space-y-1 pl-5 text-xs">
                    {budget.warnings.map(warning => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </ScrollArea>
  )
}
