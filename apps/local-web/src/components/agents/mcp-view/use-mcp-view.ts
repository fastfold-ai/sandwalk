import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpServer,
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { toast } from 'sonner'

import {
  type CatalogStatusPatch,
  type CustomMode,
  formatConnectError,
  type HeaderRow,
  headersFromRows,
  newHeaderRow,
} from './mcp-view-shared'

export type McpViewInput = {
  mcpServers: McpServer[]
  catalog: McpCatalogEntry[]
  featuredOnly?: boolean
  featuredLimit?: number | null
  onRefresh: () => Promise<void>
  onConnectCatalog: (
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string },
  ) => Promise<ConnectMcpResult>
  onToggleCatalog: (entry: McpCatalogEntry, enabled: boolean) => Promise<void>
  onCreateMcp: (
    input: Omit<McpServer, 'id' | 'createdAt' | 'updatedAt'>,
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
  onCreateMcp,
}: McpViewInput) {
  const location = useLocation()
  const [focusedMcpKey, setFocusedMcpKey] = useState<string | null>(null)
  const [mcpMode, setMcpMode] = useState<CustomMode>('remote')
  const [mcpName, setMcpName] = useState('')
  const [mcpTransport, setMcpTransport] = useState<'sse' | 'streamable_http'>(
    'streamable_http',
  )
  const [mcpTarget, setMcpTarget] = useState('')
  const [mcpDescription, setMcpDescription] = useState('')
  const [mcpAdvancedOpen, setMcpAdvancedOpen] = useState(false)
  const [mcpOauthClientId, setMcpOauthClientId] = useState('')
  const [mcpOauthServerUrl, setMcpOauthServerUrl] = useState('')
  const [mcpOauthScopes, setMcpOauthScopes] = useState('')
  const [mcpHeadersHelper, setMcpHeadersHelper] = useState('')
  const [mcpHeaderRows, setMcpHeaderRows] = useState<HeaderRow[]>([newHeaderRow()])
  const [creatingCustom, setCreatingCustom] = useState(false)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [apiKeyDraft, setApiKeyDraft] = useState<Record<string, string>>({})
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({})
  const [statusPatch, setStatusPatch] = useState<
    Record<string, CatalogStatusPatch>
  >({})

  const resetCustomForm = useCallback(() => {
    setMcpName('')
    setMcpTarget('')
    setMcpDescription('')
    setMcpOauthClientId('')
    setMcpOauthServerUrl('')
    setMcpOauthScopes('')
    setMcpHeadersHelper('')
    setMcpHeaderRows([newHeaderRow()])
    setMcpTransport('streamable_http')
    setMcpAdvancedOpen(false)
  }, [])

  const submitCustomMcp = useCallback(async () => {
    const name = mcpName.trim()
    const target = mcpTarget.trim()
    if (!name || !target) return
    setCreatingCustom(true)
    try {
      const isLocal = mcpMode === 'local'
      const parts = isLocal ? target.split(/\s+/).filter(Boolean) : []
      const headers = isLocal ? null : headersFromRows(mcpHeaderRows)
      await onCreateMcp({
        name,
        transport: isLocal ? 'stdio' : mcpTransport,
        command: isLocal ? parts[0] || null : null,
        args: isLocal ? parts.slice(1) : [],
        url: isLocal ? null : target,
        enabled: true,
        description: mcpDescription.trim() || null,
        oauthClientId: mcpOauthClientId.trim() || null,
        oauthServerUrl: mcpOauthServerUrl.trim() || null,
        oauthScopes: mcpOauthScopes.trim() || null,
        headersHelperCommand: mcpHeadersHelper.trim() || null,
        headers,
      })
      resetCustomForm()
      toast.success(`Added ${name}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add MCP server')
    } finally {
      setCreatingCustom(false)
    }
  }, [
    mcpDescription,
    mcpHeaderRows,
    mcpHeadersHelper,
    mcpMode,
    mcpName,
    mcpOauthClientId,
    mcpOauthScopes,
    mcpOauthServerUrl,
    mcpTarget,
    mcpTransport,
    onCreateMcp,
    resetCustomForm,
  ])

  const customServers = useMemo(
    () => mcpServers.filter(server => !server.catalogId),
    [mcpServers],
  )

  useEffect(() => {
    const raw = String(location.hash || '').replace(/^#/, '').trim()
    if (!raw) {
      setFocusedMcpKey(null)
      return
    }
    let key = ''
    try {
      key = decodeURIComponent(raw)
    } catch {
      key = raw
    }
    setFocusedMcpKey(key)
    const timer = window.setTimeout(() => {
      const node = document.getElementById(`mcp-${key}`)
      node?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 80)
    return () => window.clearTimeout(timer)
  }, [location.hash])

  useEffect(() => {
    setStatusPatch(prev => {
      if (Object.keys(prev).length === 0) return prev
      const next = { ...prev }
      for (const entry of catalog) {
        const patch = next[entry.id]
        if (!patch) continue
        const connectedMatches =
          patch.connected === undefined || patch.connected === entry.connected
        const enabledMatches =
          patch.enabled === undefined || patch.enabled === entry.enabled
        const messageMatches =
          patch.statusMessage === undefined ||
          (patch.statusMessage ?? null) === (entry.statusMessage ?? null)
        const countMatches =
          patch.toolCount === undefined ||
          patch.toolCount === (entry.toolCount ?? null)
        if (
          connectedMatches &&
          enabledMatches &&
          messageMatches &&
          countMatches
        ) {
          delete next[entry.id]
        }
      }
      return next
    })
  }, [catalog])

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const data = event.data
      if (!data || data.type !== 'fastfold-mcp-oauth') return
      const catalogId = String(data.catalogId || '')
      if (data.ok) {
        toast.dismiss()
        toast.success(data.message || 'Connected via OAuth', {
          description: catalogId || undefined,
        })
        if (catalogId) {
          setStatusPatch(prev => ({
            ...prev,
            [catalogId]: {
              connected: true,
              statusMessage: null,
              toolCount: null,
            },
          }))
        }
      } else {
        toast.error(data.error || 'OAuth failed', {
          description: catalogId || undefined,
        })
        if (catalogId) {
          setStatusPatch(prev => ({
            ...prev,
            [catalogId]: {
              connected: false,
              statusMessage: data.error || 'OAuth failed',
            },
          }))
        }
      }
      void onRefresh()
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [onRefresh])

  const connectOAuth = useCallback(
    async (entry: McpCatalogEntry) => {
      setPendingId(entry.id)
      try {
        const result = await onConnectCatalog(entry.id, { method: 'oauth' })
        if (result.authorizeUrl) {
          window.open(
            result.authorizeUrl,
            'fastfold-mcp-oauth',
            'width=560,height=720',
          )
          toast.message('Complete sign-in in the browser window…', {
            description: entry.name,
          })
        } else if (!result.ok) {
          toast.error(result.message || 'OAuth connect failed', {
            description: entry.name,
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
          { description: entry.name },
        )
        if (entry.authMode !== 'oauth') {
          setShowApiKey(prev => ({ ...prev, [entry.id]: true }))
        }
      } finally {
        setPendingId(null)
        await onRefresh()
      }
    },
    [onConnectCatalog, onRefresh],
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
          apiKey,
        })
        if (result.ok) {
          toast.dismiss()
          toast.success(
            result.message || `Connected · ${result.toolCount ?? 0} tools`,
            { description: entry.name },
          )
          setStatusPatch(prev => ({
            ...prev,
            [entry.id]: {
              connected: true,
              statusMessage: null,
              toolCount:
                typeof result.toolCount === 'number' ? result.toolCount : 0,
            },
          }))
          setApiKeyDraft(prev => {
            const next = { ...prev }
            delete next[entry.id]
            return next
          })
          setShowApiKey(prev => ({ ...prev, [entry.id]: false }))
        } else {
          toast.error(result.message || 'Connect failed', {
            description: entry.name,
          })
          setStatusPatch(prev => ({
            ...prev,
            [entry.id]: {
              connected: false,
              enabled: false,
              statusMessage: result.message || 'Connect failed',
              toolCount: null,
            },
          }))
        }
      } catch (err) {
        toast.error(formatConnectError(err), { description: entry.name })
      } finally {
        setPendingId(null)
        await onRefresh()
      }
    },
    [apiKeyDraft, onConnectCatalog, onRefresh],
  )

  const featuredCatalog = useMemo(
    () => catalog.filter(entry => entry.featured !== false),
    [catalog],
  )
  const moreCatalog = useMemo(
    () => catalog.filter(entry => entry.featured === false),
    [catalog],
  )

  const featuredVisible = (() => {
    if (!featuredOnly) return featuredCatalog
    if (featuredLimit === null) return featuredCatalog
    const limit = featuredLimit === undefined ? 2 : featuredLimit
    return featuredCatalog.slice(0, limit)
  })()

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
      setApiKeyDraft(prev => ({ ...prev, [id]: value })),
  }

  return {
    focusedMcpKey,
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
    customServers,
    featuredCatalog,
    moreCatalog,
    featuredVisible,
    catalogCardProps,
    setMcpMode,
    setMcpName,
    setMcpTransport,
    setMcpTarget,
    setMcpDescription,
    setMcpAdvancedOpen,
    setMcpOauthClientId,
    setMcpOauthServerUrl,
    setMcpOauthScopes,
    setMcpHeadersHelper,
    setMcpHeaderRows,
    submitCustomMcp,
  }
}
