import type {
  DatasetInstallResult,
  DatasetSummary
} from '@sandwalk/agent-ui-core'
import {
  Download,
  Loader2,
  RefreshCw,
  Search,
  Trash2
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { ListRowsSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'

export function DataView({
  onListDatasets,
  onInstallDataset,
  onRemoveDataset,
  embedded = false,
  bare = false,
  title = 'Datasets',
  description = "Local research datasets used by the agent's tools. Install open-access datasets directly; others require a manual download."
}: {
  onListDatasets: (signal?: AbortSignal) => Promise<DatasetSummary[]>
  onInstallDataset: (
    datasetId: string,
    signal?: AbortSignal
  ) => Promise<DatasetInstallResult>
  onRemoveDataset?: (
    datasetId: string,
    signal?: AbortSignal
  ) => Promise<DatasetInstallResult>
  embedded?: boolean
  /** Skip ScrollArea — for nesting inside another scroll parent. */
  bare?: boolean
  title?: string
  description?: string
}) {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [installing, setInstalling] = useState<Record<string, boolean>>({})
  const [removing, setRemoving] = useState<Record<string, boolean>>({})
  const [notice, setNotice] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return datasets
    return datasets.filter(dataset =>
      [dataset.id, dataset.description, dataset.status]
        .join(' ')
        .toLowerCase()
        .includes(needle)
    )
  }, [datasets, query])

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const next = await onListDatasets(signal)
      if (!signal?.aborted) setDatasets(next)
    },
    [onListDatasets]
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

  const install = async (dataset: DatasetSummary) => {
    setInstalling(prev => ({ ...prev, [dataset.id]: true }))
    setError(null)
    setNotice(null)
    try {
      const result = await onInstallDataset(dataset.id)
      setNotice(result.summary)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setInstalling(prev => {
        const next = { ...prev }
        delete next[dataset.id]
        return next
      })
    }
  }

  const remove = async (dataset: DatasetSummary) => {
    if (!onRemoveDataset) return
    setRemoving(prev => ({ ...prev, [dataset.id]: true }))
    setError(null)
    setNotice(null)
    try {
      const result = await onRemoveDataset(dataset.id)
      setNotice(result.summary)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRemoving(prev => {
        const next = { ...prev }
        delete next[dataset.id]
        return next
      })
    }
  }

  const body = (
    <div
      className={
        bare
          ? 'flex w-full flex-col'
          : embedded
            ? 'mx-auto flex w-full max-w-5xl flex-col p-1'
            : 'mx-auto flex w-full max-w-7xl flex-col p-4 md:p-6'
      }
    >
      {!embedded && !bare ? (
        <div className="mb-4">
          <h2 className="text-2xl font-semibold">{title}</h2>
          <p className="text-muted-foreground mt-1 text-sm">{description}</p>
        </div>
      ) : null}

      {(embedded || bare) && title ? (
        <div className="mb-3">
          <p className="text-muted-foreground text-xs font-medium">{title}</p>
          {description ? (
            <p className="text-muted-foreground mt-1 text-sm">{description}</p>
          ) : null}
        </div>
      ) : null}

      <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 mb-4 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
        <div className="relative min-w-[240px] flex-1">
          <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
          <Input
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Search datasets, descriptions..."
            className="border-border/70 bg-background/70 h-11 pl-10"
          />
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-9 shrink-0"
          disabled={refreshing || loading}
          onClick={() => void refresh()}
          aria-label="Refresh datasets"
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
      {notice ? (
        <div className="bg-muted/40 text-foreground mb-4 rounded-md border px-3 py-2 text-sm">
          {notice}
        </div>
      ) : null}

      <div className="bg-muted/20 border-border/60 divide-y overflow-hidden rounded-xl border shadow-sm">
        {loading && datasets.length === 0 ? (
          <ListRowsSkeleton rows={6} withToggle={false} />
        ) : filtered.length === 0 ? (
          <div className="text-muted-foreground px-4 py-8 text-sm">
            No datasets match this search.
          </div>
        ) : (
          filtered.map(dataset => {
            const busy =
              Boolean(installing[dataset.id]) || Boolean(removing[dataset.id])
            const canInstall =
              dataset.autoDownload && dataset.status !== 'complete'
            const canRemove =
              Boolean(onRemoveDataset) &&
              (dataset.status === 'complete' || dataset.status === 'partial')
            return (
              <div key={dataset.id} className="flex gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-medium">
                      {dataset.id}
                    </span>
                    {dataset.autoDownload ? (
                      <span className="text-muted-foreground text-xs">
                        auto-download
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">
                        manual
                      </span>
                    )}
                  </div>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {dataset.description}
                  </p>
                  <div className="text-muted-foreground mt-1 text-xs">
                    <span className="font-mono">{dataset.path}</span>
                  </div>
                  {dataset.note ? (
                    <p className="text-muted-foreground mt-1 text-xs italic">
                      {dataset.note}
                    </p>
                  ) : null}
                  {!dataset.autoDownload && dataset.source ? (
                    <a
                      href={dataset.source}
                      target="_blank"
                      rel="noreferrer"
                      className="text-foreground mt-1 inline-block text-xs underline underline-offset-2"
                    >
                      Download source
                    </a>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  {canInstall ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      onClick={() => void install(dataset)}
                    >
                      {installing[dataset.id] ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <Download className="size-3.5" />
                      )}
                      {dataset.status === 'partial' ? 'Resume' : 'Install'}
                    </Button>
                  ) : null}
                  {canRemove ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-muted-foreground hover:text-destructive size-8"
                      disabled={busy}
                      onClick={() => void remove(dataset)}
                      aria-label={`Remove ${dataset.id}`}
                      title="Remove"
                    >
                      {removing[dataset.id] ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="size-3.5" />
                      )}
                    </Button>
                  ) : null}
                  <div className="text-muted-foreground text-right text-xs">
                    {dataset.filesExpected > 0 ? (
                      <div>
                        Files: {dataset.filesFound}/{dataset.filesExpected}
                      </div>
                    ) : null}
                    <div>Size: {dataset.sizeDisplay}</div>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      <p className="text-muted-foreground mt-4 text-xs">
        Large datasets can take several minutes to download. Installs run on the
        local agent; progress is written to the agent server logs.
      </p>
    </div>
  )

  if (bare) return body

  return (
    <ScrollArea className={embedded ? 'h-[min(28rem,55vh)]' : 'flex-1'}>
      {body}
    </ScrollArea>
  )
}
