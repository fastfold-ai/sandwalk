import { Loader2, Plug, Search, Unplug } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import { McpDetailToolCard } from './mcp-detail-tool-card'
import type { McpDetailViewState } from './use-mcp-detail-view'

export {
  McpDetailApiKeyBar,
  McpDetailHeaderBar
} from './mcp-detail-header-panels'
export {
  McpDetailInfoAside,
  McpDetailStatsAside
} from './mcp-detail-aside-panels'

export function McpDetailToolsSection({ state }: { state: McpDetailViewState }) {
  const {
    loading,
    tools,
    toolQuery,
    setToolQuery,
    error,
    showCatalogActions,
    connectPending,
    configured,
    primaryConnect,
    onDisconnectCatalog,
    disconnectPending,
    disconnect,
    missingDescriptions,
    filteredTools
  } = state

  return (
    <section className="min-w-0 space-y-4 overflow-x-hidden p-1">
      <div>
        <h2 className="text-base font-semibold">Available tools</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          Tool calls exposed by this MCP, including descriptions and parameter
          schemas when available.
        </p>
      </div>

      {!loading && tools.length > 0 ? (
        <div className="relative">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2" />
          <Input
            value={toolQuery}
            onChange={event => setToolQuery(event.target.value)}
            placeholder="Search tools…"
            className="h-8 pl-8 text-sm"
            aria-label="Search tools"
          />
        </div>
      ) : null}

      {loading ? (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading tools…
        </div>
      ) : null}

      {!loading && error ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-900 dark:text-amber-200">
          <p>{error}</p>
          {showCatalogActions ? (
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                className="h-7 gap-1.5 px-2 text-xs"
                disabled={connectPending}
                onClick={() => primaryConnect()}
              >
                {connectPending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Plug className="size-3.5" />
                )}
                {configured ? 'Reconnect' : 'Connect'}
              </Button>
              {configured && onDisconnectCatalog ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 gap-1.5 px-2 text-xs"
                  disabled={disconnectPending}
                  onClick={() => void disconnect()}
                >
                  {disconnectPending ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Unplug className="size-3.5" />
                  )}
                  Disconnect
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {!loading && !error && missingDescriptions ? (
        <div className="text-muted-foreground rounded-lg border border-border/70 bg-muted/30 px-3 py-2.5 text-sm">
          Tool names loaded, but descriptions were not returned by the agent
          server probe. Click Refresh tools after updating or restarting the
          local agent server.
        </div>
      ) : null}

      {!loading && !error && tools.length === 0 ? (
        <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
          No tools reported by this MCP yet. Connect and enable it, then refresh.
        </p>
      ) : null}

      {!loading && tools.length > 0 && filteredTools.length === 0 ? (
        <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
          No tools match “{toolQuery.trim()}”.
        </p>
      ) : null}

      {!loading && filteredTools.length > 0 ? (
        <div className="space-y-2">
          {filteredTools.map(tool => (
            <McpDetailToolCard key={tool.name} tool={tool} />
          ))}
        </div>
      ) : null}
    </section>
  )
}
