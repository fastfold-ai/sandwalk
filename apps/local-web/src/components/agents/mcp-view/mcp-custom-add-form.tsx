import { ChevronDown, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import { McpCustomAddAdvanced } from './mcp-custom-add-advanced'
import { type CustomMode, type HeaderRow } from './mcp-view-shared'

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
  onSubmitCustomMcp
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
    updater: (rows: HeaderRow[]) => HeaderRow[]
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
              : 'text-muted-foreground hover:text-foreground'
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
              : 'text-muted-foreground hover:text-foreground'
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
                event.target.value as 'sse' | 'streamable_http'
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
              mcpAdvancedOpen && 'rotate-180'
            )}
          />
        </button>
        {mcpAdvancedOpen ? (
          <McpCustomAddAdvanced
            mcpMode={mcpMode}
            mcpOauthClientId={mcpOauthClientId}
            mcpOauthServerUrl={mcpOauthServerUrl}
            mcpOauthScopes={mcpOauthScopes}
            mcpHeadersHelper={mcpHeadersHelper}
            mcpHeaderRows={mcpHeaderRows}
            onMcpOauthClientIdChange={onMcpOauthClientIdChange}
            onMcpOauthServerUrlChange={onMcpOauthServerUrlChange}
            onMcpOauthScopesChange={onMcpOauthScopesChange}
            onMcpHeadersHelperChange={onMcpHeadersHelperChange}
            onMcpHeaderRowsChange={onMcpHeaderRowsChange}
          />
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
