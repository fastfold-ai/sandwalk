import { Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import { type CustomMode, type HeaderRow, newHeaderRow } from './mcp-view-shared'

export function McpCustomAddAdvanced({
  mcpMode,
  mcpOauthClientId,
  mcpOauthServerUrl,
  mcpOauthScopes,
  mcpHeadersHelper,
  mcpHeaderRows,
  onMcpOauthClientIdChange,
  onMcpOauthServerUrlChange,
  onMcpOauthScopesChange,
  onMcpHeadersHelperChange,
  onMcpHeaderRowsChange
}: {
  mcpMode: CustomMode
  mcpOauthClientId: string
  mcpOauthServerUrl: string
  mcpOauthScopes: string
  mcpHeadersHelper: string
  mcpHeaderRows: HeaderRow[]
  onMcpOauthClientIdChange: (value: string) => void
  onMcpOauthServerUrlChange: (value: string) => void
  onMcpOauthScopesChange: (value: string) => void
  onMcpHeadersHelperChange: (value: string) => void
  onMcpHeaderRowsChange: (
    updater: (rows: HeaderRow[]) => HeaderRow[]
  ) => void
}) {
  return (
    <div className="space-y-3 border-t px-3 py-3">
      {mcpMode === 'remote' ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <label className="text-muted-foreground text-xs font-medium">
              Custom headers
            </label>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 gap-1 px-2 text-xs"
              onClick={() =>
                onMcpHeaderRowsChange(rows => [...rows, newHeaderRow()])
              }
            >
              <Plus className="size-3.5" />
              Add header
            </Button>
          </div>
          <div className="space-y-2">
            {mcpHeaderRows.map(row => (
              <div
                key={row.id}
                className="grid grid-cols-[1fr_1fr_auto] gap-2"
              >
                <Input
                  value={row.name}
                  onChange={event =>
                    onMcpHeaderRowsChange(rows =>
                      rows.map(item =>
                        item.id === row.id
                          ? { ...item, name: event.target.value }
                          : item
                      )
                    )
                  }
                  placeholder="Header name"
                  className="font-mono text-sm"
                />
                <Input
                  type="password"
                  value={row.value}
                  onChange={event =>
                    onMcpHeaderRowsChange(rows =>
                      rows.map(item =>
                        item.id === row.id
                          ? { ...item, value: event.target.value }
                          : item
                      )
                    )
                  }
                  placeholder="Value"
                  className="font-mono text-sm"
                  autoComplete="off"
                />
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="size-9"
                  disabled={mcpHeaderRows.length <= 1}
                  onClick={() =>
                    onMcpHeaderRowsChange(rows =>
                      rows.length <= 1
                        ? rows
                        : rows.filter(item => item.id !== row.id)
                    )
                  }
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            ))}
          </div>
          <p className="text-muted-foreground text-xs">
            Example: Authorization / Bearer sk-… or X-API-Key / your-key.
            Values are stored as secrets.
          </p>
        </div>
      ) : null}

      <div className="space-y-2">
        <label className="text-muted-foreground text-xs font-medium">
          OAuth Client ID (optional)
        </label>
        <Input
          value={mcpOauthClientId}
          onChange={event => onMcpOauthClientIdChange(event.target.value)}
          placeholder="Stored for future OAuth connect"
        />
      </div>
      <div className="space-y-2">
        <label className="text-muted-foreground text-xs font-medium">
          OAuth Server URL (optional)
        </label>
        <Input
          value={mcpOauthServerUrl}
          onChange={event => onMcpOauthServerUrlChange(event.target.value)}
          placeholder="https://auth.example.com"
          className="font-mono text-sm"
        />
      </div>
      <div className="space-y-2">
        <label className="text-muted-foreground text-xs font-medium">
          Scopes (optional)
        </label>
        <Input
          value={mcpOauthScopes}
          onChange={event => onMcpOauthScopesChange(event.target.value)}
          placeholder="openid profile"
        />
      </div>
      {mcpMode === 'remote' ? (
        <div className="space-y-2">
          <label className="text-muted-foreground text-xs font-medium">
            Headers helper command (optional)
          </label>
          <Input
            value={mcpHeadersHelper}
            onChange={event => onMcpHeadersHelperChange(event.target.value)}
            placeholder={`echo '{"Authorization":"Bearer …"}'`}
            className="font-mono text-sm"
          />
          <p className="text-muted-foreground text-xs">
            Shell command that prints a JSON object of headers on stdout. When
            set and successful, it replaces static headers.
          </p>
        </div>
      ) : null}
    </div>
  )
}
