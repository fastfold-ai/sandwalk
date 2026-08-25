import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useCallback, useEffect, useSyncExternalStore } from 'react'

import {
  addTerminalOptimistic as storeAddOptimistic,
  getTerminalsSnapshot,
  removeTerminal as storeRemove,
  setTerminalsAll,
  setTerminalsError,
  setTerminalsLoading,
  subscribeTerminalsStore
} from '@/lib/terminals-store'

/**
 * FAS-107 X3 Fase 1 · Fetch + cache de terminales para el scope activo.
 *
 * Este hook ya NO mantiene state local — es un wrapper del store
 * singleton (`terminals-store.ts`). Cualquier consumidor lee la misma
 * lista, y las mutaciones optimistas se propagan a todo el árbol al
 * instante.
 *
 * Antes teníamos dos instancias de este hook (App.tsx y
 * AgentSessionMainPanel) con state local independiente → optimistic
 * insert en una copia no llegaba a la otra → `TerminalHostsProvider`
 * no montaba xterm para el terminal recién creado.
 *
 * API pública sin cambios: `{ terminals, loading, error, refresh,
 * addOptimistic, removeOptimistic }`. Los consumidores existentes no
 * necesitan modificaciones.
 */
export function useAppTerminals(
  client: LocalAgentClient | null,
  projectId: string | null | undefined
) {
  const snapshot = useSyncExternalStore(
    subscribeTerminalsStore,
    getTerminalsSnapshot
  )

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!client) return
      setTerminalsLoading(true)
      setTerminalsError(null)
      try {
        const rows = await client.listTerminals({
          projectId: projectId ?? null,
          signal
        })
        if (!signal?.aborted) setTerminalsAll(rows)
      } catch (err) {
        if (signal?.aborted) return
        setTerminalsError((err as Error).message)
      } finally {
        if (!signal?.aborted) setTerminalsLoading(false)
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

  // Wrappers de compat con la API previa. Delegan al store.
  const addOptimistic = useCallback(storeAddOptimistic, [])
  const removeOptimistic = useCallback(storeRemove, [])

  return {
    terminals: snapshot.terminals,
    loading: snapshot.loading,
    error: snapshot.error,
    refresh,
    addOptimistic,
    removeOptimistic
  }
}
