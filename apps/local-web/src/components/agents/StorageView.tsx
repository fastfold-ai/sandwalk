import type { StorageCategory, StorageReport } from '@sandwalk/agent-ui-core'
import { ChevronDown, HardDrive, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { SettingsBlockSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

function formatBytes(bytes: number): string {
  const value = Math.max(0, bytes)
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB'] as const
  let n = value / 1024
  for (let i = 0; i < units.length; i += 1) {
    if (n < 1024 || i === units.length - 1) {
      return `${n.toFixed(1)} ${units[i]}`
    }
    n /= 1024
  }
  return `${value} B`
}

export function StorageView({
  onLoad
}: {
  onLoad: (signal?: AbortSignal) => Promise<StorageReport>
}) {
  const [report, setReport] = useState<StorageReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true)
      setError(null)
      try {
        const next = await onLoad(signal)
        if (signal?.aborted) return
        setReport(next)
      } catch (err) {
        if (signal?.aborted) return
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [onLoad]
  )

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const categories = report?.categories || []
  const totalBytes = report?.totalBytes || 0
  const availableBytes = report?.availableBytes || 0

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-8 py-10">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold">Storage</h2>
            <p className="text-muted-foreground mt-2 text-sm">
              Where FastFold Agent keeps projects, datasets, chat files, and
              history on this machine — plus the Python environment used by the
              built-in code sandbox.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading}
            onClick={() => void load()}
          >
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        <section className="space-y-3 border-b pb-8">
          <h3 className="text-base font-semibold">Data location</h3>
          <p className="text-muted-foreground text-sm">
            Local home for agent config, workspaces, sessions, and installed
            datasets.
          </p>
          {loading && !report ? (
            <SettingsBlockSkeleton />
          ) : report ? (
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0 space-y-1">
                <div className="flex items-center gap-2">
                  <HardDrive className="text-muted-foreground size-4 shrink-0" />
                  <code className="truncate font-mono text-sm">
                    {report.location.path}
                  </code>
                </div>
                <p className="text-muted-foreground text-sm">
                  {formatBytes(report.location.bytes)} on disk ·{' '}
                  {report.location.label}
                </p>
              </div>
            </div>
          ) : null}
        </section>

        <section className="space-y-4">
          <h3 className="text-base font-semibold">Disk usage</h3>
          {loading && !report ? (
            <SettingsBlockSkeleton />
          ) : report ? (
            <>
              <div
                className="bg-muted flex h-3 w-full overflow-hidden rounded-full"
                aria-hidden
              >
                {categories.map(category => {
                  const pct =
                    totalBytes > 0 ? (category.bytes / totalBytes) * 100 : 0
                  if (pct <= 0) return null
                  return (
                    <div
                      key={category.id}
                      className="h-full min-w-[2px]"
                      style={{
                        width: `${Math.max(pct, 0.4)}%`,
                        backgroundColor: category.color
                      }}
                      title={`${category.label}: ${formatBytes(category.bytes)}`}
                    />
                  )
                })}
              </div>

              <div className="space-y-1">
                {categories.map(category => (
                  <CategoryRow
                    key={category.id}
                    category={category}
                    expanded={Boolean(expanded[category.id])}
                    onToggle={() =>
                      setExpanded(current => ({
                        ...current,
                        [category.id]: !current[category.id]
                      }))
                    }
                  />
                ))}
              </div>

              <div className="text-muted-foreground flex flex-wrap gap-x-6 gap-y-1 border-t pt-4 text-sm">
                <div>
                  Total:{' '}
                  <span className="text-foreground font-medium">
                    {formatBytes(totalBytes)}
                  </span>
                </div>
                <div>
                  Available on disk:{' '}
                  <span className="text-foreground font-medium">
                    {formatBytes(availableBytes)}
                  </span>
                </div>
              </div>
            </>
          ) : null}
        </section>
      </div>
    </ScrollArea>
  )
}

function CategoryRow({
  category,
  expanded,
  onToggle
}: {
  category: StorageCategory
  expanded: boolean
  onToggle: () => void
}) {
  const isPythonEnv = category.id === 'python_env'
  const children = (category.children || []).filter(child =>
    isPythonEnv ? true : child.bytes > 0
  )
  const hasChildren = children.length > 0

  return (
    <div>
      <button
        type="button"
        className={cn(
          'hover:bg-muted/50 flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm',
          !hasChildren && 'cursor-default'
        )}
        onClick={hasChildren ? onToggle : undefined}
        disabled={!hasChildren}
      >
        <span
          className="size-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: category.color }}
        />
        <span className="min-w-0 flex-1 truncate font-medium">
          {category.label}
        </span>
        {hasChildren ? (
          <ChevronDown
            className={cn(
              'text-muted-foreground size-3.5 shrink-0 transition-transform',
              expanded && 'rotate-180'
            )}
          />
        ) : null}
        <span className="text-muted-foreground shrink-0 tabular-nums">
          {formatBytes(category.bytes)}
        </span>
      </button>
      {isPythonEnv && category.path ? (
        <p className="text-muted-foreground truncate px-2 pb-1 pl-7 font-mono text-[11px]">
          {category.path}
          {hasChildren
            ? ` · ${children.filter(c => !c.id.endsWith(':truncated')).length} packages`
            : ''}
        </p>
      ) : null}
      {hasChildren && expanded ? (
        isPythonEnv ? (
          <ScrollArea className="border-border/60 ml-4 h-72 border-l pl-3">
            <div className="space-y-0.5 pr-3">
              {children.map(child => (
                <div
                  key={child.id}
                  className="text-muted-foreground flex items-center gap-3 px-2 py-1.5 text-sm"
                >
                  <span className="min-w-0 flex-1 truncate font-mono text-xs">
                    {child.label}
                  </span>
                </div>
              ))}
            </div>
          </ScrollArea>
        ) : (
          <div className="border-border/60 ml-4 space-y-0.5 border-l pl-3">
            {children.map(child => (
              <div
                key={child.id}
                className="text-muted-foreground flex items-center gap-3 px-2 py-1.5 text-sm"
              >
                <span className="min-w-0 flex-1 truncate">{child.label}</span>
                <span className="shrink-0 tabular-nums">
                  {formatBytes(child.bytes)}
                </span>
              </div>
            ))}
          </div>
        )
      ) : null}
    </div>
  )
}
