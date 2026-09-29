import type {
  AgentSession,
  SessionGroup,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'

import {
  assertNever,
  buildStripItemSources,
  getStripItemKind,
  matchStripItem,
  resolveStripItem,
  type StripItem,
  type StripItemKind
} from './strip-item'

/**
 * FAS-107 X5.3 · Tests de invariantes de convivencia para StripItem.
 *
 * Property-based con fast-check: en vez de casos individuales, valida
 * propiedades matemáticas del sistema sobre miles de combinaciones
 * generadas al azar. Esto cierra la clase de bugs que hoy tuvimos que
 * cazar uno por uno.
 *
 * Invariantes probadas:
 *
 * 1. **Resolver total**: para cualquier id que existe en alguna
 *    fuente, `resolveStripItem` retorna el kind correcto.
 * 2. **Resolver silencioso**: para cualquier id que NO existe en
 *    ninguna fuente, retorna null (nunca throw, nunca undefined).
 * 3. **Exhaustive kind coverage**: `matchStripItem` cubre los 3 kinds
 *    (verificado por TypeScript en compile time + runtime con
 *    property test).
 * 4. **`assertNever` throws siempre**: garantiza que si alguien pasa
 *    algo que TS no capturó, explota loud instead of silent.
 * 5. **`getStripItemKind` es consistente con `resolveStripItem`**.
 */

// Arbitraries: generadores para fast-check.

const arbSession: fc.Arbitrary<AgentSession> = fc
  .record({
    id: fc.string({ minLength: 1 }).map(s => `chat_${s}`),
    title: fc.string(),
    projectId: fc.option(fc.string({ minLength: 1 }), { nil: null }),
    status: fc.constant('idle' as const)
  })
  .map(rec => rec as unknown as AgentSession)

const arbTerminal: fc.Arbitrary<TerminalSession> = fc
  .record({
    id: fc.string({ minLength: 1 }).map(s => `term_${s}`),
    title: fc.string(),
    projectId: fc.option(fc.string({ minLength: 1 }), { nil: null })
  })
  .map(rec => rec as unknown as TerminalSession)

const arbGroup: fc.Arbitrary<SessionGroup> = fc
  .record({
    id: fc.string({ minLength: 1 }).map(s => `grp_${s}`),
    name: fc.string(),
    color: fc.constant(null),
    pinned: fc.boolean(),
    itemIds: fc.array(fc.string()),
    activeChatId: fc.string()
  })
  .map(rec => rec as unknown as SessionGroup)

describe('StripItem · invariantes de convivencia', () => {
  describe('resolveStripItem', () => {
    it('total: siempre retorna el kind correcto para chats existentes', () => {
      fc.assert(
        fc.property(fc.array(arbSession, { minLength: 1 }), sessions => {
          const target = sessions[0]
          const sources = buildStripItemSources({
            sessions,
            terminals: [],
            tabGroups: []
          })
          const resolved = resolveStripItem(target.id, sources)
          expect(resolved?.kind).toBe('chat')
          expect(resolved?.id).toBe(target.id)
        })
      )
    })

    it('total: siempre retorna el kind correcto para terminales existentes', () => {
      fc.assert(
        fc.property(fc.array(arbTerminal, { minLength: 1 }), terminals => {
          const target = terminals[0]
          const sources = buildStripItemSources({
            sessions: [],
            terminals,
            tabGroups: []
          })
          const resolved = resolveStripItem(target.id, sources)
          expect(resolved?.kind).toBe('terminal')
          expect(resolved?.id).toBe(target.id)
        })
      )
    })

    it('total: siempre retorna el kind correcto para grupos existentes', () => {
      fc.assert(
        fc.property(fc.array(arbGroup, { minLength: 1 }), tabGroups => {
          const target = tabGroups[0]
          const sources = buildStripItemSources({
            sessions: [],
            terminals: [],
            tabGroups
          })
          const resolved = resolveStripItem(target.id, sources)
          expect(resolved?.kind).toBe('group')
          expect(resolved?.id).toBe(target.id)
        })
      )
    })

    it('silencioso: retorna null para ids inexistentes (nunca throw)', () => {
      fc.assert(
        fc.property(fc.string({ minLength: 1 }), id => {
          const sources = buildStripItemSources({
            sessions: [],
            terminals: [],
            tabGroups: []
          })
          expect(() => resolveStripItem(id, sources)).not.toThrow()
          expect(resolveStripItem(id, sources)).toBeNull()
        })
      )
    })

    it('prioriza grupo sobre terminal y chat cuando el id colisiona', () => {
      // Caso patológico: el mismo id existe en dos fuentes.
      const id = 'collision_id'
      const session = { id, title: 'chat' } as unknown as AgentSession
      const terminal = { id, title: 'term' } as unknown as TerminalSession
      const group = {
        id,
        name: 'grp',
        itemIds: []
      } as unknown as SessionGroup
      const sources = buildStripItemSources({
        sessions: [session],
        terminals: [terminal],
        tabGroups: [group]
      })
      expect(resolveStripItem(id, sources)?.kind).toBe('group')
    })

    it('nunca hace switch por prefijo — un `term_*` en sessions se resuelve como chat', () => {
      // Regla clave: el prefijo del id es solo debug. La fuente decide
      // el kind. Si algún día el backend devuelve un id con prefijo
      // "erróneo", el resolver sigue funcionando.
      const paradox = {
        id: 'term_pero_es_chat',
        title: 'chat de prefijo raro'
      } as unknown as AgentSession
      const sources = buildStripItemSources({
        sessions: [paradox],
        terminals: [],
        tabGroups: []
      })
      expect(resolveStripItem(paradox.id, sources)?.kind).toBe('chat')
    })
  })

  describe('getStripItemKind', () => {
    it('siempre consistente con resolveStripItem', () => {
      fc.assert(
        fc.property(
          fc.array(arbSession),
          fc.array(arbTerminal),
          fc.array(arbGroup),
          fc.string({ minLength: 1 }),
          (sessions, terminals, tabGroups, id) => {
            const sources = buildStripItemSources({
              sessions,
              terminals,
              tabGroups
            })
            const kind = getStripItemKind(id, sources)
            const resolved = resolveStripItem(id, sources)
            expect(kind).toBe(resolved?.kind ?? null)
          }
        )
      )
    })
  })

  describe('matchStripItem', () => {
    it('cubre los 3 kinds sin fallar', () => {
      const chat: StripItem = {
        kind: 'chat',
        id: 'chat_1',
        session: {} as unknown as AgentSession
      }
      const terminal: StripItem = {
        kind: 'terminal',
        id: 'term_1',
        terminal: {} as unknown as TerminalSession
      }
      const group: StripItem = {
        kind: 'group',
        id: 'grp_1',
        group: {} as unknown as SessionGroup
      }

      const handlers = {
        chat: () => 'chat_result',
        terminal: () => 'terminal_result',
        group: () => 'group_result'
      }

      expect(matchStripItem(chat, handlers)).toBe('chat_result')
      expect(matchStripItem(terminal, handlers)).toBe('terminal_result')
      expect(matchStripItem(group, handlers)).toBe('group_result')
    })

    it('narrowea correctamente el tipo específico dentro del handler', () => {
      const chat: StripItem = {
        kind: 'chat',
        id: 'chat_1',
        session: { title: 'hello' } as unknown as AgentSession
      }

      const title = matchStripItem(chat, {
        chat: session => session.title,
        terminal: t => t.title,
        group: g => g.name
      })

      expect(title).toBe('hello')
    })
  })

  describe('assertNever', () => {
    it('siempre throws con contenido del valor inesperado', () => {
      expect(() =>
        assertNever({ kind: 'nueva_variante_no_manejada' } as never)
      ).toThrow(/unhandled discriminated union case/)
    })

    it('el mensaje incluye la data (para debug)', () => {
      try {
        assertNever({ kind: 'foo', extra: 42 } as never)
      } catch (err) {
        expect((err as Error).message).toContain('foo')
        expect((err as Error).message).toContain('42')
      }
    })
  })

  describe('exhaustividad estática (compile-time)', () => {
    it('typecheck-driven: todo consumer que use `matchStripItem` maneja los 3 kinds', () => {
      // Este test es "trivial" en runtime pero su verdadero valor está
      // en compile time: si alguien agrega un `kind` al union y no
      // actualiza matchStripItem, TypeScript rompe el build.
      const kinds: StripItemKind[] = ['chat', 'terminal', 'group']
      const handlers = {
        chat: () => 'chat',
        terminal: () => 'terminal',
        group: () => 'group'
      }

      for (const kind of kinds) {
        expect(handlers[kind]).toBeDefined()
      }
    })
  })
})
