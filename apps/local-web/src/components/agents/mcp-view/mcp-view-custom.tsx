import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpServer
} from '@sandwalk/agent-ui-core'
import { useState } from 'react'

import { Button } from '@/components/ui/button'

import { McpCustomAddForm } from './mcp-custom-add-form'
import { McpCustomServerList } from './mcp-custom-server-list'
import { McpSuggestedStrip } from './mcp-suggested-strip'
import { type CustomMode, type HeaderRow } from './mcp-view-shared'

export function McpCustomSection({
  installedServers,
  suggestedCatalog,
  catalogById,
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
  onOpenCatalog,
  onToggleCustom,
  onToggleCatalog,
  onDeleteMcp,
  onConnectCustom,
  onConnectCatalog,
  onRefresh,
  onInstallCatalog,
  onRevealStoredSecret,
  onResetFeaturedDefaults
}: {
  installedServers: McpServer[]
  suggestedCatalog: McpCatalogEntry[]
  catalogById: Map<string, McpCatalogEntry>
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
  onOpenCatalog?: (entry: McpCatalogEntry) => void
  onToggleCustom: (id: string, enabled: boolean) => void
  onToggleCatalog: (entry: McpCatalogEntry, enabled: boolean) => void
  onDeleteMcp: (id: string) => void
  onConnectCustom?: (
    server: McpServer,
    input: { method: 'oauth' | 'api_key'; apiKey?: string }
  ) => Promise<ConnectMcpResult>
  onConnectCatalog: (
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string }
  ) => Promise<ConnectMcpResult>
  onRefresh?: () => Promise<void>
  onInstallCatalog?: (catalogId: string) => void | Promise<void>
  onRevealStoredSecret?: (integrationKey: string) => Promise<string>
  onResetFeaturedDefaults?: () => void | Promise<void>
}) {
  const [showAddForm, setShowAddForm] = useState(false)

  return (
    <section className="space-y-3">
      <McpCustomServerList
        installedServers={installedServers}
        catalogById={catalogById}
        focusedMcpKey={focusedMcpKey}
        onOpenServer={onOpenServer}
        onOpenCatalog={onOpenCatalog}
        onToggleCustom={onToggleCustom}
        onToggleCatalog={onToggleCatalog}
        onDeleteMcp={onDeleteMcp}
        onConnectCustom={onConnectCustom}
        onConnectCatalog={onConnectCatalog}
        onRefresh={onRefresh}
        onRevealStoredSecret={onRevealStoredSecret}
        onAddNew={() => setShowAddForm(true)}
      />

      {onInstallCatalog && suggestedCatalog.length > 0 ? (
        <McpSuggestedStrip
          suggested={suggestedCatalog}
          onInstall={onInstallCatalog}
          onResetDefaults={onResetFeaturedDefaults}
          onOpenCatalog={onOpenCatalog}
        />
      ) : null}

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
    </section>
  )
}
