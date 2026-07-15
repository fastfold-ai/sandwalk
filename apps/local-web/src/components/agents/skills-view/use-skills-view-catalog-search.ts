import type { AgentCatalogSkill } from '@sandwalk/agent-ui-core'
import { useEffect, useState } from 'react'

export function useSkillsViewCatalogSearch({
  catalogSearchMode,
  query,
  onSearchCatalog
}: {
  catalogSearchMode: boolean
  query: string
  onSearchCatalog: (
    query: string,
    signal?: AbortSignal
  ) => Promise<AgentCatalogSkill[]>
}) {
  const [catalogResults, setCatalogResults] = useState<AgentCatalogSkill[]>([])
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogError, setCatalogError] = useState<string | null>(null)

  useEffect(() => {
    if (!catalogSearchMode) {
      setCatalogResults([])
      setCatalogError(null)
      setCatalogLoading(false)
      return
    }
    const text = query.trim()
    if (text.length < 2) {
      setCatalogResults([])
      setCatalogError(null)
      setCatalogLoading(false)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setCatalogLoading(true)
      setCatalogError(null)
      void onSearchCatalog(text, controller.signal)
        .then(items => {
          if (!controller.signal.aborted) setCatalogResults(items)
        })
        .catch(error => {
          if (controller.signal.aborted) return
          setCatalogResults([])
          setCatalogError(
            error instanceof Error ? error.message : 'Unable to search skills.sh.'
          )
        })
        .finally(() => {
          if (!controller.signal.aborted) setCatalogLoading(false)
        })
    }, 220)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [catalogSearchMode, onSearchCatalog, query])

  return {
    catalogResults,
    catalogLoading,
    catalogError,
    setCatalogResults,
    setCatalogError
  }
}
