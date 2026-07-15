import type { McpServer } from '@sandwalk/agent-ui-core'
import { Plug, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { McpToggle } from './mcp-view-shared'

export function McpCustomServerList({
  customServers,
  focusedMcpKey,
  onOpenServer,
  onToggleCustom,
  onDeleteMcp,
}: {
  customServers: McpServer[]
  focusedMcpKey: string | null
  onOpenServer?: (server: McpServer) => void
  onToggleCustom: (id: string, enabled: boolean) => void
  onDeleteMcp: (id: string) => void
}) {
  return (
    <div className="mt-3 space-y-2">
      {customServers.map(server => (
        <div
          id={`mcp-server-${server.id}`}
          key={server.id}
          role={onOpenServer ? 'button' : undefined}
          tabIndex={onOpenServer ? 0 : undefined}
          onClick={() => onOpenServer?.(server)}
          onKeyDown={event => {
            if (!onOpenServer) return
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              onOpenServer(server)
            }
          }}
          className={cn(
            'bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors',
            onOpenServer && 'cursor-pointer',
            focusedMcpKey === `server-${server.id}` &&
              'ring-ring ring-2 ring-offset-2 ring-offset-background',
          )}
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="bg-muted text-muted-foreground grid size-6 shrink-0 place-items-center rounded">
                <Plug className="size-3.5" />
              </span>
              <span className="truncate text-sm font-medium">
                {server.name}
              </span>
              <span className="text-muted-foreground text-xs">
                {server.transport === 'streamable_http'
                  ? 'Streamable HTTP'
                  : server.transport === 'sse'
                    ? 'SSE'
                    : 'stdio'}
              </span>
              {server.headersConfigured ? (
                <span className="text-muted-foreground text-xs">
                  · headers
                </span>
              ) : null}
            </div>
            {server.description ? (
              <p className="text-muted-foreground mt-1 truncate text-xs">
                {server.description}
              </p>
            ) : null}
            <p className="text-muted-foreground mt-1 truncate font-mono text-xs">
              {server.command
                ? `${server.command} ${server.args.join(' ')}`.trim()
                : server.url}
            </p>
          </div>
          <div
            className="flex items-center gap-2"
            onClick={event => event.stopPropagation()}
          >
            <McpToggle
              enabled={server.enabled}
              label={`Enable ${server.name}`}
              onToggle={() => onToggleCustom(server.id, !server.enabled)}
            />
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              onClick={() => onDeleteMcp(server.id)}
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        </div>
      ))}
      {customServers.length === 0 ? (
        <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
          No custom MCP servers yet.
        </p>
      ) : null}
    </div>
  )
}
