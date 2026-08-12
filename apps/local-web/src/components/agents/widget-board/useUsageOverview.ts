import type { UsageOverview } from '@sandwalk/agent-ui-core'
import { useEffect, useState } from 'react'

import {
  readUsageOverviewCache,
  writeUsageOverviewCache
} from '@/lib/usage-overview-cache'

type UsageClient = {
  baseUrl?: string
  getUsageOverview?: (
    signalOrOpts?:
      | AbortSignal
      | { projectId?: string | null; signal?: AbortSignal }
  ) => Promise<UsageOverview>
}

export function useUsageOverview(
  client: UsageClient | null | undefined,
  projectId?: string | null
) {
  const cacheKey = client?.baseUrl || 'default'
  const scopeId = projectId?.trim() || null
  const [overview, setOverview] = useState<UsageOverview | null>(() =>
    readUsageOverviewCache(cacheKey, scopeId)
  )
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    if (!client?.getUsageOverview) return
    const warm = readUsageOverviewCache(cacheKey, scopeId)
    if (warm && reloadToken === 0) setOverview(warm)
    const controller = new AbortController()
    void client
      .getUsageOverview({ projectId: scopeId, signal: controller.signal })
      .then(next => {
        writeUsageOverviewCache(cacheKey, next, scopeId)
        setOverview(next)
        setError(null)
      })
      .catch(err => {
        if (controller.signal.aborted) return
        if (!warm && !readUsageOverviewCache(cacheKey, scopeId)) {
          setError(err instanceof Error ? err.message : 'Failed to load usage')
        }
      })
    return () => controller.abort()
  }, [cacheKey, client, reloadToken, scopeId])

  return {
    overview,
    error,
    reload: () => setReloadToken(token => token + 1)
  }
}
