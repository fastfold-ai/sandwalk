import type { McpCatalogEntry, McpServer } from '@sandwalk/agent-ui-core'
import { ChevronDown, Plug, Search, X } from 'lucide-react'

import {
  McpGlyph,
  mcpMetaText
} from '@/components/agents/specialists-view/specialists-view-shared'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

type SelectedMcpRow = {
  key: string
  kind: 'server' | 'catalog'
  name: string
  server: McpServer | null
  catalog: McpCatalogEntry | null
  status: 'ok' | 'missing' | 'disabled' | 'disconnected'
  statusLabel: string | null
}

export function SpecialistsEditorMcpsSection({
  mcpCount,
  onManageMcps,
  mcpAddOpen,
  onMcpAddOpenChange,
  mcpAddQuery,
  onMcpAddQueryChange,
  availableMcps,
  onAddMcp,
  selectedMcpRows,
  onOpenMcp,
  onRemoveMcp,
  onRemoveMcpCatalog
}: {
  mcpCount: number
  onManageMcps?: () => void
  mcpAddOpen: boolean
  onMcpAddOpenChange: (open: boolean) => void
  mcpAddQuery: string
  onMcpAddQueryChange: (query: string) => void
  availableMcps: McpServer[]
  onAddMcp: (id: string) => void
  selectedMcpRows: SelectedMcpRow[]
  onOpenMcp?: (target: { kind: 'server' | 'catalog'; id: string }) => void
  onRemoveMcp: (id: string) => void
  onRemoveMcpCatalog: (catalogId: string) => void
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-baseline gap-2">
          <h2 className="text-sm font-medium">MCPs ({mcpCount})</h2>
          {onManageMcps ? (
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground text-xs transition-colors"
              onClick={onManageMcps}
            >
              Manage all MCPs
            </button>
          ) : null}
        </div>
        <DropdownMenu
          open={mcpAddOpen}
          onOpenChange={open => {
            onMcpAddOpenChange(open)
            if (!open) onMcpAddQueryChange('')
          }}
        >
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="bg-muted/40 hover:bg-muted/60 text-muted-foreground inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-xs transition-colors"
            >
              Add an MCP…
              <ChevronDown className="size-3.5" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="w-80 p-0"
            onCloseAutoFocus={event => event.preventDefault()}
          >
            <div className="border-b px-2 py-2">
              <div className="relative">
                <Search className="text-muted-foreground/70 pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2" />
                <Input
                  value={mcpAddQuery}
                  onChange={event => onMcpAddQueryChange(event.target.value)}
                  placeholder="Search"
                  className="h-8 border-0 bg-transparent pl-7 shadow-none focus-visible:ring-0"
                  autoFocus
                />
              </div>
            </div>
            <div className="chat-scrollbar max-h-56 overflow-y-auto py-1">
              {availableMcps.length === 0 ? (
                <p className="text-muted-foreground px-3 py-3 text-xs">
                  Nothing to add.
                </p>
              ) : (
                availableMcps.map(server => {
                  const meta = mcpMetaText(server)
                  return (
                    <DropdownMenuItem
                      key={server.id}
                      className="gap-2 py-2"
                      onClick={() => onAddMcp(server.id)}
                    >
                      <McpGlyph server={server} className="size-[18px]" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm">
                          {server.name}
                        </span>
                        {server.description ? (
                          <span className="text-muted-foreground block truncate text-xs">
                            {server.description}
                          </span>
                        ) : null}
                        {meta ? (
                          <span className="text-muted-foreground/70 block truncate text-[10px]">
                            {meta}
                          </span>
                        ) : null}
                      </span>
                    </DropdownMenuItem>
                  )
                })
              )}
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {selectedMcpRows.length === 0 ? (
        <p className="text-muted-foreground py-2 text-sm">No MCPs selected.</p>
      ) : (
        <div className="divide-border/40 divide-y">
          {selectedMcpRows.map(row => {
            const meta = row.server ? mcpMetaText(row.server) : null
            const catalogMeta =
              row.kind === 'catalog'
                ? row.catalog?.id || row.key.replace(/^catalog:/, '')
                : null
            const openTarget =
              row.kind === 'catalog'
                ? {
                    kind: 'catalog' as const,
                    id: row.key.replace(/^catalog:/, '')
                  }
                : {
                    kind: 'server' as const,
                    id: row.server?.id || row.key.replace(/^server:/, '')
                  }
            return (
              <div key={row.key} className="flex items-center gap-3 py-2.5">
                <button
                  type="button"
                  className={cn(
                    'flex min-w-0 flex-1 items-center gap-3 text-left',
                    onOpenMcp &&
                      'hover:opacity-90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded-md'
                  )}
                  disabled={!onOpenMcp || !openTarget.id}
                  onClick={() => {
                    if (!openTarget.id) return
                    onOpenMcp?.(openTarget)
                  }}
                >
                  {row.server ? (
                    <McpGlyph server={row.server} />
                  ) : (
                    <span className="bg-muted flex size-7 shrink-0 items-center justify-center rounded-md">
                      <Plug className="text-muted-foreground size-3.5" />
                    </span>
                  )}
                  <span className="min-w-0 flex-1">
                    <span
                      className={cn(
                        'block truncate text-sm',
                        onOpenMcp && 'hover:underline'
                      )}
                    >
                      {row.name}
                    </span>
                    <span className="text-muted-foreground block truncate text-xs">
                      {[meta || catalogMeta, row.statusLabel]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </span>
                </button>
                {row.status !== 'ok' ? (
                  <span className="text-amber-500/90 shrink-0 text-[11px] font-medium">
                    {row.statusLabel}
                  </span>
                ) : null}
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground rounded-md p-1 transition-colors"
                  aria-label={`Remove ${row.name}`}
                  onClick={() => {
                    if (row.kind === 'catalog') {
                      onRemoveMcpCatalog(row.key.replace(/^catalog:/, ''))
                    } else if (row.server) {
                      onRemoveMcp(row.server.id)
                    } else {
                      onRemoveMcp(row.key.replace(/^server:/, ''))
                    }
                  }}
                >
                  <X className="size-3.5" />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
