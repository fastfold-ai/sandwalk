import { cn } from '@/lib/utils'

import { McpIcon } from './mcp-view-shared'
import type { McpDetailViewState } from './use-mcp-detail-view'

export function McpDetailInfoAside({ state }: { state: McpDetailViewState }) {
  const {
    kind,
    catalogEntry,
    title,
    description,
    enabled,
    togglePending,
    toggleEnabled,
    transport
  } = state

  return (
    <aside className="space-y-3 lg:sticky lg:top-4 lg:border-r lg:border-border/60 lg:pr-4">
      <div className="space-y-2">
        <McpIcon
          id={kind === 'catalog' ? catalogEntry?.id || '' : ''}
          name={title}
          url={
            kind === 'catalog'
              ? catalogEntry?.url
              : typeof state.endpoint === 'string' &&
                  state.endpoint.includes('://')
                ? state.endpoint
                : null
          }
          size="lg"
        />
        <div className="min-w-0 space-y-0.5">
          <div className="flex items-start justify-between gap-2">
            <h1 className="break-all text-lg font-semibold">{title}</h1>
            {state.hasToggle ? (
              <button
                type="button"
                role="switch"
                aria-checked={enabled}
                aria-label={enabled ? `Disable ${title}` : `Enable ${title}`}
                disabled={togglePending}
                className={cn(
                  'relative mt-1 inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
                  enabled
                    ? 'bg-black/75 dark:bg-zinc-300/50'
                    : 'bg-zinc-200 dark:bg-zinc-700',
                  togglePending && 'cursor-not-allowed opacity-60'
                )}
                onClick={toggleEnabled}
              >
                <span
                  className={cn(
                    'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
                    enabled ? 'translate-x-4' : 'translate-x-0.5'
                  )}
                />
              </button>
            ) : null}
          </div>
          <p className="text-muted-foreground mb-6 pb-3 text-sm leading-relaxed">
            {description || 'MCP server'}
          </p>
          <div className="mt-6 space-y-1 border-t border-border/60 pt-5 text-xs">
            <div className="text-muted-foreground flex items-center gap-1.5">
              <span className="text-foreground/90 font-medium">Type:</span>
              <span className="truncate">
                {kind === 'catalog' ? 'Featured' : 'Custom'}
              </span>
            </div>
            {transport ? (
              <div className="text-muted-foreground flex items-center gap-1.5">
                <span className="text-foreground/90 font-medium">Transport:</span>
                <span className="truncate">{transport}</span>
              </div>
            ) : null}
            {kind === 'catalog' && catalogEntry?.authMethod ? (
              <div className="text-muted-foreground flex items-center gap-1.5">
                <span className="text-foreground/90 font-medium">Auth:</span>
                <span className="truncate">
                  {catalogEntry.authMethod === 'oauth'
                    ? 'OAuth'
                    : catalogEntry.authMethod === 'local'
                      ? 'Local token'
                      : 'API key'}
                </span>
              </div>
            ) : null}
            {kind === 'catalog' && catalogEntry?.setupUrl ? (
              <div className="text-muted-foreground flex items-start gap-1.5">
                <span className="text-foreground/90 shrink-0 font-medium">
                  Plugin:
                </span>
                <span className="break-all">{catalogEntry.setupUrl}</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </aside>
  )
}

export function McpDetailStatsAside({ state }: { state: McpDetailViewState }) {
  const {
    result,
    catalogEntry,
    tools,
    statusLabel,
    statusHealthy,
    statusWarn,
    connected,
    endpoint
  } = state

  return (
    <aside className="space-y-5 lg:sticky lg:top-4">
      <div>
        <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
          Tools
        </p>
        <p className="mt-1 text-3xl font-semibold tabular-nums">
          {result?.toolCount ?? catalogEntry?.toolCount ?? tools.length ?? 0}
        </p>
      </div>
      <div>
        <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
          Status
        </p>
        <p className="mt-1 inline-flex items-center gap-1.5 text-sm">
          <span
            className={cn(
              'size-1.5 rounded-full',
              statusHealthy
                ? 'bg-emerald-500'
                : statusWarn
                  ? 'bg-amber-500'
                  : connected
                    ? 'bg-emerald-500'
                    : 'bg-muted-foreground/50'
            )}
          />
          {statusLabel}
        </p>
      </div>
      {endpoint ? (
        <div>
          <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
            Endpoint
          </p>
          <p className="text-muted-foreground mt-1 break-all font-mono text-xs leading-relaxed">
            {endpoint}
          </p>
        </div>
      ) : null}
      {result?.message ? (
        <div>
          <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
            Last probe
          </p>
          <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
            {result.message}
          </p>
        </div>
      ) : null}
    </aside>
  )
}
