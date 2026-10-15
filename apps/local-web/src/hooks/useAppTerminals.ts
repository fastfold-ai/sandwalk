import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useCallback, useEffect } from 'react'

import { useTerminalsStore } from '@/lib/terminals-store'

/**
 * FAS-107 X4.0 · Fachada del store singleton Zustand.
 *
 * Este hook YA NO mantiene state local — es una fachada del
 * `useTerminalsStore` (Zustand). Cualquier consumidor lee la misma
 * lista, y las mutaciones optimistas se propagan a todo el árbol al
 * instante por diseño del store.
 *
 * Antes teníamos dos instancias de este hook con `useState` local
 * → optimistic insert en una copia no llegaba a la otra →
 * `TerminalHostsProvider` no montaba xterm para el terminal recién
 * creado (bug crítico X3).
 *
 * API pública sin cambios: `{ terminals, loading, error, refresh,
 * addOptimistic, removeOptimistic }`. Los consumidores existentes no
 * necesitan modificaciones.
 *
 * NOTA: el `useEffect` de fetch inicial se dispara por cada instancia
 * del hook. En un futuro (X4.2) el `TerminalService` monta el fetch
 * una sola vez a nivel de app; por ahora el fetch múltiple es
 * inofensivo porque el store es único (los `setAll` idempotentes
 * cortan el re-render si la referencia es la misma).
 */
export function useAppTerminals(
  client: LocalAgentClient | null,
  projectId: string | null | undefined
) {
  const terminals = useTerminalsStore(state => state.terminals)
  const loading = useTerminalsStore(state => state.loading)
  const error = useTerminalsStore(state => state.error)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!client) return
      const { setAll, setLoading, setError, revision } = useTerminalsStore.getState()
      setLoading(true)
      setError(null)
      try {
        const rows = await client.listTerminals({
          projectId: projectId ?? null,
          signal
        })
        // `revision` is from before the request. A create/delete in between
        // bumps it, and applying this older list would unmount the new shell.
        if (!signal?.aborted) setAll(rows, revision)
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

  const addOptimistic = useCallback(
    useTerminalsStore.getState().addOptimistic,
    []
  )
  const removeOptimistic = useCallback(useTerminalsStore.getState().remove, [])

  return {
    terminals,
    loading,
    error,
    refresh,
    addOptimistic,
    removeOptimistic
  }
}
