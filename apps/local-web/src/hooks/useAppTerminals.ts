import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { TerminalSession } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useState } from 'react'

/**
 * Fetch and cache terminals for a project (FAS-107).
 *
 * Peer of the sessions loader — the sidebar and split picker call this
 * to enumerate terminals alongside chats. Refetches on `projectId`
 * change and exposes a manual `refresh()` for post-mutation reloads.
 */
export function useAppTerminals(
  client: LocalAgentClient | null,
  projectId: string | null | undefined
) {
  const [terminals, setTerminals] = useState<TerminalSession[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!client) return
      setLoading(true)
      setError(null)
      try {
        const rows = await client.listTerminals({
          projectId: projectId ?? null,
          signal
        })
        if (!signal?.aborted) setTerminals(rows)
      } catch (err) {
        if (signal?.aborted) return
        setError((err as Error).message)
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [client, projectId]
  )

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const refresh = useCallback(() => {
    void load()
  }, [load])

  return { terminals, loading, error, refresh }
}
