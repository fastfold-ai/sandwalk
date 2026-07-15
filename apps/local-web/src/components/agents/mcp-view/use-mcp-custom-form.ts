import type { McpCatalogEntry, McpServer } from '@sandwalk/agent-ui-core'
import { useCallback, useState } from 'react'
import { toast } from 'sonner'

import {
  type CustomMode,
  type HeaderRow,
  headersFromRows,
  newHeaderRow
} from './mcp-view-shared'

export function useMcpCustomForm(
  onCreateMcp: (
    input: Omit<McpServer, 'id' | 'createdAt' | 'updatedAt'>
  ) => Promise<void>
) {
  const [mcpMode, setMcpMode] = useState<CustomMode>('remote')
  const [mcpName, setMcpName] = useState('')
  const [mcpTransport, setMcpTransport] = useState<'sse' | 'streamable_http'>(
    'streamable_http'
  )
  const [mcpTarget, setMcpTarget] = useState('')
  const [mcpDescription, setMcpDescription] = useState('')
  const [mcpAdvancedOpen, setMcpAdvancedOpen] = useState(false)
  const [mcpOauthClientId, setMcpOauthClientId] = useState('')
  const [mcpOauthServerUrl, setMcpOauthServerUrl] = useState('')
  const [mcpOauthScopes, setMcpOauthScopes] = useState('')
  const [mcpHeadersHelper, setMcpHeadersHelper] = useState('')
  const [mcpHeaderRows, setMcpHeaderRows] = useState<HeaderRow[]>([
    newHeaderRow()
  ])
  const [creatingCustom, setCreatingCustom] = useState(false)

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
        headers
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
    resetCustomForm
  ])

  return {
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
    submitCustomMcp
  }
}

export function useMcpCatalogLists(catalog: McpCatalogEntry[]) {
  const featuredCatalog = catalog.filter(entry => entry.featured !== false)
  const moreCatalog = catalog.filter(entry => entry.featured === false)
  return { featuredCatalog, moreCatalog }
}

export function featuredCatalogVisible(
  featuredCatalog: McpCatalogEntry[],
  featuredOnly: boolean,
  featuredLimit?: number | null
) {
  if (!featuredOnly) return featuredCatalog
  if (featuredLimit === null) return featuredCatalog
  const limit = featuredLimit === undefined ? 2 : featuredLimit
  return featuredCatalog.slice(0, limit)
}
