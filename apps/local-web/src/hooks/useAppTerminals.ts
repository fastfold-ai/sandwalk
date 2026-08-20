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

  /**
   * Optimistic insert used right after `client.createTerminal(...)` so
   * the renderer can detect the id as a terminal (and pick TerminalLeaf
   * instead of ChatLeaf) BEFORE the background `refresh()` fetch lands.
   */
  const addOptimistic = useCallback((term: TerminalSession) => {
    setTerminals(prev => {
      if (prev.some(t => t.id === term.id)) return prev
      return [term, ...prev]
    })
  }, [])

  const removeOptimistic = useCallback((terminalId: string) => {
    setTerminals(prev => prev.filter(t => t.id !== terminalId))
  }, [])

  return { terminals, loading, error, refresh, addOptimistic, removeOptimistic }
}
