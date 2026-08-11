import type { Specialist, ToolCatalog, ToolSummary } from '@sandwalk/agent-ui-core'
import { type Dispatch, type SetStateAction,useEffect, useMemo, useState } from 'react'

import type { SpecialistFormState } from '@/components/agents/specialists-view/specialists-view-utils'

type SpecialistsEditorToolsInput = {
  mode: 'new' | 'edit'
  editing: Specialist | null
  setForm: Dispatch<SetStateAction<SpecialistFormState>>
  onListTools?: (signal?: AbortSignal) => Promise<ToolCatalog>
}

export function useSpecialistsEditorTools({
  mode,
  editing,
  setForm,
  onListTools
}: SpecialistsEditorToolsInput) {
  const [catalogTools, setCatalogTools] = useState<ToolSummary[]>([])
  const [toolsLoading, setToolsLoading] = useState(false)
  const [toolQuery, setToolQuery] = useState('')

  useEffect(() => {
    setToolQuery('')
  }, [editing, mode])

  useEffect(() => {
    if (!onListTools) return
    const controller = new AbortController()
    setToolsLoading(true)
    void onListTools(controller.signal)
      .then(catalog => {
        if (!controller.signal.aborted) setCatalogTools(catalog.data || [])
      })
      .catch(() => {
        if (!controller.signal.aborted) setCatalogTools([])
      })
      .finally(() => {
        if (!controller.signal.aborted) setToolsLoading(false)
      })
    return () => controller.abort()
  }, [onListTools])

  useEffect(() => {
    if (mode !== 'new' || catalogTools.length === 0) return
    setForm(current => {
      if (current.toolNames.length > 0) return current
      return {
        ...current,
        toolNames: catalogTools
          .filter(tool => tool.tier === 'core')
          .map(tool => tool.id)
          .sort()
      }
    })
  }, [catalogTools, mode, setForm])

  const filteredCatalogTools = useMemo(() => {
    const needle = toolQuery.trim().toLowerCase()
    if (!needle) return catalogTools
    return catalogTools.filter(tool =>
      `${tool.id} ${tool.name} ${tool.description} ${tool.category}`
        .toLowerCase()
        .includes(needle)
    )
  }, [catalogTools, toolQuery])

  const coreTools = useMemo(
    () => filteredCatalogTools.filter(tool => tool.tier === 'core'),
    [filteredCatalogTools]
  )
  const extraTools = useMemo(
    () => filteredCatalogTools.filter(tool => tool.tier !== 'core'),
    [filteredCatalogTools]
  )

  const toggleTool = (toolId: string) => {
    setForm(current => {
      const selected = new Set(current.toolNames)
      if (selected.has(toolId)) selected.delete(toolId)
      else selected.add(toolId)
      return {
        ...current,
        toolNames: Array.from(selected).sort()
      }
    })
  }

  const setTierTools = (tools: ToolSummary[], enabled: boolean) => {
    setForm(current => {
      const selected = new Set(current.toolNames)
      for (const tool of tools) {
        if (enabled) selected.add(tool.id)
        else selected.delete(tool.id)
      }
      return {
        ...current,
        toolNames: Array.from(selected).sort()
      }
    })
  }

  return {
    catalogTools,
    toolsLoading,
    toolQuery,
    setToolQuery,
    coreTools,
    extraTools,
    toggleTool,
    setTierTools
  }
}
