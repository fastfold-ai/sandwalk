import type { McpServer } from '@sandwalk/agent-ui-core'

import { McpCustomAddForm } from './mcp-custom-add-form'
import { McpCustomServerList } from './mcp-custom-server-list'
import {
  type CustomMode,
  type HeaderRow,
} from './mcp-view-shared'

export function McpCustomSection({
  customServers,
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
  focusedMcpKey,
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
  onOpenServer,
  onToggleCustom,
  onDeleteMcp,
}: {
  customServers: McpServer[]
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
  focusedMcpKey: string | null
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
  onOpenServer?: (server: McpServer) => void
  onToggleCustom: (id: string, enabled: boolean) => void
  onDeleteMcp: (id: string) => void
}) {
  return (
    <section className="space-y-2">
      <p className="text-muted-foreground text-xs font-medium">
        Custom ({customServers.length})
      </p>
      <p className="text-muted-foreground text-sm">
        Add a remote HTTP/SSE MCP or a local stdio command. Custom headers and
        a headers helper cover API keys and other auth schemes.
      </p>

      <McpCustomAddForm
        mcpMode={mcpMode}
        mcpName={mcpName}
        mcpTransport={mcpTransport}
        mcpTarget={mcpTarget}
        mcpDescription={mcpDescription}
        mcpAdvancedOpen={mcpAdvancedOpen}
        mcpOauthClientId={mcpOauthClientId}
        mcpOauthServerUrl={mcpOauthServerUrl}
        mcpOauthScopes={mcpOauthScopes}
        mcpHeadersHelper={mcpHeadersHelper}
        mcpHeaderRows={mcpHeaderRows}
        creatingCustom={creatingCustom}
        onMcpModeChange={onMcpModeChange}
        onMcpNameChange={onMcpNameChange}
        onMcpTransportChange={onMcpTransportChange}
        onMcpTargetChange={onMcpTargetChange}
        onMcpDescriptionChange={onMcpDescriptionChange}
        onMcpAdvancedOpenChange={onMcpAdvancedOpenChange}
        onMcpOauthClientIdChange={onMcpOauthClientIdChange}
        onMcpOauthServerUrlChange={onMcpOauthServerUrlChange}
        onMcpOauthScopesChange={onMcpOauthScopesChange}
        onMcpHeadersHelperChange={onMcpHeadersHelperChange}
        onMcpHeaderRowsChange={onMcpHeaderRowsChange}
        onSubmitCustomMcp={onSubmitCustomMcp}
      />

      <McpCustomServerList
        customServers={customServers}
        focusedMcpKey={focusedMcpKey}
        onOpenServer={onOpenServer}
        onToggleCustom={onToggleCustom}
        onDeleteMcp={onDeleteMcp}
      />
    </section>
  )
}
