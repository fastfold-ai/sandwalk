import { McpDetailView, McpView } from './dashboard-main-views-lazy'
import type { DashboardMainViewsProps } from './dashboard-main-views-types'

export function DashboardMainMcpPanel({
  client,
  navigate,
  mcpServers,
  mcpCatalog,
  mcpCatalogLoading,
  mcpCatalogDetailId,
  mcpServerDetailId,
  mcpDetailCatalogEntry,
  mcpDetailServer,
  isMcpDetail,
  loadMcpServers,
  refreshMcp,
  loadIntegrations
}: Pick<
  DashboardMainViewsProps,
  | 'client'
  | 'navigate'
  | 'mcpServers'
  | 'mcpCatalog'
  | 'mcpCatalogLoading'
  | 'mcpCatalogDetailId'
  | 'mcpServerDetailId'
  | 'mcpDetailCatalogEntry'
  | 'mcpDetailServer'
  | 'isMcpDetail'
  | 'loadMcpServers'
  | 'refreshMcp'
  | 'loadIntegrations'
>) {
  if (isMcpDetail) {
    return (
      <McpDetailView
        kind={mcpCatalogDetailId ? 'catalog' : 'server'}
        catalogEntry={mcpDetailCatalogEntry}
        server={mcpDetailServer}
        onBack={() => navigate('/dashboard/mcp')}
        onLoadTools={async () => {
          if (mcpCatalogDetailId) {
            return client.validateMcpCatalog(mcpCatalogDetailId)
          }
          if (mcpServerDetailId) {
            return client.validateMcpServer(mcpServerDetailId)
          }
          return {
            ok: false,
            toolCount: 0,
            message: 'MCP not found',
            tools: [],
            toolDetails: []
          }
        }}
        onToggleEnabled={
          mcpCatalogDetailId && mcpDetailCatalogEntry
            ? async enabled => {
                await client.setMcpCatalogEnabled(mcpCatalogDetailId, enabled)
                await refreshMcp()
              }
            : mcpServerDetailId
              ? async enabled => {
                  await client.updateMcpServer(mcpServerDetailId, {
                    enabled
                  })
                  await loadMcpServers()
                }
              : undefined
        }
        onConnectCatalog={
          mcpCatalogDetailId
            ? async input => {
                const result = await client.connectMcpCatalog(
                  mcpCatalogDetailId,
                  input
                )
                await refreshMcp()
                await loadIntegrations()
                return result
              }
            : undefined
        }
        onDisconnectCatalog={
          mcpCatalogDetailId
            ? async () => {
                const result =
                  await client.disconnectMcpCatalog(mcpCatalogDetailId)
                await refreshMcp()
                await loadIntegrations()
                return result
              }
            : undefined
        }
        onRefreshMeta={async () => {
          await refreshMcp()
          await loadIntegrations()
        }}
      />
    )
  }

  return (
    <McpView
      mcpServers={mcpServers}
      catalog={mcpCatalog}
      catalogLoading={mcpCatalogLoading}
      onRefresh={refreshMcp}
      onConnectCatalog={async (catalogId, input) => {
        const result = await client.connectMcpCatalog(catalogId, input)
        await refreshMcp()
        await loadIntegrations()
        return result
      }}
      onToggleCatalog={async (entry, enabled) => {
        await client.setMcpCatalogEnabled(entry.id, enabled)
        await refreshMcp()
      }}
      onCreateMcp={async input => {
        await client.createMcpServer(input)
        await loadMcpServers()
      }}
      onDeleteMcp={async id => {
        await client.deleteMcpServer(id)
        await loadMcpServers()
      }}
      onToggleCustom={async (id, enabled) => {
        await client.updateMcpServer(id, { enabled })
        await loadMcpServers()
      }}
      onConnectCustom={async (server, input) => {
        const result = await client.connectMcpServer(server.id, input)
        if (input.method === 'api_key' || !result.authorizeUrl) {
          await loadMcpServers()
        }
        return result
      }}
      onOpenCatalog={entry =>
        navigate(`/dashboard/mcp/catalog/${encodeURIComponent(entry.id)}`)
      }
      onOpenServer={server =>
        navigate(`/dashboard/mcp/server/${encodeURIComponent(server.id)}`)
      }
      onLoadMcpJson={async () => {
        const result = await client.getMcpJsonConfig()
        return {
          path: result.path,
          document: result.document
        }
      }}
      onSaveMcpJson={async document => {
        await client.putMcpJsonConfig(document)
        await loadMcpServers()
      }}
    />
  )
}
