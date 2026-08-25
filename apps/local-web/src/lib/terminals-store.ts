import type { TerminalSession } from '@sandwalk/agent-ui-core'

/**
 * FAS-107 X3 Fase 1 · Store singleton para terminales.
 *
 * Fuente única de verdad para "qué terminales existen" en la UI. Antes
 * teníamos dos instancias de `useAppTerminals` (App.tsx y
 * AgentSessionMainPanel) con state local independiente — la optimistic
 * insert que hacía el picker del split iba a una copia, mientras que el
 * `TerminalHostsProvider` leía de la otra → el xterm nunca se montaba
 * (terminal vacío).
 *
 * Este store centraliza los `terminals`, `loading` y `error`, y expone
 * setters que cualquier consumidor puede llamar. Los componentes se
 * suscriben con `useSyncExternalStore` (React 18 nativo).
 *
 * Filtrado por proyecto: el store guarda TODOS los terminales de la
 * lista fetcheada. Un fetch scoped a proyecto reemplaza la lista. Los
 * consumidores no filtran acá — cada superficie decide qué mostrar.
 */

type TerminalsState = {
  terminals: TerminalSession[]
  loading: boolean
  error: string | null
}

const state: TerminalsState = {
  terminals: [],
  loading: false,
  error: null
}

const listeners = new Set<() => void>()

function emit() {
  for (const l of listeners) l()
}

export function subscribeTerminalsStore(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function getTerminalsSnapshot(): TerminalsState {
  return state
}

export function setTerminalsAll(next: TerminalSession[]) {
  if (state.terminals === next) return
  state.terminals = next
  emit()
}

export function setTerminalsLoading(next: boolean) {
  if (state.loading === next) return
  state.loading = next
  emit()
}

export function setTerminalsError(next: string | null) {
  if (state.error === next) return
  state.error = next
  emit()
}

/**
 * Optimistic insert. Idempotente por id — si ya existe, no duplica.
 * Se usa justo después de `client.createTerminal(...)` para que el
 * `TerminalHostsProvider` monte el xterm antes de que el fetch scoped
 * al proyecto complete.
 */
export function addTerminalOptimistic(term: TerminalSession) {
  const existing = state.terminals.find(t => t.id === term.id)
  if (existing) return
  state.terminals = [term, ...state.terminals]
  emit()
}

/** Remove por id. Idempotente. */
export function removeTerminal(terminalId: string) {
  const next = state.terminals.filter(t => t.id !== terminalId)
  if (next.length === state.terminals.length) return
  state.terminals = next
  emit()
}

/** Patch parcial de un terminal por id. Si no existe, no-op. */
export function patchTerminal(
  terminalId: string,
  changes: Partial<TerminalSession>
) {
  let mutated = false
  const next = state.terminals.map(t => {
    if (t.id !== terminalId) return t
    mutated = true
    return { ...t, ...changes }
  })
  if (!mutated) return
  state.terminals = next
  emit()
}
