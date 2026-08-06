import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpServer,
  ValidateMcpResult
} from '@sandwalk/agent-ui-core'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { disposeMcpOAuthWatch } from './mcp-oauth-browser'
import { useMcpDetailConnect } from './use-mcp-detail-connect'

export type McpDetailViewInput = {
  kind: 'catalog' | 'server'
  catalogEntry?: McpCatalogEntry | null
  server?: McpServer | null
  onLoadTools: () => Promise<ValidateMcpResult>
  onToggleEnabled?: (enabled: boolean) => Promise<void>
  onConnectCatalog?: (input: {
    method: 'oauth' | 'api_key'
    apiKey?: string
  }) => Promise<ConnectMcpResult>
  onDisconnectCatalog?: () => Promise<ConnectMcpResult | void>
  onRefreshMeta?: () => Promise<void>
}

export function useMcpDetailView({
  kind,
  catalogEntry,
  server,
  onLoadTools,
  onToggleEnabled,
  onConnectCatalog,
  onDisconnectCatalog,
  onRefreshMeta
}: McpDetailViewInput) {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ValidateMcpResult | null>(null)
  const [togglePending, setTogglePending] = useState(false)
  const [connectPending, setConnectPending] = useState(false)
  const [disconnectPending, setDisconnectPending] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  const [apiKeyDraft, setApiKeyDraft] = useState('')
  const [toolQuery, setToolQuery] = useState('')

  const title =
    kind === 'catalog'
      ? catalogEntry?.name || 'MCP'
      : server?.name || 'MCP'
  const description =
    kind === 'catalog'
      ? catalogEntry?.description || null
      : server?.description || null
  const enabled =
    kind === 'catalog'
      ? Boolean(catalogEntry?.enabled)
      : Boolean(server?.enabled)
  const configured =
    kind === 'catalog'
      ? Boolean(catalogEntry?.configured || catalogEntry?.connected)
      : Boolean(server)
  const connected =
    kind === 'catalog'
      ? Boolean(catalogEntry?.connected || catalogEntry?.configured)
      : Boolean(server?.enabled)
  const docsUrl = kind === 'catalog' ? catalogEntry?.docsUrl || null : null
  const transport =
    kind === 'catalog'
      ? catalogEntry?.transport || null
      : server?.transport || null
  const endpoint =
    kind === 'catalog'
      ? catalogEntry?.transport === 'stdio'
        ? catalogEntry?.command || null
        : catalogEntry?.url || null
      : server?.url || server?.command || null

  const isLocalStdio =
    kind === 'catalog' &&
    Boolean(
      catalogEntry &&
        (catalogEntry.transport === 'stdio' || catalogEntry.authMode === 'none')
    )
  const supportsApiKey =
    kind === 'catalog' && catalogEntry && !isLocalStdio
      ? catalogEntry.authMode !== 'oauth'
      : false
  const supportsOAuth =
    kind === 'catalog' && catalogEntry && !isLocalStdio
      ? catalogEntry.authMode !== 'api_key'
      : false
  const hasBothAuth = supportsApiKey && supportsOAuth
  const connectLabel = configured ? 'Reconnect' : 'Connect'
  const needsReconnect =
    Boolean(error) &&
    /expired|reconnect|invalid_token|unauthorized|401|500/i.test(error || '')

  const statusLabel = useMemo(() => {
    if (result) {
      if (result.ok) return 'Healthy'
      if (needsReconnect || /expired|reconnect/i.test(result.message || '')) {
        return 'Needs reconnect'
      }
      return 'Probe failed'
    }
    if (connected) return 'Connected'
    if (enabled) return 'Enabled'
    return 'Disabled'
  }, [connected, enabled, needsReconnect, result])

  const statusHealthy = result?.ok === true
  const statusWarn =
    Boolean(result && !result.ok) || needsReconnect || Boolean(error)

  const tools = useMemo(() => {
    if (result?.toolDetails?.length) return result.toolDetails
    return (result?.tools || []).map(name => ({
      name,
      title: null,
      description: null,
      inputSchema: null
    }))
  }, [result])

  const filteredTools = useMemo(() => {
    const q = toolQuery.trim().toLowerCase()
    if (!q) return tools
    return tools.filter(tool => {
      const haystack = [tool.name, tool.title, tool.description]
        .filter(Boolean)
        .join('\n')
        .toLowerCase()
      return haystack.includes(q)
    })
  }, [toolQuery, tools])

  const missingDescriptions =
    tools.length > 0 && tools.every(tool => !tool.description)

  async function loadTools(isRefresh = false) {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const next = await onLoadTools()
      setResult(next)
      if (!next.ok) {
        setError(next.message || 'Unable to load MCP tools')
      }
      return next
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : String(err))
      return null
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    void loadTools(false)
  }, [kind, catalogEntry?.id, server?.id])

  useEffect(() => {
    if (kind !== 'catalog' || !onRefreshMeta) return
    const onMessage = (event: MessageEvent) => {
      const data = event.data
      if (!data || data.type !== 'fastfold-mcp-oauth') return
      const catalogId = String(data.catalogId || '')
      if (catalogEntry?.id && catalogId && catalogId !== catalogEntry.id) {
        return
      }
      disposeMcpOAuthWatch()
      if (data.ok) {
        toast.dismiss()
        toast.success(data.message || 'Connected via OAuth', {
          description: catalogEntry?.name
        })
        void onRefreshMeta().then(() => loadTools(true))
      } else {
        toast.error(data.error || 'OAuth failed', {
          description: catalogEntry?.name
        })
        void onRefreshMeta()
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [catalogEntry?.id, catalogEntry?.name, kind, onRefreshMeta])

  const {
    connectOAuth,
    connectApiKey,
    primaryConnect,
    disconnect
  } = useMcpDetailConnect({
    catalogEntry,
    supportsApiKey,
    apiKeyDraft,
    onConnectCatalog,
    onDisconnectCatalog,
    onRefreshMeta,
    loadTools,
    setConnectPending,
    setDisconnectPending,
    setShowApiKey,
    setApiKeyDraft,
    setResult,
    setError
  })

  const showCatalogActions =
    kind === 'catalog' && Boolean(onConnectCatalog) && !isLocalStdio

  const toggleEnabled = () => {
    if (!onToggleEnabled) return
    if (kind === 'catalog' && !configured && !enabled) {
      toast.error(
        isLocalStdio
          ? 'Install the launcher first (sandwalk mcp install pymol), then enable.'
          : 'Connect with OAuth or API key first, then enable.',
        {
          description: title
        }
      )
      return
    }
    setTogglePending(true)
    void onToggleEnabled(!enabled)
      .catch(() => undefined)
      .finally(() => setTogglePending(false))
  }

  return {
    loading,
    refreshing,
    error,
    result,
    togglePending,
    connectPending,
    disconnectPending,
    showApiKey,
    setShowApiKey,
    apiKeyDraft,
    setApiKeyDraft,
    toolQuery,
    setToolQuery,
    title,
    description,
    enabled,
    configured,
    connected,
    docsUrl,
    transport,
    endpoint,
    supportsApiKey,
    supportsOAuth,
    hasBothAuth,
    connectLabel,
    needsReconnect,
    statusLabel,
    statusHealthy,
    statusWarn,
    tools,
    filteredTools,
    missingDescriptions,
    showCatalogActions,
    isLocalStdio,
    kind,
    catalogEntry,
    hasToggle: Boolean(onToggleEnabled),
    loadTools,
    connectOAuth,
    connectApiKey,
    primaryConnect,
    disconnect,
    toggleEnabled,
    onDisconnectCatalog
  }
}

export type McpDetailViewState = ReturnType<typeof useMcpDetailView>
