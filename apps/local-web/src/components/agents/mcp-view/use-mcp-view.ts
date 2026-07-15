import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpServer
} from '@sandwalk/agent-ui-core'
import { useMemo, useState } from 'react'

import { type CatalogStatusPatch } from './mcp-view-shared'
import { useMcpConnect } from './use-mcp-connect'
import {
  featuredCatalogVisible,
  useMcpCatalogLists,
  useMcpCustomForm
} from './use-mcp-custom-form'
import {
  useMcpHashFocus,
  useMcpOAuthMessage,
  useMcpStatusPatchSync
} from './use-mcp-view-effects'

export type McpViewInput = {
  mcpServers: McpServer[]
  catalog: McpCatalogEntry[]
  featuredOnly?: boolean
  featuredLimit?: number | null
  onRefresh: () => Promise<void>
  onConnectCatalog: (
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string }
  ) => Promise<ConnectMcpResult>
  onToggleCatalog: (entry: McpCatalogEntry, enabled: boolean) => Promise<void>
  onCreateMcp: (
    input: Omit<McpServer, 'id' | 'createdAt' | 'updatedAt'>
  ) => Promise<void>
}

export function useMcpView({
  mcpServers,
  catalog,
  featuredOnly = false,
  featuredLimit,
  onRefresh,
  onConnectCatalog,
  onToggleCatalog,
  onCreateMcp
}: McpViewInput) {
  const focusedMcpKey = useMcpHashFocus()
  const customForm = useMcpCustomForm(onCreateMcp)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [apiKeyDraft, setApiKeyDraft] = useState<Record<string, string>>({})
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({})
  const [statusPatch, setStatusPatch] = useState<
    Record<string, CatalogStatusPatch>
  >({})

  useMcpStatusPatchSync(catalog, setStatusPatch)
  useMcpOAuthMessage(onRefresh, setStatusPatch)

  const { connectOAuth, connectApiKey } = useMcpConnect({
    onConnectCatalog,
    onRefresh,
    apiKeyDraft,
    setPendingId,
    setStatusPatch,
    setApiKeyDraft,
    setShowApiKey
  })

  const customServers = useMemo(
    () => mcpServers.filter(server => !server.catalogId),
    [mcpServers]
  )

  const { featuredCatalog, moreCatalog } = useMcpCatalogLists(catalog)
  const featuredVisible = featuredCatalogVisible(
    featuredCatalog,
    featuredOnly,
    featuredLimit
  )

  const catalogCardProps = {
    statusPatch,
    pendingId,
    focusedMcpKey,
    showApiKey,
    apiKeyDraft,
    onConnectOAuth: (entry: McpCatalogEntry) => void connectOAuth(entry),
    onConnectApiKey: (entry: McpCatalogEntry) => void connectApiKey(entry),
    onToggleCatalog,
    onPendingIdChange: setPendingId,
    onStatusPatchChange: setStatusPatch,
    onShowApiKeyChange: (id: string, show: boolean) =>
      setShowApiKey(prev => ({ ...prev, [id]: show })),
    onApiKeyDraftChange: (id: string, value: string) =>
      setApiKeyDraft(prev => ({ ...prev, [id]: value }))
  }

  return {
    focusedMcpKey,
    mcpMode: customForm.mcpMode,
    mcpName: customForm.mcpName,
    mcpTransport: customForm.mcpTransport,
    mcpTarget: customForm.mcpTarget,
    mcpDescription: customForm.mcpDescription,
    mcpAdvancedOpen: customForm.mcpAdvancedOpen,
    mcpOauthClientId: customForm.mcpOauthClientId,
    mcpOauthServerUrl: customForm.mcpOauthServerUrl,
    mcpOauthScopes: customForm.mcpOauthScopes,
    mcpHeadersHelper: customForm.mcpHeadersHelper,
    mcpHeaderRows: customForm.mcpHeaderRows,
    creatingCustom: customForm.creatingCustom,
    customServers,
    featuredCatalog,
    moreCatalog,
    featuredVisible,
    catalogCardProps,
    setMcpMode: customForm.setMcpMode,
    setMcpName: customForm.setMcpName,
    setMcpTransport: customForm.setMcpTransport,
    setMcpTarget: customForm.setMcpTarget,
    setMcpDescription: customForm.setMcpDescription,
    setMcpAdvancedOpen: customForm.setMcpAdvancedOpen,
    setMcpOauthClientId: customForm.setMcpOauthClientId,
    setMcpOauthServerUrl: customForm.setMcpOauthServerUrl,
    setMcpOauthScopes: customForm.setMcpOauthScopes,
    setMcpHeadersHelper: customForm.setMcpHeadersHelper,
    setMcpHeaderRows: customForm.setMcpHeaderRows,
    submitCustomMcp: customForm.submitCustomMcp
  }
}
