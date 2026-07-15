import type {
  ConnectMcpResult,
  McpJsonDocument,
  McpServer
} from '@sandwalk/agent-ui-core'
import { Code2 } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'

import { McpCustomAddForm } from './mcp-custom-add-form'
import { McpCustomServerList } from './mcp-custom-server-list'
import { McpJsonEditorDialog } from './mcp-json-editor-dialog'
import { type CustomMode, type HeaderRow } from './mcp-view-shared'

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
  onConnectCustom,
  onLoadMcpJson,
  onSaveMcpJson
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
  onMcpHeaderRowsChange: (updater: (rows: HeaderRow[]) => HeaderRow[]) => void
  onSubmitCustomMcp: () => void
  onOpenServer?: (server: McpServer) => void
  onToggleCustom: (id: string, enabled: boolean) => void
  onDeleteMcp: (id: string) => void
  onConnectCustom?: (
    server: McpServer,
    input: { method: 'oauth' | 'api_key'; apiKey?: string }
  ) => Promise<ConnectMcpResult>
  onLoadMcpJson?: () => Promise<{ path: string; document: McpJsonDocument }>
  onSaveMcpJson?: (document: McpJsonDocument) => Promise<void>
}) {
  const [jsonOpen, setJsonOpen] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const canEditJson = Boolean(onLoadMcpJson && onSaveMcpJson)

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-foreground text-sm font-semibold">
            Installed MCP servers
          </p>
          <p className="text-muted-foreground mt-0.5 text-sm">
            Custom servers from{' '}
            <span className="font-mono text-xs">~/.sandwalk/mcp.json</span>.
            Catalog MCPs stay above.
          </p>
        </div>
        {canEditJson ? (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setJsonOpen(true)}
          >
            <Code2 className="size-3.5" />
            Edit mcp.json
          </Button>
        ) : null}
      </div>

      <McpCustomServerList
        customServers={customServers}
        focusedMcpKey={focusedMcpKey}
        onOpenServer={onOpenServer}
        onToggleCustom={onToggleCustom}
        onDeleteMcp={onDeleteMcp}
        onConnect={onConnectCustom}
        onAddNew={() => setShowAddForm(true)}
      />

      {showAddForm ? (
        <div className="bg-card space-y-3 rounded-xl border p-4">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold">Add custom MCP</p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowAddForm(false)}
            >
              Close
            </Button>
          </div>
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
            onSubmitCustomMcp={() => {
              onSubmitCustomMcp()
              setShowAddForm(false)
            }}
          />
        </div>
      ) : null}

      {canEditJson ? (
        <McpJsonEditorDialog
          open={jsonOpen}
          onOpenChange={setJsonOpen}
          onLoad={onLoadMcpJson!}
          onSave={onSaveMcpJson!}
        />
      ) : null}
    </section>
  )
}
