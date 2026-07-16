import type { McpCatalogEntry } from '@sandwalk/agent-ui-core'
import type { Dispatch, SetStateAction } from 'react'
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { toast } from 'sonner'

import { type CatalogStatusPatch } from './mcp-view-shared'

export function useMcpHashFocus() {
  const location = useLocation()
  const focusedMcpKey = (() => {
    const raw = String(location.hash || '').replace(/^#/, '').trim()
    if (!raw) return null
    try {
      return decodeURIComponent(raw)
    } catch {
      return raw
    }
  })()

  useEffect(() => {
    if (!focusedMcpKey) return
    const timer = window.setTimeout(() => {
      const node = document.getElementById(`mcp-${focusedMcpKey}`)
      node?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 80)
    return () => window.clearTimeout(timer)
  }, [focusedMcpKey])

  return focusedMcpKey
}

export function useMcpStatusPatchSync(
  catalog: McpCatalogEntry[],
  setStatusPatch: Dispatch<SetStateAction<Record<string, CatalogStatusPatch>>>
) {
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
  }, [catalog, setStatusPatch])
}

export function useMcpOAuthMessage(
  onRefresh: () => Promise<void>,
  setStatusPatch: Dispatch<SetStateAction<Record<string, CatalogStatusPatch>>>
) {
  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const data = event.data
      if (!data || data.type !== 'fastfold-mcp-oauth') return
      const catalogId = String(data.catalogId || '')
      if (data.ok) {
        toast.dismiss()
        toast.success(data.message || 'Connected via OAuth', {
          description: catalogId || undefined
        })
        if (catalogId) {
          setStatusPatch(prev => ({
            ...prev,
            [catalogId]: {
              connected: true,
              enabled: data.enabled !== false,
              statusMessage: null,
              toolCount:
                typeof data.toolCount === 'number' ? data.toolCount : null
            }
          }))
        }
      } else {
        toast.error(data.error || 'OAuth failed', {
          description: catalogId || undefined
        })
        if (catalogId) {
          setStatusPatch(prev => ({
            ...prev,
            [catalogId]: {
              connected: false,
              statusMessage: data.error || 'OAuth failed'
            }
          }))
        }
      }
      void onRefresh()
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [onRefresh, setStatusPatch])
}
