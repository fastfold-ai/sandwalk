import type {
  DatasetSummary,
  ToolBatchAction,
  ToolBatchResult,
  ToolCatalog,
  ToolSummary
} from '@sandwalk/agent-ui-core'
import {
  Check,
  Database,
  Loader2,
  RefreshCw,
  Search,
  TriangleAlert
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { ListRowsSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

function ToolToggle({
  enabled,
  pending,
  label,
  onToggle
}: {
  enabled: boolean
  pending?: boolean
  label: string
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      disabled={pending}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700',
        pending && 'cursor-not-allowed opacity-60'
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onToggle()
      }}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          enabled ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}

function statusClass(status: ToolSummary['status']) {
  if (status === 'experimental')
    return 'text-amber-700 bg-amber-500/10 dark:text-amber-300'
  if (status === 'guarded')
    return 'text-violet-700 bg-violet-500/10 dark:text-violet-300'
  return 'text-muted-foreground bg-muted'
}

export function ToolsView({
  onListTools,
  onUpdateToolEnabled,
  onBatchUpdateTools,
  onListDatasets,
  onOpenData
}: {
  onListTools: (signal?: AbortSignal) => Promise<ToolCatalog>
  onUpdateToolEnabled: (
    toolId: string,
    enabled: boolean,
    signal?: AbortSignal
  ) => Promise<ToolSummary>
  onBatchUpdateTools: (
    action: ToolBatchAction,
    ids: string[],
    signal?: AbortSignal
  ) => Promise<ToolBatchResult>
  onListDatasets: (signal?: AbortSignal) => Promise<DatasetSummary[]>
  onOpenData: () => void
}) {
  const [catalog, setCatalog] = useState<ToolCatalog | null>(null)
  const [datasets, setDatasets] = useState<DatasetSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'enabled' | 'disabled'
  >('all')
  const [pending, setPending] = useState<Record<string, boolean>>({})
  const [batchBusy, setBatchBusy] = useState(false)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const [nextTools, nextDatasets] = await Promise.all([
        onListTools(signal),
        onListDatasets(signal).catch(() => [] as DatasetSummary[])
      ])
      if (!signal?.aborted) {
        setCatalog(nextTools)
        setDatasets(nextDatasets)
      }
    },
    [onListTools, onListDatasets]
  )

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    void load(controller.signal)
      .catch(err => {
        if (!controller.signal.aborted)
          setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [load])

  const refresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRefreshing(false)
    }
  }

  const tools = catalog?.data || []

  const categories = useMemo(() => {
    const present = new Set(tools.map(t => t.category))
    return [...present].sort((a, b) => a.localeCompare(b))
  }, [tools])

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const tool of tools) {
      counts[tool.category] = (counts[tool.category] || 0) + 1
    }
    return counts
  }, [tools])

  const enabledCount = tools.filter(t => t.enabled).length
  const disabledCount = tools.length - enabledCount

  // Map a requires_data token (e.g. "depmap_mutations") to a known dataset id
  // (e.g. "depmap") and its install status.
  const datasetStatusById = useMemo(() => {
    const map = new Map<string, DatasetSummary['status']>()
    for (const dataset of datasets) map.set(dataset.id, dataset.status)
    return map
  }, [datasets])

  const resolveRequirement = useCallback(
    (token: string) => {
      const normalized = token.trim().toLowerCase()
      let datasetId: string | null = null
      if (datasetStatusById.has(normalized)) {
        datasetId = normalized
      } else {
        const prefix = normalized.split('_')[0]
        if (datasetStatusById.has(prefix)) datasetId = prefix
      }
      if (!datasetId) return { datasetId: null, installed: null as boolean | null }
      const status = datasetStatusById.get(datasetId)
      const installed = status === 'complete' || status === 'on-demand'
      return { datasetId, installed }
    },
    [datasetStatusById]
  )

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return tools.filter(tool => {
      if (categoryFilter !== 'all' && tool.category !== categoryFilter)
        return false
      if (statusFilter === 'enabled' && !tool.enabled) return false
      if (statusFilter === 'disabled' && tool.enabled) return false
      if (!needle) return true
      const haystack = [
        tool.id,
        tool.description,
        tool.category,
        tool.requiresData.join(' ')
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [tools, query, categoryFilter, statusFilter])

  const enableEligible = useMemo(
    () => filtered.filter(t => !t.enabled).map(t => t.id),
    [filtered]
  )
  const disableEligible = useMemo(
    () => filtered.filter(t => t.enabled).map(t => t.id),
    [filtered]
  )

  const batchUpdate = async (action: ToolBatchAction) => {
    const ids = action === 'enable' ? enableEligible : disableEligible
    if (ids.length === 0) return
    setBatchBusy(true)
    setError(null)
    try {
      const result = await onBatchUpdateTools(action, ids)
      const succeeded = new Set(result.succeeded)
      const nextEnabled = action === 'enable'
      setCatalog(prev =>
        prev
          ? {
              ...prev,
              data: prev.data.map(item =>
                succeeded.has(item.id)
                  ? { ...item, enabled: nextEnabled }
                  : item
              )
            }
          : prev
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBatchBusy(false)
    }
  }

  const toggle = async (tool: ToolSummary) => {
    setPending(prev => ({ ...prev, [tool.id]: true }))
    setError(null)
    try {
      const updated = await onUpdateToolEnabled(tool.id, !tool.enabled)
      setCatalog(prev =>
        prev
          ? {
              ...prev,
              data: prev.data.map(item =>
                item.id === tool.id
                  ? { ...item, enabled: updated.enabled }
                  : item
              )
            }
          : prev
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setPending(prev => {
        const next = { ...prev }
        delete next[tool.id]
        return next
      })
    }
  }

  const filterButtonClass = (active: boolean) =>
    cn(
      'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
      active
        ? 'bg-muted text-foreground'
        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
    )

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6 xl:flex-row">
        <div className="min-w-0 flex-1">
          <div className="mb-4">
            <h2 className="text-2xl font-semibold">Tools</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Research tools available to the agent. Toggle a tool off to hide it
              from the agent's discovery and calls.
            </p>
          </div>

          <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 mb-4 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
            <div className="relative min-w-[240px] flex-1">
              <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
              <Input
                value={query}
                onChange={event => setQuery(event.target.value)}
                placeholder="Search tools by name, description, or dataset"
                className="border-border/70 bg-background/70 h-11 pl-10"
              />
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="size-9 shrink-0"
              disabled={refreshing || loading}
              onClick={() => void refresh()}
              aria-label="Refresh tools"
            >
              {refreshing || loading ? (
                <Loader2 className="animate-spin" />
              ) : (
                <RefreshCw />
              )}
            </Button>
          </div>

          {error ? (
            <div className="border-destructive/40 text-destructive mb-4 rounded-md border px-3 py-2 text-sm">
              {error}
            </div>
          ) : null}

          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="text-muted-foreground text-xs">
              {enabledCount} of {tools.length} tools enabled
              {catalog && filtered.length !== tools.length
                ? ` · showing ${filtered.length}`
                : ''}
            </p>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground h-7 text-xs"
                disabled={batchBusy || enableEligible.length === 0}
                onClick={() => void batchUpdate('enable')}
              >
                {batchBusy ? (
                  <Loader2 className="animate-spin" />
                ) : null}
                Enable ({enableEligible.length})
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground h-7 text-xs"
                disabled={batchBusy || disableEligible.length === 0}
                onClick={() => void batchUpdate('disable')}
              >
                {batchBusy ? (
                  <Loader2 className="animate-spin" />
                ) : null}
                Disable ({disableEligible.length})
              </Button>
            </div>
          </div>

          <div className="bg-muted/20 border-border/60 divide-y overflow-hidden rounded-xl border shadow-sm">
            {loading && tools.length === 0 ? (
              <ListRowsSkeleton rows={8} />
            ) : filtered.length === 0 ? (
              <div className="text-muted-foreground px-4 py-8 text-sm">
                No tools match this search.
              </div>
            ) : (
              filtered.map(tool => (
                <div
                  key={tool.id}
                  className="flex items-start justify-between gap-3 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium">
                        {tool.id}
                      </span>
                      {tool.status !== 'stable' ? (
                        <span
                          className={cn(
                            'rounded-full px-2 py-0.5 text-xs font-medium',
                            statusClass(tool.status)
                          )}
                        >
                          {tool.status}
                        </span>
                      ) : null}
                    </div>
                    <p className="text-muted-foreground mt-1 text-sm">
                      {tool.description}
                    </p>
                    {tool.requiresData.length > 0 ? (
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <span className="text-muted-foreground text-xs">
                          Requires:
                        </span>
                        {tool.requiresData.map(req => {
                          const { installed } = resolveRequirement(req)
                          return (
                            <button
                              key={req}
                              type="button"
                              onClick={onOpenData}
                              title={
                                installed === null
                                  ? undefined
                                  : installed
                                    ? 'Dataset installed'
                                    : 'Dataset not installed'
                              }
                              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 font-mono text-[11px]"
                            >
                              {installed === true ? (
                                <Check className="size-3 text-emerald-600" />
                              ) : installed === false ? (
                                <TriangleAlert className="size-3 text-amber-600" />
                              ) : (
                                <Database className="size-3" />
                              )}
                              {req}
                            </button>
                          )
                        })}
                      </div>
                    ) : null}
                  </div>
                  <ToolToggle
                    enabled={tool.enabled}
                    pending={Boolean(pending[tool.id])}
                    label={`${tool.enabled ? 'Disable' : 'Enable'} ${tool.id}`}
                    onToggle={() => void toggle(tool)}
                  />
                </div>
              ))
            )}
          </div>
        </div>

        <aside className="flex w-full shrink-0 flex-col gap-4 xl:sticky xl:top-4 xl:self-start xl:w-[280px]">
          <section className="bg-background/70 rounded-lg p-2">
            <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
              Status
            </div>
            <button
              type="button"
              className={filterButtonClass(statusFilter === 'all')}
              onClick={() => setStatusFilter('all')}
            >
              All ({tools.length})
            </button>
            <button
              type="button"
              className={filterButtonClass(statusFilter === 'enabled')}
              onClick={() => setStatusFilter('enabled')}
            >
              Enabled ({enabledCount})
            </button>
            <button
              type="button"
              className={filterButtonClass(statusFilter === 'disabled')}
              onClick={() => setStatusFilter('disabled')}
            >
              Disabled ({disabledCount})
            </button>
          </section>
          <section className="bg-background/70 flex min-h-0 flex-col rounded-lg p-2 xl:max-h-[calc(100vh-14rem)]">
            <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
              Categories
            </div>
            <ScrollArea className="min-h-0 flex-1 pr-2">
              <button
                type="button"
                className={filterButtonClass(categoryFilter === 'all')}
                onClick={() => setCategoryFilter('all')}
              >
                All ({tools.length})
              </button>
              {categories.map(category => (
                <button
                  key={category}
                  type="button"
                  className={filterButtonClass(categoryFilter === category)}
                  onClick={() => setCategoryFilter(category)}
                >
                  {category} ({categoryCounts[category] || 0})
                </button>
              ))}
            </ScrollArea>
          </section>
        </aside>
      </div>
    </ScrollArea>
  )
}
