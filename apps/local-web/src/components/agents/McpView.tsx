import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpJsonDocument,
  McpServer
} from '@sandwalk/agent-ui-core'

import { ScrollArea } from '@/components/ui/scroll-area'

import {
  McpFeaturedSection,
  McpMoreCatalogSection
} from './mcp-view/mcp-view-catalog'
import { McpCustomSection } from './mcp-view/mcp-view-custom'
import { useMcpView } from './mcp-view/use-mcp-view'

export function McpView({
  mcpServers,
  catalog,
  catalogLoading,
  featuredOnly = false,
  featuredLimit,
  featuredLabel = 'MCPs',
  onShowAll,
  onRefresh,
  onConnectCatalog,
  onToggleCatalog,
  onCreateMcp,
  onDeleteMcp,
  onToggleCustom,
  onOpenCatalog,
  onOpenServer,
  onConnectCustom,
  onLoadMcpJson,
  onSaveMcpJson,
  embedded = false
}: {
  mcpServers: McpServer[]
  catalog: McpCatalogEntry[]
  catalogLoading?: boolean
  /** Overview: only the Featured catalog grid (same cards as MCP page). */
  featuredOnly?: boolean
  /** When featuredOnly, how many cards to show. Omit for 2; null = all. */
  featuredLimit?: number | null
  /** Section title when featuredOnly (default MCPs). */
  featuredLabel?: string
  onShowAll?: () => void
  onRefresh: () => Promise<void>
  onConnectCatalog: (
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string }
  ) => Promise<ConnectMcpResult>
  onToggleCatalog: (entry: McpCatalogEntry, enabled: boolean) => Promise<void>
  onCreateMcp: (
    input: Omit<McpServer, 'id' | 'createdAt' | 'updatedAt'>
  ) => Promise<void>
  onDeleteMcp: (id: string) => Promise<void>
  onToggleCustom: (id: string, enabled: boolean) => Promise<void>
  onOpenCatalog?: (entry: McpCatalogEntry) => void
  onOpenServer?: (server: McpServer) => void
  onConnectCustom?: (
    server: McpServer,
    input: { method: 'oauth' | 'api_key'; apiKey?: string }
  ) => Promise<ConnectMcpResult>
  onLoadMcpJson?: () => Promise<{ path: string; document: McpJsonDocument }>
  onSaveMcpJson?: (document: McpJsonDocument) => Promise<void>
  embedded?: boolean
}) {
  const view = useMcpView({
    mcpServers,
    catalog,
    featuredOnly,
    featuredLimit,
    onRefresh,
    onConnectCatalog,
    onToggleCatalog,
    onCreateMcp,
  })

  const featuredSection = (
    <McpFeaturedSection
      featuredOnly={featuredOnly}
      featuredLabel={featuredLabel}
      featuredCatalog={view.featuredCatalog}
      featuredVisible={view.featuredVisible}
      catalogLoading={catalogLoading}
      featuredLimit={featuredLimit}
      onShowAll={onShowAll}
      onOpenCatalog={onOpenCatalog}
      {...view.catalogCardProps}
    />
  )

  if (featuredOnly) {
    return featuredSection
  }

  return (
    <ScrollArea className={embedded ? 'h-[min(22rem,45vh)]' : 'flex-1'}>
      <div
        className={
          embedded
            ? 'mx-auto w-full max-w-5xl space-y-6 p-1'
            : 'mx-auto w-full max-w-7xl space-y-6 p-4 md:p-6'
        }
      >
        {!embedded ? (
          <div>
            <h2 className="text-2xl font-semibold">MCP servers</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Connect featured cloud MCPs (off by default). Credentials save under
              Integrations / keys. Add custom stdio, SSE, or HTTP servers below.
            </p>
          </div>
        ) : null}

        <div className="space-y-6 pb-4">
          {featuredSection}

          <McpMoreCatalogSection
            moreCatalog={view.moreCatalog}
            onOpenCatalog={onOpenCatalog}
            {...view.catalogCardProps}
          />

          <McpCustomSection
            customServers={view.customServers}
            mcpMode={view.mcpMode}
            mcpName={view.mcpName}
            mcpTransport={view.mcpTransport}
            mcpTarget={view.mcpTarget}
            mcpDescription={view.mcpDescription}
            mcpAdvancedOpen={view.mcpAdvancedOpen}
            mcpOauthClientId={view.mcpOauthClientId}
            mcpOauthServerUrl={view.mcpOauthServerUrl}
            mcpOauthScopes={view.mcpOauthScopes}
            mcpHeadersHelper={view.mcpHeadersHelper}
            mcpHeaderRows={view.mcpHeaderRows}
            creatingCustom={view.creatingCustom}
            focusedMcpKey={view.focusedMcpKey}
            onMcpModeChange={view.setMcpMode}
            onMcpNameChange={view.setMcpName}
            onMcpTransportChange={view.setMcpTransport}
            onMcpTargetChange={view.setMcpTarget}
            onMcpDescriptionChange={view.setMcpDescription}
            onMcpAdvancedOpenChange={view.setMcpAdvancedOpen}
            onMcpOauthClientIdChange={view.setMcpOauthClientId}
            onMcpOauthServerUrlChange={view.setMcpOauthServerUrl}
            onMcpOauthScopesChange={view.setMcpOauthScopes}
            onMcpHeadersHelperChange={view.setMcpHeadersHelper}
            onMcpHeaderRowsChange={updater => view.setMcpHeaderRows(updater)}
            onSubmitCustomMcp={() => void view.submitCustomMcp()}
            onOpenServer={onOpenServer}
            onToggleCustom={(id, enabled) => void onToggleCustom(id, enabled)}
            onDeleteMcp={id => void onDeleteMcp(id)}
            onConnectCustom={onConnectCustom}
            onLoadMcpJson={onLoadMcpJson}
            onSaveMcpJson={onSaveMcpJson}
          />
        </div>
      </div>
    </ScrollArea>
  )
}
