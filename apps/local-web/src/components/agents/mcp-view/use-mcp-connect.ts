import type {
  ConnectMcpResult,
  McpCatalogEntry
} from '@sandwalk/agent-ui-core'
import type { Dispatch, SetStateAction } from 'react'
import { useCallback } from 'react'
import { toast } from 'sonner'

import { openMcpOAuthBrowser } from './mcp-oauth-browser'
import { type CatalogStatusPatch, formatConnectError } from './mcp-view-shared'

type McpConnectState = {
  apiKeyDraft: Record<string, string>
  setPendingId: (id: string | null) => void
  setStatusPatch: Dispatch<SetStateAction<Record<string, CatalogStatusPatch>>>
  setApiKeyDraft: Dispatch<SetStateAction<Record<string, string>>>
  setShowApiKey: Dispatch<SetStateAction<Record<string, boolean>>>
}

export function useMcpConnect({
  onConnectCatalog,
  onRefresh,
  apiKeyDraft,
  setPendingId,
  setStatusPatch,
  setApiKeyDraft,
  setShowApiKey
}: McpConnectState & {
  onConnectCatalog: (
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string }
  ) => Promise<ConnectMcpResult>
  onRefresh: () => Promise<void>
}) {
  const connectOAuth = useCallback(
    async (entry: McpCatalogEntry) => {
      setPendingId(entry.id)
      try {
        const result = await onConnectCatalog(entry.id, { method: 'oauth' })
        if (result.authorizeUrl) {
          await openMcpOAuthBrowser(result.authorizeUrl, onRefresh)
          toast.message('Complete sign-in in your browser…', {
            description: entry.name
          })
        } else if (!result.ok) {
          toast.error(result.message || 'OAuth connect failed', {
            description: entry.name
          })
          if (entry.authMode !== 'oauth') {
            setShowApiKey(prev => ({ ...prev, [entry.id]: true }))
          }
        }
      } catch (err) {
        const message = formatConnectError(err)
        const apiKeyOnly = /uses api key auth, not oauth/i.test(message)
        const oauthUnavailable =
          apiKeyOnly ||
          /no oauth registration|use api key connect/i.test(message)
        if (apiKeyOnly || oauthUnavailable) {
          toast.message('API key required', {
            description: `${entry.name} uses an API key — enter it in the dialog to connect.`
          })
        } else {
          toast.error(message, { description: entry.name })
        }
        if (entry.authMode !== 'oauth') {
          setShowApiKey(prev => ({ ...prev, [entry.id]: true }))
        }
      } finally {
        setPendingId(null)
        await onRefresh()
      }
    },
    [onConnectCatalog, onRefresh, setPendingId, setShowApiKey]
  )

  const connectApiKey = useCallback(
    async (
      entry: McpCatalogEntry
    ): Promise<{ ok: boolean; message: string }> => {
      const apiKey = (apiKeyDraft[entry.id] || '').trim()
      if (!apiKey) {
        const message = 'API key is required'
        toast.error(message, { description: entry.name })
        return { ok: false, message }
      }
      setPendingId(entry.id)
      try {
        const result = await onConnectCatalog(entry.id, {
          method: 'api_key',
          apiKey
        })
        if (result.ok) {
          const message =
            result.message || `Connected · ${result.toolCount ?? 0} tools`
          toast.dismiss()
          toast.success(message, { description: entry.name })
          setStatusPatch(prev => ({
            ...prev,
            [entry.id]: {
              connected: true,
              statusMessage: null,
              toolCount:
                typeof result.toolCount === 'number' ? result.toolCount : 0
            }
          }))
          setApiKeyDraft(prev => {
            const next = { ...prev }
            delete next[entry.id]
            return next
          })
          return { ok: true, message }
        }
        const message = result.message || 'Connect failed'
        toast.error(message, { description: entry.name })
        setStatusPatch(prev => ({
          ...prev,
          [entry.id]: {
            connected: false,
            enabled: false,
            statusMessage: message,
            toolCount: null
          }
        }))
        return { ok: false, message }
      } catch (err) {
        const message = formatConnectError(err)
        toast.error(message, { description: entry.name })
        return { ok: false, message }
      } finally {
        setPendingId(null)
        await onRefresh()
      }
    },
    [
      apiKeyDraft,
      onConnectCatalog,
      onRefresh,
      setApiKeyDraft,
      setPendingId,
      setStatusPatch
    ]
  )

  return { connectOAuth, connectApiKey }
}
