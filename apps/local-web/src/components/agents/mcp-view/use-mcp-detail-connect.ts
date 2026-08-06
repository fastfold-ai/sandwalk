import type {
  ConnectMcpResult,
  McpCatalogEntry
} from '@sandwalk/agent-ui-core'
import { useCallback } from 'react'
import { toast } from 'sonner'

import {
  disposeMcpOAuthWatch,
  openMcpOAuthBrowser
} from './mcp-oauth-browser'
import { formatConnectError } from './mcp-view-shared'

type McpDetailConnectInput = {
  catalogEntry?: McpCatalogEntry | null
  supportsApiKey: boolean
  apiKeyDraft: string
  onConnectCatalog?: (input: {
    method: 'oauth' | 'api_key'
    apiKey?: string
  }) => Promise<ConnectMcpResult>
  onDisconnectCatalog?: () => Promise<ConnectMcpResult | void>
  onRefreshMeta?: () => Promise<void>
  loadTools: (
    isRefresh?: boolean
  ) => Promise<{ ok: boolean; toolCount?: number; message?: string } | null>
  setConnectPending: (value: boolean) => void
  setDisconnectPending: (value: boolean) => void
  setShowApiKey: (value: boolean) => void
  setApiKeyDraft: (value: string) => void
  setResult: (value: null) => void
  setError: (value: null) => void
}

export function useMcpDetailConnect({
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
}: McpDetailConnectInput) {
  const connectOAuth = useCallback(async () => {
    if (!onConnectCatalog || !catalogEntry) return
    setConnectPending(true)
    try {
      const connectResult = await onConnectCatalog({ method: 'oauth' })
      if (connectResult.authorizeUrl) {
        await openMcpOAuthBrowser(connectResult.authorizeUrl, async () => {
          await onRefreshMeta?.()
          const next = await loadTools(true)
          if (!next?.ok) return false
          disposeMcpOAuthWatch()
          toast.dismiss()
          toast.success(
            next.message || `Connected · ${next.toolCount ?? 0} tools`,
            { description: catalogEntry.name }
          )
          return true
        })
        toast.message('Complete sign-in in your browser…', {
          description: catalogEntry.name
        })
      } else if (!connectResult.ok) {
        toast.error(connectResult.message || 'OAuth connect failed', {
          description: catalogEntry.name
        })
        if (supportsApiKey) setShowApiKey(true)
      } else {
        toast.success(
          connectResult.message ||
            `Connected · ${connectResult.toolCount ?? 0} tools`,
          { description: catalogEntry.name }
        )
        await onRefreshMeta?.()
        await loadTools(true)
      }
    } catch (err) {
      const message = formatConnectError(err)
      toast.error(message, { description: catalogEntry.name })
      if (supportsApiKey) setShowApiKey(true)
    } finally {
      setConnectPending(false)
    }
  }, [
    catalogEntry,
    loadTools,
    onConnectCatalog,
    onRefreshMeta,
    setConnectPending,
    setShowApiKey,
    supportsApiKey
  ])

  const connectApiKey = useCallback(async () => {
    if (!onConnectCatalog || !catalogEntry) return
    const apiKey = apiKeyDraft.trim()
    if (!apiKey) {
      toast.error('API key is required', { description: catalogEntry.name })
      return
    }
    setConnectPending(true)
    try {
      const connectResult = await onConnectCatalog({
        method: 'api_key',
        apiKey
      })
      if (!connectResult.ok) {
        toast.error(connectResult.message || 'Connect failed', {
          description: catalogEntry.name
        })
      } else {
        toast.success(
          connectResult.message ||
            `Connected · ${connectResult.toolCount ?? 0} tools`,
          { description: catalogEntry.name }
        )
        setShowApiKey(false)
        setApiKeyDraft('')
        await onRefreshMeta?.()
        await loadTools(true)
      }
    } catch (err) {
      toast.error(formatConnectError(err), { description: catalogEntry.name })
    } finally {
      setConnectPending(false)
    }
  }, [
    apiKeyDraft,
    catalogEntry,
    loadTools,
    onConnectCatalog,
    onRefreshMeta,
    setApiKeyDraft,
    setConnectPending,
    setShowApiKey
  ])

  const primaryConnect = () => {
    const supportsOAuth =
      Boolean(catalogEntry) && catalogEntry?.authMode !== 'api_key'
    if (supportsOAuth && catalogEntry?.preferredAuth === 'oauth') {
      void connectOAuth()
      return
    }
    if (supportsApiKey && !supportsOAuth) {
      setShowApiKey(true)
      return
    }
    if (supportsOAuth) {
      void connectOAuth()
      return
    }
    setShowApiKey(true)
  }

  const disconnect = async () => {
    if (!onDisconnectCatalog || !catalogEntry) return
    setDisconnectPending(true)
    try {
      await onDisconnectCatalog()
      toast.success('Disconnected', { description: catalogEntry.name })
      setResult(null)
      setError(null)
      await onRefreshMeta?.()
    } catch (err) {
      toast.error(formatConnectError(err), { description: catalogEntry.name })
    } finally {
      setDisconnectPending(false)
    }
  }

  return {
    connectOAuth,
    connectApiKey,
    primaryConnect,
    disconnect
  }
}
