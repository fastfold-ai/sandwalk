import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpJsonDocument,
  McpServer
} from '@sandwalk/agent-ui-core'
import { Code2 } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

import { McpJsonEditorDialog } from './mcp-view/mcp-json-editor-dialog'
import { McpFeaturedSection } from './mcp-view/mcp-view-catalog'
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
  onInstallCatalog,
  onLoadMcpJson,
  onSaveMcpJson,
  embedded = false
}: {
  mcpServers: McpServer[]
  catalog: McpCatalogEntry[]
  catalogLoading?: boolean
  /** Overview / onboarding: only the Featured catalog grid. */
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
  /** Re-add a removed catalog template (Suggested strip). */
  onInstallCatalog?: (catalogId: string) => Promise<void>
  onLoadMcpJson?: () => Promise<{ path: string; document: McpJsonDocument }>
  onSaveMcpJson?: (document: McpJsonDocument) => Promise<void>
  embedded?: boolean
}) {
  const [jsonOpen, setJsonOpen] = useState(false)
  const canEditJson = Boolean(onLoadMcpJson && onSaveMcpJson)

  const view = useMcpView({
    mcpServers,
    catalog,
    featuredOnly,
    featuredLimit,
    onRefresh,
    onConnectCatalog,
    onToggleCatalog,
    onCreateMcp
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
            : 'mx-auto w-full max-w-7xl space-y-6 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8'
        }
      >
        {!embedded ? (
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-2xl font-semibold">MCP servers</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Manage installed servers in{' '}
                <span className="font-mono text-xs">~/.sandwalk/mcp.json</span>.
                Catalog templates seed here by default; connect credentials under
                Integrations / keys.
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
        ) : canEditJson ? (
          <div className="flex justify-end">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setJsonOpen(true)}
            >
              <Code2 className="size-3.5" />
              Edit mcp.json
            </Button>
          </div>
        ) : null}

        <div className="space-y-6 pb-4">
          <McpCustomSection
            installedServers={view.installedServers}
            suggestedCatalog={view.suggestedCatalog}
            catalogById={view.catalogById}
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
            onOpenCatalog={onOpenCatalog}
            onToggleCustom={(id, enabled) => void onToggleCustom(id, enabled)}
            onToggleCatalog={(entry, enabled) =>
              void onToggleCatalog(entry, enabled)
            }
            onDeleteMcp={id => void onDeleteMcp(id)}
            onConnectCustom={onConnectCustom}
            onConnectCatalog={onConnectCatalog}
            onInstallCatalog={onInstallCatalog}
          />
        </div>
      </div>

      {canEditJson ? (
        <McpJsonEditorDialog
          open={jsonOpen}
          onOpenChange={setJsonOpen}
          onLoad={onLoadMcpJson!}
          onSave={onSaveMcpJson!}
        />
      ) : null}
    </ScrollArea>
  )
}
