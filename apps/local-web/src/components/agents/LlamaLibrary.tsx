import type {
  LlamaCatalog,
  LlamaCatalogModel,
  LlamaRuntimeStatus
} from '@sandwalk/agent-local-client'
import { Check, Loader } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import { formatContext, parseModelId } from './llama-model-label'
import { LlamaRuntimeButton } from './LlamaRuntimeButton'

export type LlamaLibraryActions = {
  load: () => Promise<LlamaRuntimeStatus>
  ensure: () => Promise<LlamaRuntimeStatus>
  catalog: (query?: string) => Promise<LlamaCatalog>
  install: (repo: string, quant?: string | null) => Promise<{ ok: boolean }>
  remove: (modelId: string) => Promise<{ ok: boolean }>
  loadModel: (modelId: string) => Promise<{ ok: boolean }>
  unloadModel: (modelId: string) => Promise<{ ok: boolean }>
  update: () => Promise<LlamaRuntimeStatus>
}

export function LlamaLibrary({
  actions,
  selectedId,
  onUse
}: {
  actions: LlamaLibraryActions
  selectedId: string | null
  onUse: (modelId: string) => void
}) {
  const [status, setStatus] = useState<LlamaRuntimeStatus | null>(null)
  const [catalog, setCatalog] = useState<LlamaCatalog | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [installing, setInstalling] = useState<string | null>(null)
  const [catalogError, setCatalogError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const next = await actions.load()
    setStatus(next)
    if (!next.running) {
      setCatalog(null)
      return
    }
    if (typeof actions.catalog !== 'function') {
      setCatalogError('Reload the window to load the Llama catalog.')
      setCatalog({
        installed: next.models.map(id => ({
          id,
          context: null,
          size: null,
          vision: false,
          state: 'unloaded',
          error: null
        })),
        recommended: []
      })
      return
    }
    setLoading(true)
    try {
      setCatalog(await actions.catalog(query))
      setCatalogError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not load the Llama catalog'
      setCatalogError(message)
    } finally {
      setLoading(false)
    }
  }, [actions, query])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const somethingLoading = (catalog?.installed || []).some(
    model => model.state === 'loading'
  )
  const installingNow = status?.phase === 'installing' || installing != null

  useEffect(() => {
    if (status?.phase === 'ready' || status?.phase === 'error') {
      setInstalling(null)
    }
  }, [status?.phase])

  useEffect(() => {
    if (
      status?.running &&
      status.phase !== 'installing' &&
      status.phase !== 'opening' &&
      status.phase !== 'updating' &&
      !somethingLoading &&
      installing == null
    ) {
      return
    }
    const timer = window.setInterval(() => {
      void refresh()
    }, status?.phase === 'installing' ? 1000 : 3000)
    return () => window.clearInterval(timer)
  }, [installing, refresh, somethingLoading, status?.phase, status?.running])

  if (!status?.running) {
    return <LlamaRuntimeButton load={actions.load} ensure={actions.ensure} />
  }

  const searching = Boolean(query.trim())
  const installed = searching ? [] : catalog?.installed || []
  const recommended = (catalog?.recommended || []).filter(item =>
    searching ? true : !item.installed
  )
  const activeRepo = status.install?.repo || null
  const activeQuant = status.install?.quant || null
  const isDownloading = (item: LlamaCatalogModel) =>
    status.phase === 'installing' &&
    item.repo === activeRepo &&
    (item.quant || null) === (activeQuant || null)
  const orderedRecommended = [...recommended].sort(
    (a, b) => Number(isDownloading(b)) - Number(isDownloading(a))
  )

  const progress = status.log?.length
    ? status.log
    : status.detail
      ? [status.detail]
      : []

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-muted-foreground truncate font-mono text-[11px]">
          localhost:9931
          {status.version ? ` · ${status.version}` : ''}
        </p>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground inline-flex shrink-0 items-center gap-1 text-xs"
          disabled={status.phase === 'updating'}
          onClick={() => {
            void actions.update().then(setStatus)
          }}
        >
          {status.phase === 'updating' ? (
            <Loader className="size-3.5 animate-spin" />
          ) : null}
          Update
        </button>
      </div>
      {installingNow || status.phase === 'error' ? (
        <pre
          className={cn(
            'max-h-28 overflow-auto rounded-lg px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap',
            status.phase === 'error'
              ? 'bg-destructive/10 text-destructive'
              : 'bg-muted/60 text-foreground'
          )}
        >
          {progress.join('\n') || 'Starting download…'}
        </pre>
      ) : null}
      <Input
        value={query}
        onChange={event => setQuery(event.target.value)}
        placeholder="Search models"
      />
      {loading && !catalog ? (
        <p className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader className="size-4 animate-spin" />
          Loading models…
        </p>
      ) : null}

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
      {searching ? null : (
      <section className="space-y-1">
        <p className="text-muted-foreground text-xs">Installed</p>
        <div className="space-y-1">
          {installed.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No installed models match. Download one below.
            </p>
          ) : (
            installed.map(model => (
              <ModelRow
                key={model.id}
                id={model.id}
                detail={[
                  model.size,
                  formatContext(model.context),
                  model.state === 'loaded' || model.state === 'ready'
                    ? 'Ready'
                    : model.state === 'loading'
                      ? 'Loading'
                      : model.state === 'failed'
                        ? 'Failed to load'
                        : 'Unloaded'
                ]
                  .filter(Boolean)
                  .join(' · ')}
                selected={selectedId === model.id}
                action={
                  model.state === 'loading'
                    ? 'Loading'
                    : model.state === 'loaded' || model.state === 'ready'
                      ? 'Unload'
                      : 'Load'
                }
                spinning={model.state === 'loading'}
                onAction={() => {
                  if (model.state === 'loaded' || model.state === 'ready') {
                    void actions.unloadModel(model.id).then(() => refresh())
                    return
                  }
                  if (model.state === 'loading') return
                  void actions.loadModel(model.id).then(() => refresh())
                }}
                onUse={
                  selectedId === model.id ? undefined : () => onUse(model.id)
                }
                onRemove={() => {
                  const label = parseModelId(model.id).name || model.id
                  if (
                    !window.confirm(
                      `Remove ${label} from this machine? The downloaded files will be deleted.`
                    )
                  ) {
                    return
                  }
                  void actions.remove(model.id).then(() => refresh()).catch(err =>
                    toast.error(
                      err instanceof Error ? err.message : 'Could not remove the model'
                    )
                  )
                }}
              />
            ))
          )}
        </div>
      </section>
      )}

      <section className="space-y-1">
        <p className="text-muted-foreground text-xs">
          {query.trim() ? 'Catalog' : 'Recommended for this machine'}
        </p>
        <div className="space-y-1">
          {orderedRecommended.map(item => (
            <CatalogRow
              key={`${item.repo}:${item.quant || ''}`}
              item={item}
              busy={installing === item.repo || isDownloading(item)}
              downloading={isDownloading(item)}
              onInstall={() => {
                setInstalling(item.repo)
                void actions.install(item.repo, item.quant).catch(err => {
                  setInstalling(null)
                  toast.error(
                    err instanceof Error ? err.message : 'Could not start the download'
                  )
                })
              }}
            />
          ))}
          {orderedRecommended.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              {catalogError ||
                (searching
                  ? 'No catalog matches.'
                  : 'No recommendations for this machine.')}
            </p>
          ) : null}
        </div>
      </section>
      </div>
    </div>
  )
}

function ModelTitle({ id }: { id: string }) {
  const parsed = parseModelId(id)
  return (
    <span className="flex min-w-0 items-center gap-1.5">
      <span className="truncate text-sm">
        {parsed.org ? (
          <span className="text-muted-foreground">{parsed.org}/</span>
        ) : null}
        {parsed.name}
      </span>
      {parsed.params ? (
        <span className="border-border text-muted-foreground shrink-0 rounded border px-1 py-px text-[10px] leading-4 font-medium">
          {parsed.params}
        </span>
      ) : null}
      {parsed.quant ? (
        <span className="bg-muted text-muted-foreground shrink-0 rounded-full px-1.5 py-px text-[10px] leading-4 font-medium">
          {parsed.quant}
        </span>
      ) : null}
    </span>
  )
}

function ModelRow({
  id,
  detail,
  selected,
  action,
  spinning,
  downloading,
  onAction,
  onUse,
  onRemove
}: {
  id: string
  detail: string
  selected: boolean
  action: string
  spinning?: boolean
  downloading?: boolean
  onAction: () => void
  onUse?: () => void
  onRemove?: () => void
}) {
  return (
    <div
      className={cn(
        'flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left',
        downloading
          ? 'border-amber-500/70 bg-amber-500/10'
          : selected
            ? 'border-foreground bg-muted/40'
            : 'border-border/60'
      )}
    >
      <span className="min-w-0 flex-1">
        <ModelTitle id={id} />
        {detail ? (
          <span className="text-muted-foreground mt-0.5 block truncate text-xs">
            {detail}
          </span>
        ) : null}
      </span>
      {onUse ? (
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground shrink-0 text-xs"
          onClick={onUse}
        >
          Set as default
        </button>
      ) : selected ? (
        <span className="inline-flex shrink-0 items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
          <Check className="size-3.5" />
          Default
        </span>
      ) : null}
      {onRemove ? (
        <button
          type="button"
          className="text-muted-foreground hover:text-destructive shrink-0 text-xs"
          onClick={onRemove}
        >
          Remove
        </button>
      ) : null}
      <button
        type="button"
        disabled={spinning}
        className={cn(
          'inline-flex shrink-0 items-center gap-1 text-xs disabled:opacity-70',
          downloading
            ? 'text-amber-700 dark:text-amber-300'
            : 'text-muted-foreground hover:text-foreground'
        )}
        onClick={onAction}
      >
        {spinning ? <Loader className="size-3.5 animate-spin" /> : null}
        {downloading ? 'Downloading' : action}
      </button>
    </div>
  )
}

function CatalogRow({
  item,
  busy,
  downloading,
  onInstall
}: {
  item: LlamaCatalogModel
  busy: boolean
  downloading?: boolean
  onInstall: () => void
}) {
  return (
    <ModelRow
      id={item.id || item.repo}
      detail={item.size || ''}
      selected={item.installed}
      downloading={downloading}
      action={item.installed ? 'Installed' : busy ? 'Installing…' : 'Install'}
      spinning={busy}
      onAction={onInstall}
    />
  )
}

/** Stays on the Llama card after the dialog closes, so a long download remains visible. */
export function LlamaInstallNotice({
  actions
}: {
  actions: LlamaLibraryActions
}) {
  const [status, setStatus] = useState<LlamaRuntimeStatus | null>(null)

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const next = await actions.load()
        if (!cancelled) setStatus(next)
      } catch {
        // The card stays quiet if the status call fails.
      }
    }
    void tick()
    const timer = window.setInterval(() => void tick(), 1000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [actions])

  if (status?.phase !== 'installing' && status?.phase !== 'error') return null
  const line = status.detail || status.log?.at(-1) || status.install?.spec || ''
  const failed = status.phase === 'error'
  return (
    <div
      className={cn(
        'rounded-lg px-3 py-2 text-xs',
        failed
          ? 'bg-destructive/10 text-destructive'
          : 'bg-amber-500/10 text-amber-800 dark:text-amber-200'
      )}
    >
      <p className="font-medium">{failed ? 'Download failed' : 'Downloading'}</p>
      {line ? <p className="mt-1 font-mono text-[11px] leading-relaxed">{line}</p> : null}
    </div>
  )
}
