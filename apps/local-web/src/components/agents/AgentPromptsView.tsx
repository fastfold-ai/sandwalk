import type {
  PromptBudgetResponse,
  RuntimeSettings,
  Specialist
} from '@sandwalk/agent-ui-core'
import { Check, ChevronDown, Loader, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

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

import {
  type KnowledgeLevel,
  KnowledgeLevelControl,
  knowledgeLevelFromSettings} from './prompts-view/knowledge-level-control'
import { PromptBudgetResults } from './prompts-view/prompt-budget-results'
import {
  patchPromptBudgetSpecialists,
  PROMPT_BUDGET_CACHE_TTL_MS,
  promptBudgetCache,
  readTokenCountMethod,
  type TokenCountMethod,
  writePromptBudgetCache,
  writeTokenCountMethod
} from './prompts-view/prompt-budget-shared'

export function AgentPromptsView({
  connected,
  onGetPromptBudget,
  onListSpecialists,
  onGetRuntimeSettings,
  onUpdateRuntimeSettings
}: {
  connected: boolean
  onGetPromptBudget: (
    options?: {
      specialistId?: string | null
      projectId?: string | null
      sampleQuery?: string | null
      tokenCountMethod?: TokenCountMethod | null
    },
    signal?: AbortSignal
  ) => Promise<PromptBudgetResponse>
  onListSpecialists: (signal?: AbortSignal) => Promise<Specialist[]>
  onGetRuntimeSettings: (signal?: AbortSignal) => Promise<RuntimeSettings>
  onUpdateRuntimeSettings: (
    changes: Partial<RuntimeSettings>,
    signal?: AbortSignal
  ) => Promise<RuntimeSettings>
}) {
  const [specialists, setSpecialists] = useState<Specialist[]>(
    () => promptBudgetCache?.specialists || []
  )
  const [specialistId, setSpecialistId] = useState(
    () => promptBudgetCache?.specialistId || ''
  )
  const [tokenCountMethod, setTokenCountMethod] = useState<TokenCountMethod>(
    () => promptBudgetCache?.tokenCountMethod || readTokenCountMethod()
  )
  const [budget, setBudget] = useState<PromptBudgetResponse | null>(() => {
    const cached = promptBudgetCache
    if (!cached) return null
    if (Date.now() - cached.at > PROMPT_BUDGET_CACHE_TTL_MS) return null
    if (cached.tokenCountMethod !== readTokenCountMethod()) return null
    return cached.budget
  })
  const [loading, setLoading] = useState(() => budget == null)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [knowledgeLevel, setKnowledgeLevel] = useState<KnowledgeLevel>('high')
  const [savingLevel, setSavingLevel] = useState(false)
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
    void onGetRuntimeSettings(controller.signal)
      .then(settings => {
        if (!controller.signal.aborted) {
          setKnowledgeLevel(knowledgeLevelFromSettings(settings))
        }
      })
      .catch(() => {
        /* keep default high */
      })
    return () => controller.abort()
  }, [connected, onGetRuntimeSettings])

  useEffect(() => {
    if (!connected) return
    const controller = new AbortController()
    void onListSpecialists(controller.signal)
      .then(rows => {
        if (!controller.signal.aborted) {
          const next = rows.filter(item => item.enabled !== false)
          setSpecialists(next)
          if (promptBudgetCache) {
            patchPromptBudgetSpecialists(next)
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
      const localAbort = new AbortController()
      const onOuterAbort = () => localAbort.abort()
      signal?.addEventListener('abort', onOuterAbort)
      // Client-side ceiling so Context never spins forever if MCP/skill
      // staging wedges the server-side estimate.
      const timeout = window.setTimeout(() => localAbort.abort(), 50_000)
      try {
        const next = await onGetPromptBudget(
          {
            specialistId: specialistId || null,
            tokenCountMethod
          },
          localAbort.signal
        )
        if (!signal?.aborted && !localAbort.signal.aborted) {
          setBudget(next)
          writePromptBudgetCache({
            specialistId,
            tokenCountMethod,
            specialists: specialistsRef.current,
            budget: next,
            at: Date.now()
          })
        }
      } catch (err) {
        if (!signal?.aborted) {
          const message = err instanceof Error ? err.message : String(err)
          setError(
            /aborted|abort/i.test(message)
              ? 'Context estimate timed out. Disable hung MCP servers and retry.'
              : message
          )
        }
      } finally {
        window.clearTimeout(timeout)
        signal?.removeEventListener('abort', onOuterAbort)
        if (!signal?.aborted) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    },
    [connected, onGetPromptBudget, specialistId, tokenCountMethod]
  )

  useEffect(() => {
    if (skipNextFetchRef.current) {
      skipNextFetchRef.current = false
      const cached = promptBudgetCache
      if (
        cached &&
        cached.specialistId === specialistId &&
        cached.tokenCountMethod === tokenCountMethod &&
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
  }, [fetchBudget, specialistId, tokenCountMethod])

  const handleTokenCountMethod = useCallback((next: TokenCountMethod) => {
    setTokenCountMethod(next)
    writeTokenCountMethod(next)
  }, [])

  const handleKnowledgeLevel = useCallback(
    async (next: KnowledgeLevel) => {
      if (!connected) return
      // Optimistic UI so the slider does not snap back while the PATCH runs.
      setKnowledgeLevel(next)
      setSavingLevel(true)
      setError(null)
      try {
        const updated = await onUpdateRuntimeSettings({
          knowledgeLevel: next
        })
        setKnowledgeLevel(knowledgeLevelFromSettings(updated))
        await fetchBudget(undefined, true)
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setSavingLevel(false)
      }
    },
    [connected, fetchBudget, onUpdateRuntimeSettings]
  )

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-7xl space-y-8 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold">Context</h2>
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

        <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(16rem,20rem)] md:items-start">
          <KnowledgeLevelControl
            connected={connected}
            value={knowledgeLevel}
            saving={savingLevel}
            onChange={handleKnowledgeLevel}
          />

          <section className="space-y-1.5">
            <span className="text-sm font-medium">Specialist</span>
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
                      <span className="bg-muted/40 flex size-7 shrink-0 items-center justify-center rounded-lg">
                        <span className="bg-muted-foreground/30 size-2 rounded-full" />
                      </span>
                    )}
                    <span className="truncate text-sm">
                      {selectedSpecialist?.name || 'None (defaults)'}
                    </span>
                  </span>
                  <ChevronDown className="text-muted-foreground size-4 shrink-0" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-72 p-1"
              >
                <DropdownMenuLabel className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                  Experiment with specialist
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="gap-2.5"
                  onSelect={() => setSpecialistId('')}
                >
                  <span className="bg-muted/40 flex size-7 shrink-0 items-center justify-center rounded-lg">
                    <span className="bg-muted-foreground/30 size-2 rounded-full" />
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
                        <span className="block truncate text-sm">
                          {item.name}
                        </span>
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
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        {isEstimating && !budget ? (
          <div className="bg-muted/20 flex min-h-40 flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-4 py-10">
            <Loader className="text-muted-foreground size-5 animate-spin" />
            <div className="text-center">
              <p className="text-sm font-medium">Estimating input token context</p>
              <p className="text-muted-foreground mt-1 text-xs">
                Building the runtime prompt and tool schemas…
              </p>
            </div>
          </div>
        ) : budget ? (
          <PromptBudgetResults
            budget={budget}
            selectedSpecialist={selectedSpecialist}
            isEstimating={isEstimating}
            tokenCountMethod={tokenCountMethod}
            onTokenCountMethodChange={handleTokenCountMethod}
            countingDisabled={!connected || isEstimating}
          />
        ) : null}
      </div>
    </ScrollArea>
  )
}
