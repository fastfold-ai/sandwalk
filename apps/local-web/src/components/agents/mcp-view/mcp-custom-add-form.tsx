import { ChevronDown, Loader2, Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import {
  type CustomMode,
  type HeaderRow,
  newHeaderRow,
} from './mcp-view-shared'

export function McpCustomAddForm({
  mcpMode,
  mcpName,
  mcpTransport,
  mcpTarget,
  mcpDescription,
  mcpAdvancedOpen,
  mcpOauthClientId,
  mcpOauthServerUrl,
  mcpOauthScopes,
  mcpHeadersHelper,
  mcpHeaderRows,
  creatingCustom,
  onMcpModeChange,
  onMcpNameChange,
  onMcpTransportChange,
  onMcpTargetChange,
  onMcpDescriptionChange,
  onMcpAdvancedOpenChange,
  onMcpOauthClientIdChange,
  onMcpOauthServerUrlChange,
  onMcpOauthScopesChange,
  onMcpHeadersHelperChange,
  onMcpHeaderRowsChange,
  onSubmitCustomMcp,
}: {
  mcpMode: CustomMode
  mcpName: string
  mcpTransport: 'sse' | 'streamable_http'
  mcpTarget: string
  mcpDescription: string
  mcpAdvancedOpen: boolean
  mcpOauthClientId: string
  mcpOauthServerUrl: string
  mcpOauthScopes: string
  mcpHeadersHelper: string
  mcpHeaderRows: HeaderRow[]
  creatingCustom: boolean
  onMcpModeChange: (mode: CustomMode) => void
  onMcpNameChange: (value: string) => void
  onMcpTransportChange: (value: 'sse' | 'streamable_http') => void
  onMcpTargetChange: (value: string) => void
  onMcpDescriptionChange: (value: string) => void
  onMcpAdvancedOpenChange: (open: boolean) => void
  onMcpOauthClientIdChange: (value: string) => void
  onMcpOauthServerUrlChange: (value: string) => void
  onMcpOauthScopesChange: (value: string) => void
  onMcpHeadersHelperChange: (value: string) => void
  onMcpHeaderRowsChange: (
    updater: (rows: HeaderRow[]) => HeaderRow[],
  ) => void
  onSubmitCustomMcp: () => void
}) {
  return (
    <div className="bg-background/60 space-y-3 rounded-lg border p-4">
      <div className="inline-flex rounded-md border p-0.5">
        <button
          type="button"
          className={cn(
            'rounded px-3 py-1.5 text-sm transition-colors',
            mcpMode === 'remote'
              ? 'bg-muted font-medium'
              : 'text-muted-foreground hover:text-foreground',
          )}
          onClick={() => onMcpModeChange('remote')}
        >
          Remote
        </button>
        <button
          type="button"
          className={cn(
            'rounded px-3 py-1.5 text-sm transition-colors',
            mcpMode === 'local'
              ? 'bg-muted font-medium'
              : 'text-muted-foreground hover:text-foreground',
          )}
          onClick={() => onMcpModeChange('local')}
        >
          Local command
        </button>
      </div>

      <div className="space-y-2">
        <label className="text-muted-foreground text-xs font-medium">
          Name
        </label>
        <Input
          value={mcpName}
          onChange={event => onMcpNameChange(event.target.value)}
          placeholder="My MCP server"
        />
      </div>

      <div className="space-y-2">
        <label className="text-muted-foreground text-xs font-medium">
          {mcpMode === 'local' ? 'Command' : 'Remote MCP server URL'}
        </label>
        <Input
          value={mcpTarget}
          onChange={event => onMcpTargetChange(event.target.value)}
          placeholder={
            mcpMode === 'local'
              ? 'npx -y @example/mcp-server'
              : 'https://mcp.example.com/mcp'
          }
          className="font-mono text-sm"
        />
      </div>

      {mcpMode === 'remote' ? (
        <div className="space-y-2">
          <label className="text-muted-foreground text-xs font-medium">
            Transport
          </label>
          <select
            value={mcpTransport}
            onChange={event =>
              onMcpTransportChange(
                event.target.value as 'sse' | 'streamable_http',
              )
            }
            className="bg-background h-9 w-full rounded-md border px-3 text-sm"
          >
            <option value="streamable_http">Streamable HTTP</option>
            <option value="sse">SSE (legacy)</option>
          </select>
        </div>
      ) : null}

      <div className="space-y-2">
        <label className="text-muted-foreground text-xs font-medium">
          Description (optional)
        </label>
        <Input
          value={mcpDescription}
          onChange={event => onMcpDescriptionChange(event.target.value)}
          placeholder="What this server is for"
        />
      </div>

      <div className="rounded-md border">
        <button
          type="button"
          className="hover:bg-muted/40 flex w-full items-center justify-between px-3 py-2 text-left text-sm"
          onClick={() => onMcpAdvancedOpenChange(!mcpAdvancedOpen)}
        >
          <span className="font-medium">Advanced settings</span>
          <ChevronDown
            className={cn(
              'text-muted-foreground size-4 transition-transform',
              mcpAdvancedOpen && 'rotate-180',
            )}
          />
        </button>
        {mcpAdvancedOpen ? (
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
                                : item,
                            ),
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
                                : item,
                            ),
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
                              : rows.filter(item => item.id !== row.id),
                          )
                        }
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
                <p className="text-muted-foreground text-xs">
                  Example: Authorization / Bearer sk-… or X-API-Key /
                  your-key. Values are stored as secrets.
                </p>
              </div>
            ) : null}

            <div className="space-y-2">
              <label className="text-muted-foreground text-xs font-medium">
                OAuth Client ID (optional)
              </label>
              <Input
                value={mcpOauthClientId}
                onChange={event =>
                  onMcpOauthClientIdChange(event.target.value)
                }
                placeholder="Stored for future OAuth connect"
              />
            </div>
            <div className="space-y-2">
              <label className="text-muted-foreground text-xs font-medium">
                OAuth Server URL (optional)
              </label>
              <Input
                value={mcpOauthServerUrl}
                onChange={event =>
                  onMcpOauthServerUrlChange(event.target.value)
                }
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
                  onChange={event =>
                    onMcpHeadersHelperChange(event.target.value)
                  }
                  placeholder={`echo '{"Authorization":"Bearer …"}'`}
                  className="font-mono text-sm"
                />
                <p className="text-muted-foreground text-xs">
                  Shell command that prints a JSON object of headers on
                  stdout. When set and successful, it replaces static
                  headers.
                </p>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="flex justify-end">
        <Button
          disabled={creatingCustom || !mcpName.trim() || !mcpTarget.trim()}
          onClick={onSubmitCustomMcp}
        >
          {creatingCustom ? <Loader2 className="size-4 animate-spin" /> : null}
          Add server
        </Button>
      </div>
    </div>
  )
}
