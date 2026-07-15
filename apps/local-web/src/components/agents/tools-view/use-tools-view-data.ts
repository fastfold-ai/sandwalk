import type {
  DatasetSummary,
  ToolBatchAction,
  ToolBatchResult,
  ToolCatalog,
  ToolSummary
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { toolTier } from './tools-view-shared'

export function useToolsViewData({
  onListTools,
  onUpdateToolEnabled,
  onBatchUpdateTools,
  onListDatasets
}: {
  onListTools: (signal?: AbortSignal) => Promise<ToolCatalog>
  onUpdateToolEnabled: (
    toolId: string,
    enabled: boolean,
    signal?: AbortSignal
  ) => Promise<ToolSummary>
  onBatchUpdateTools: (
    action: ToolBatchAction,
    ids: string[],
    signal?: AbortSignal
  ) => Promise<ToolBatchResult>
  onListDatasets: (signal?: AbortSignal) => Promise<DatasetSummary[]>
}) {
  const [catalog, setCatalog] = useState<ToolCatalog | null>(null)
  const [datasets, setDatasets] = useState<DatasetSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [tierFilter, setTierFilter] = useState<'all' | 'core' | 'extra'>('all')
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'enabled' | 'disabled'
  >('all')
  const [pending, setPending] = useState<Record<string, boolean>>({})
  const [batchBusy, setBatchBusy] = useState(false)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const [nextTools, nextDatasets] = await Promise.all([
        onListTools(signal),
        onListDatasets(signal).catch(() => [] as DatasetSummary[])
      ])
      if (!signal?.aborted) {
        setCatalog(nextTools)
        setDatasets(nextDatasets)
      }
    },
    [onListTools, onListDatasets]
  )

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    void load(controller.signal)
      .catch(err => {
        if (!controller.signal.aborted)
          setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [load])

  const refresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRefreshing(false)
    }
  }

  const tools = catalog?.data || []

  const categories = useMemo(() => {
    const present = new Set(tools.map(t => t.category))
    return [...present].sort((a, b) => a.localeCompare(b))
  }, [tools])

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const tool of tools) {
      counts[tool.category] = (counts[tool.category] || 0) + 1
    }
    return counts
  }, [tools])

  const enabledCount = tools.filter(t => t.enabled).length
  const disabledCount = tools.length - enabledCount
  const coreCount = tools.filter(t => toolTier(t) === 'core').length
  const extraCount = tools.length - coreCount

  const datasetStatusById = useMemo(() => {
    const map = new Map<string, DatasetSummary['status']>()
    for (const dataset of datasets) map.set(dataset.id, dataset.status)
    return map
  }, [datasets])

  const resolveRequirement = useCallback(
    (token: string) => {
      const normalized = token.trim().toLowerCase()
      let datasetId: string | null = null
      if (datasetStatusById.has(normalized)) {
        datasetId = normalized
      } else {
        const prefix = normalized.split('_')[0]
        if (datasetStatusById.has(prefix)) datasetId = prefix
      }
      if (!datasetId) return { datasetId: null, installed: null as boolean | null }
      const status = datasetStatusById.get(datasetId)
      const installed = status === 'complete' || status === 'on-demand'
      return { datasetId, installed }
    },
    [datasetStatusById]
  )

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return tools.filter(tool => {
      if (categoryFilter !== 'all' && tool.category !== categoryFilter)
        return false
      if (tierFilter !== 'all' && toolTier(tool) !== tierFilter) return false
      if (statusFilter === 'enabled' && !tool.enabled) return false
      if (statusFilter === 'disabled' && tool.enabled) return false
      if (!needle) return true
      const haystack = [
        tool.id,
        tool.description,
        tool.category,
        tool.requiresData.join(' ')
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [tools, query, categoryFilter, tierFilter, statusFilter])

  const enableEligible = useMemo(
    () => filtered.filter(t => !t.enabled).map(t => t.id),
    [filtered]
  )
  const disableEligible = useMemo(
    () => filtered.filter(t => t.enabled).map(t => t.id),
    [filtered]
  )

  const batchUpdate = async (action: ToolBatchAction) => {
    const ids = action === 'enable' ? enableEligible : disableEligible
    if (ids.length === 0) return
    setBatchBusy(true)
    setError(null)
    try {
      const result = await onBatchUpdateTools(action, ids)
      const succeeded = new Set(result.succeeded)
      const nextEnabled = action === 'enable'
      setCatalog(prev =>
        prev
          ? {
              ...prev,
              data: prev.data.map(item =>
                succeeded.has(item.id)
                  ? { ...item, enabled: nextEnabled }
                  : item
              )
            }
          : prev
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBatchBusy(false)
    }
  }

  const toggle = async (tool: ToolSummary) => {
    setPending(prev => ({ ...prev, [tool.id]: true }))
    setError(null)
    try {
      const updated = await onUpdateToolEnabled(tool.id, !tool.enabled)
      setCatalog(prev =>
        prev
          ? {
              ...prev,
              data: prev.data.map(item =>
                item.id === tool.id
                  ? { ...item, enabled: updated.enabled }
                  : item
              )
            }
          : prev
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setPending(prev => {
        const next = { ...prev }
        delete next[tool.id]
        return next
      })
    }
  }

  return {
    catalog,
    loading,
    refreshing,
    error,
    query,
    setQuery,
    categoryFilter,
    setCategoryFilter,
    tierFilter,
    setTierFilter,
    statusFilter,
    setStatusFilter,
    pending,
    batchBusy,
    tools,
    categories,
    categoryCounts,
    enabledCount,
    disabledCount,
    coreCount,
    extraCount,
    filtered,
    enableEligible,
    disableEligible,
    refresh,
    batchUpdate,
    toggle,
    resolveRequirement
  }
}
