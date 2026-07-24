import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpServer,
  ValidateMcpResult
} from '@sandwalk/agent-ui-core'

import { ScrollArea } from '@/components/ui/scroll-area'

import {
  McpDetailApiKeyBar,
  McpDetailHeaderBar,
  McpDetailInfoAside,
  McpDetailStatsAside,
  McpDetailToolsSection
} from './mcp-detail-panels'
import { useMcpDetailView } from './use-mcp-detail-view'

export function McpDetailView({
  kind,
  catalogEntry,
  server,
  onBack,
  onLoadTools,
  onToggleEnabled,
  onConnectCatalog,
  onDisconnectCatalog,
  onRefreshMeta
}: {
  kind: 'catalog' | 'server'
  catalogEntry?: McpCatalogEntry | null
  server?: McpServer | null
  onBack: () => void
  onLoadTools: () => Promise<ValidateMcpResult>
  onToggleEnabled?: (enabled: boolean) => Promise<void>
  onConnectCatalog?: (input: {
    method: 'oauth' | 'api_key'
    apiKey?: string
  }) => Promise<ConnectMcpResult>
  onDisconnectCatalog?: () => Promise<ConnectMcpResult | void>
  onRefreshMeta?: () => Promise<void>
}) {
  const state = useMcpDetailView({
    kind,
    catalogEntry,
    server,
    onLoadTools,
    onToggleEnabled,
    onConnectCatalog,
    onDisconnectCatalog,
    onRefreshMeta
  })

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <McpDetailHeaderBar state={state} onBack={onBack} />
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 md:p-6">
          <McpDetailApiKeyBar state={state} />
          <div className="grid items-start gap-4 lg:grid-cols-[240px_minmax(0,1fr)_220px]">
            <McpDetailInfoAside state={state} />
            <McpDetailToolsSection state={state} />
            <McpDetailStatsAside state={state} />
          </div>
        </div>
      </ScrollArea>
    </div>
  )
}
