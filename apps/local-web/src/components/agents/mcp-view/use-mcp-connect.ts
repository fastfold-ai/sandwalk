import type {
  ConnectMcpResult,
  McpCatalogEntry
} from '@sandwalk/agent-ui-core'
import type { Dispatch, SetStateAction } from 'react'
import { useCallback } from 'react'
import { toast } from 'sonner'

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
          window.open(
            result.authorizeUrl,
            'fastfold-mcp-oauth',
            'width=560,height=720'
          )
          toast.message('Complete sign-in in the browser window…', {
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
        const oauthUnavailable =
          /no oauth registration|use api key connect/i.test(message)
        toast.error(
          oauthUnavailable
            ? `${entry.name} OAuth needs a registered client here — use API key instead.`
            : message,
          { description: entry.name }
        )
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
    async (entry: McpCatalogEntry) => {
      const apiKey = (apiKeyDraft[entry.id] || '').trim()
      if (!apiKey) {
        toast.error('API key is required', { description: entry.name })
        return
      }
      setPendingId(entry.id)
      try {
        const result = await onConnectCatalog(entry.id, {
          method: 'api_key',
          apiKey
        })
        if (result.ok) {
          toast.dismiss()
          toast.success(
            result.message || `Connected · ${result.toolCount ?? 0} tools`,
            { description: entry.name }
          )
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
          setShowApiKey(prev => ({ ...prev, [entry.id]: false }))
        } else {
          toast.error(result.message || 'Connect failed', {
            description: entry.name
          })
          setStatusPatch(prev => ({
            ...prev,
            [entry.id]: {
              connected: false,
              enabled: false,
              statusMessage: result.message || 'Connect failed',
              toolCount: null
            }
          }))
        }
      } catch (err) {
        toast.error(formatConnectError(err), { description: entry.name })
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
      setShowApiKey,
      setStatusPatch
    ]
  )

  return { connectOAuth, connectApiKey }
}
