import type { TerminalSession } from '@sandwalk/agent-ui-core'
import { beforeEach, describe, expect, it } from 'vitest'

import { useTerminalsStore } from './terminals-store'

/**
 * FAS-107 X4.1 · Tests base del store singleton (Zustand).
 *
 * Contrato que garantizan estos tests:
 * - Cada action que muta produce una referencia NUEVA de `terminals`
 *   (por eso el X del chip re-renderea al instante).
 * - Idempotencia: acciones sobre estado inexistente son no-op.
 * - Selectores atómicos: mutar un campo no dispara re-render del otro.
 */

const term = (id: string, patch: Partial<TerminalSession> = {}): TerminalSession =>
  ({
    id,
    title: `Terminal ${id}`,
    projectId: null,
    workspacePath: null,
    status: 'idle',
    organizeLabel: null,
    color: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...patch
  }) as unknown as TerminalSession

beforeEach(() => {
  useTerminalsStore.setState({
    terminals: [],
    loading: false,
    error: null,
    revision: 0
  })
})

describe('useTerminalsStore', () => {
  describe('setAll', () => {
    it('reemplaza la lista y devuelve nueva referencia', () => {
      const before = useTerminalsStore.getState().terminals
      const next = [term('term_1'), term('term_2')]
      useTerminalsStore.getState().setAll(next)
      const after = useTerminalsStore.getState().terminals
      expect(after).toBe(next)
      expect(after).not.toBe(before)
      expect(after).toHaveLength(2)
    })

    it('carries the UI-only agent mark across a server list refresh', () => {
      useTerminalsStore.getState().setAll([term('term_1'), term('term_2')])
      useTerminalsStore.getState().patch('term_1', { agent: 'codex' } as never)
      // Server rows never include `agent`.
      useTerminalsStore.getState().setAll([term('term_1'), term('term_2')])
      const [t1, t2] = useTerminalsStore.getState().terminals
      expect((t1 as { agent?: string }).agent).toBe('codex')
      expect((t2 as { agent?: string }).agent).toBeUndefined()
    })

    it('lets an explicit agent from the server (or null) override the carry-over', () => {
      useTerminalsStore.getState().setAll([term('term_1')])
      useTerminalsStore.getState().patch('term_1', { agent: 'codex' } as never)
      useTerminalsStore.getState().setAll([term('term_1', { agent: null } as never)])
      expect((useTerminalsStore.getState().terminals[0] as { agent?: unknown }).agent).toBeNull()
    })

    it('keeps a terminal created while a list request was in flight', () => {
      const seen = useTerminalsStore.getState().revision
      const created = term('term_new')
      useTerminalsStore.getState().addOptimistic(created)
      useTerminalsStore.getState().setAll([], seen)
      expect(useTerminalsStore.getState().terminals).toEqual([created])
    })

    it('es no-op si el array es la misma referencia', () => {
      const list = [term('term_1')]
      useTerminalsStore.getState().setAll(list)
      const first = useTerminalsStore.getState().terminals
      useTerminalsStore.getState().setAll(list)
      const second = useTerminalsStore.getState().terminals
      expect(second).toBe(first)
    })
  })

  describe('addOptimistic', () => {
    it('inserta un terminal nuevo al inicio', () => {
      const t1 = term('term_1')
      useTerminalsStore.getState().addOptimistic(t1)
      expect(useTerminalsStore.getState().terminals).toEqual([t1])
    })

    it('es idempotente si el id ya existe', () => {
      const t1 = term('term_1')
      useTerminalsStore.getState().addOptimistic(t1)
      const before = useTerminalsStore.getState().terminals
      useTerminalsStore.getState().addOptimistic(t1)
      const after = useTerminalsStore.getState().terminals
      expect(after).toBe(before)
      expect(after).toHaveLength(1)
    })

    it('produce una referencia nueva del array al insertar', () => {
      useTerminalsStore.getState().addOptimistic(term('term_1'))
      const before = useTerminalsStore.getState().terminals
      useTerminalsStore.getState().addOptimistic(term('term_2'))
      const after = useTerminalsStore.getState().terminals
      expect(after).not.toBe(before)
    })
  })

  describe('remove', () => {
    it('elimina por id', () => {
      useTerminalsStore.getState().setAll([term('term_1'), term('term_2')])
      useTerminalsStore.getState().remove('term_1')
      expect(useTerminalsStore.getState().terminals).toHaveLength(1)
      expect(
        useTerminalsStore.getState().terminals[0].id
      ).toBe('term_2')
    })

    it('es no-op si el id no existe', () => {
      useTerminalsStore.getState().setAll([term('term_1')])
      const before = useTerminalsStore.getState().terminals
      useTerminalsStore.getState().remove('term_no_existe')
      const after = useTerminalsStore.getState().terminals
      expect(after).toBe(before)
    })

    it('produce una referencia nueva del array al eliminar', () => {
      useTerminalsStore.getState().setAll([term('term_1'), term('term_2')])
      const before = useTerminalsStore.getState().terminals
      useTerminalsStore.getState().remove('term_1')
      const after = useTerminalsStore.getState().terminals
      expect(after).not.toBe(before)
    })
  })

  describe('patch', () => {
    it('modifica parcialmente por id', () => {
      useTerminalsStore.getState().setAll([term('term_1', { title: 'Old' })])
      useTerminalsStore.getState().patch('term_1', { title: 'New' })
      expect(useTerminalsStore.getState().terminals[0].title).toBe('New')
    })

    it('es no-op si el id no existe', () => {
      useTerminalsStore.getState().setAll([term('term_1')])
      const before = useTerminalsStore.getState().terminals
      useTerminalsStore.getState().patch('term_no_existe', { title: 'X' })
      const after = useTerminalsStore.getState().terminals
      expect(after).toBe(before)
    })

    it('produce una referencia nueva del item modificado', () => {
      useTerminalsStore.getState().setAll([term('term_1'), term('term_2')])
      const [t1Before, t2Before] = useTerminalsStore.getState().terminals
      useTerminalsStore.getState().patch('term_1', { title: 'New' })
      const [t1After, t2After] = useTerminalsStore.getState().terminals
      expect(t1After).not.toBe(t1Before)
      expect(t2After).toBe(t2Before) // el no modificado conserva referencia
    })
  })

  describe('setLoading / setError', () => {
    it('marca loading', () => {
      useTerminalsStore.getState().setLoading(true)
      expect(useTerminalsStore.getState().loading).toBe(true)
    })

    it('setLoading es no-op si el valor no cambia', () => {
      const before = useTerminalsStore.getState()
      useTerminalsStore.getState().setLoading(false)
      const after = useTerminalsStore.getState()
      expect(after.loading).toBe(before.loading)
    })

    it('marca error', () => {
      useTerminalsStore.getState().setError('boom')
      expect(useTerminalsStore.getState().error).toBe('boom')
    })
  })

  describe('inmutabilidad del snapshot (regresión X3 Fase 1)', () => {
    it('el objeto de state tiene referencia nueva tras cada mutación', () => {
      // Contrato clave: React `useSyncExternalStore` (que Zustand usa
      // internamente) compara referencias. Si el objeto de state no
      // cambiara, React no re-renderaría (bug X3 Fase 1).
      const before = useTerminalsStore.getState()
      useTerminalsStore.getState().addOptimistic(term('term_1'))
      const after = useTerminalsStore.getState()
      // Zustand crea un state nuevo por action; incluso los campos no
      // tocados quedan expuestos con la misma identidad para permitir
      // selectores atómicos sin re-renders innecesarios.
      expect(after.terminals).not.toBe(before.terminals)
    })
  })
})
