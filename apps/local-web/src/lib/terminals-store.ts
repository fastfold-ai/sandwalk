import type { TerminalSession } from '@sandwalk/agent-ui-core'
import { create } from 'zustand'

/**
 * FAS-107 X4.0 · Store singleton para terminales (Zustand).
 *
 * Fuente única de verdad para "qué terminales existen" en la UI y
 * qué campos tiene cada uno.
 *
 * Contexto del rediseño (ver docs §9):
 *
 * X3 Fase 1 intentó armar este store a mano con `useSyncExternalStore`.
 * El bug: `getTerminalsSnapshot()` devolvía siempre la misma referencia
 * porque el objeto se mutaba en el sitio. React compara referencias con
 * `Object.is` — si la referencia no cambia, no re-renderea. Explica
 * directamente el "X del chip no cierra hasta que cambio de tab".
 *
 * X4.0 reemplaza el patrón por Zustand. Cada action genera un objeto
 * de state nuevo (patrón inmutable), y los suscriptores se enteran por
 * diseño. Selectores atómicos (una prop por hook) evitan re-renders
 * innecesarios sin necesidad de `useShallow` para el caso simple.
 *
 * Referente arquitectónico: Wave Terminal block system con `ViewModel`
 * reactivo por bloque (sustituyendo Jotai por Zustand).
 *
 * API pública:
 *
 *   // Suscripción reactiva (selectores atómicos)
 *   const terminals = useTerminalsStore(state => state.terminals)
 *   const terminal  = useTerminalsStore(state =>
 *     state.terminals.find(t => t.id === id) ?? null
 *   )
 *
 *   // Acceso imperativo (sin suscripción — para uso en callbacks)
 *   useTerminalsStore.getState().terminals
 *
 *   // Acciones (todas idempotentes)
 *   useTerminalsStore.getState().setAll(list)
 *   useTerminalsStore.getState().addOptimistic(term)
 *   useTerminalsStore.getState().patch(id, {title: 'New name'})
 *   useTerminalsStore.getState().remove(id)
 */

type TerminalsState = {
  terminals: TerminalSession[]
  loading: boolean
  error: string | null

  /** Reemplaza toda la lista. Se llama después de `listTerminals` del backend. */
  setAll: (next: TerminalSession[]) => void

  /** Marca inicio/fin de un fetch al backend. */
  setLoading: (next: boolean) => void

  /** Guarda el mensaje de error del último fetch fallido. */
  setError: (next: string | null) => void

  /**
   * Insert optimista. Idempotente por id: si ya existe, no duplica.
   * Se usa justo después de `client.createTerminal(...)` para que el
   * `TerminalHostsProvider` monte el xterm antes de que el fetch
   * scoped al proyecto complete.
   */
  addOptimistic: (term: TerminalSession) => void

  /** Remove por id. Idempotente. */
  remove: (terminalId: string) => void

  /** Patch parcial de un terminal por id. Si no existe, no-op. */
  patch: (terminalId: string, changes: Partial<TerminalSession>) => void
}

export const useTerminalsStore = create<TerminalsState>()(set => ({
  terminals: [],
  loading: false,
  error: null,

  setAll: next =>
    set(state => (state.terminals === next ? state : { terminals: next })),

  setLoading: next =>
    set(state => (state.loading === next ? state : { loading: next })),

  setError: next =>
    set(state => (state.error === next ? state : { error: next })),

  addOptimistic: term =>
    set(state => {
      if (state.terminals.some(t => t.id === term.id)) return state
      return { terminals: [term, ...state.terminals] }
    }),

  remove: terminalId =>
    set(state => {
      const next = state.terminals.filter(t => t.id !== terminalId)
      if (next.length === state.terminals.length) return state
      return { terminals: next }
    }),

  patch: (terminalId, changes) =>
    set(state => {
      let mutated = false
      const next = state.terminals.map(t => {
        if (t.id !== terminalId) return t
        mutated = true
        return { ...t, ...changes }
      })
      if (!mutated) return state
      return { terminals: next }
    })
}))
