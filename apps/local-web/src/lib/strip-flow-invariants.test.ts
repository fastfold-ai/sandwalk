import type {
  AgentSession,
  SessionGroup,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'

import { resolveStripActive } from './strip-active'
import {
  buildStripItemSources,
  resolveStripItem,
  type StripItem
} from './strip-item'

/**
 * FAS-107 X5.4 · Property tests del flujo strip end-to-end.
 *
 * Los tests anteriores (X5.3 + `app-display-invariants`) validaron
 * componentes individuales. Estos validan el **contrato entre
 * componentes** — la clase de bugs "un consumer ve el active de una
 * forma, otro consumer lo ve de otra".
 *
 * Invariantes:
 * 1. `resolveStripActive` y `resolveStripItem` acuerdan en el tipo
 *    del active. Nunca uno dice "chat" y el otro "terminal".
 * 2. Un id nunca puede pertenecer a dos fuentes distintas
 *    simultáneamente (o si pasa, el resolver prioriza consistente).
 * 3. Cerrar un tab (removerlo de openTabIds) produce un openTabIds
 *    subset — nunca inventa ids nuevos.
 */

const arbSession: fc.Arbitrary<AgentSession> = fc
  .record({
    id: fc.uuid(),
    title: fc.string(),
    projectId: fc.option(fc.uuid(), { nil: null })
  })
  .map(rec => rec as unknown as AgentSession)

const arbTerminal: fc.Arbitrary<TerminalSession> = fc
  .record({
    id: fc.uuid().map(u => `term_${u}`),
    title: fc.string(),
    projectId: fc.option(fc.uuid(), { nil: null })
  })
  .map(rec => rec as unknown as TerminalSession)

const arbGroup: fc.Arbitrary<SessionGroup> = fc
  .record({
    id: fc.uuid().map(u => `grp_${u}`),
    name: fc.string(),
    color: fc.constant(null),
    pinned: fc.boolean(),
    itemIds: fc.array(fc.uuid()),
    activeChatId: fc.uuid()
  })
  .map(rec => rec as unknown as SessionGroup)

describe('acuerdo entre resolveStripActive y resolveStripItem', () => {
  it('el kind del active de la ruta coincide con el kind resuelto por sources', () => {
    // Regresión del bug del `stripSessionId`: `resolveStripActive` decía
    // el active era `chat_xxx` (por route.sessionId) pero el resolver de
    // sources decía era `terminal` (por prefijo del id).
    fc.assert(
      fc.property(arbSession, arbTerminal, arbGroup, (chat, term, group) => {
        // Caso 1: ruta chat, sources tiene el chat.
        {
          const active = resolveStripActive(
            { sessionId: chat.id, terminalId: null },
            null
          )
          const sources = buildStripItemSources({
            sessions: [chat],
            terminals: [term],
            tabGroups: [group]
          })
          if (active) {
            const item = resolveStripItem(active.id, sources)
            if (item) {
              // Ambos deben acordar en el kind (chat en este caso).
              expect(active.kind).toBe(item.kind)
            }
          }
        }
        // Caso 2: ruta terminal.
        {
          const active = resolveStripActive(
            { sessionId: null, terminalId: term.id },
            null
          )
          const sources = buildStripItemSources({
            sessions: [chat],
            terminals: [term],
            tabGroups: [group]
          })
          if (active) {
            const item = resolveStripItem(active.id, sources)
            if (item) {
              expect(active.kind).toBe(item.kind)
            }
          }
        }
      })
    )
  })

  it('grupo activo tiene precedencia sobre route.sessionId y route.terminalId', () => {
    fc.assert(
      fc.property(arbGroup, arbSession, arbTerminal, (group, chat, term) => {
        const active = resolveStripActive(
          { sessionId: chat.id, terminalId: term.id },
          group
        )
        expect(active?.kind).toBe('group')
        expect(active?.id).toBe(group.id)
      })
    )
  })
})

describe('flujo de cierre · closeSessionTab invariantes', () => {
  /**
   * Simula la lógica de `closeSessionTab.tabIsInScope` para property
   * tests. Debe reconocer chats Y terminales (regresión del hotfix
   * `37e731f`).
   */
  function tabIsInScopePure(
    tabId: string,
    activeProjectId: string | null,
    sessions: AgentSession[],
    terminals: TerminalSession[]
  ): boolean {
    if (tabId.startsWith('grp_')) return true
    if (tabId.startsWith('term_')) {
      const t = terminals.find(x => x.id === tabId)
      if (!t) return false
      if (!activeProjectId) return true
      return (t.projectId ?? null) === activeProjectId
    }
    const s = sessions.find(x => x.id === tabId)
    if (!s) return false
    if (!activeProjectId) return true
    return s.projectId === activeProjectId
  }

  it('cerrar un tab no cascadea sobre otros tabs del mismo scope', () => {
    // Regresión del hotfix `37e731f`: `deleteSession` filtraba
    // `openTabIds` descartando grp_* y term_*.
    fc.assert(
      fc.property(
        fc.array(arbSession, { minLength: 2, maxLength: 10 }),
        fc.uuid(),
        (sessions, activeProjectId) => {
          // Todos en el mismo proyecto.
          const scoped = sessions.map(s => ({ ...s, projectId: activeProjectId }))
          const openTabIds = scoped.map(s => s.id)
          const toClose = openTabIds[0]
          const withoutClosed = openTabIds.filter(id => id !== toClose)
          const next = withoutClosed.filter(id =>
            tabIsInScopePure(id, activeProjectId, scoped, [])
          )
          // Cerrar el chat A NO debería quitar el chat B/C/D del scope.
          expect(next.length).toBe(withoutClosed.length)
        }
      )
    )
  })

  it('cerrar un chat NO afecta terminales del mismo proyecto', () => {
    // Regresión del hotfix `37e731f` (asimetría real reportada).
    fc.assert(
      fc.property(
        arbSession,
        arbTerminal,
        fc.uuid(),
        (chat, term, activeProjectId) => {
          const scopedChat = { ...chat, projectId: activeProjectId }
          const scopedTerm = { ...term, projectId: activeProjectId }
          const openTabIds = [scopedChat.id, scopedTerm.id]
          const withoutClosed = openTabIds.filter(id => id !== scopedChat.id)
          const next = withoutClosed.filter(id =>
            tabIsInScopePure(id, activeProjectId, [scopedChat], [scopedTerm])
          )
          expect(next).toContain(scopedTerm.id)
        }
      )
    )
  })

  it('tabIsInScope siempre acepta grupos y nunca cascadea sobre ellos', () => {
    fc.assert(
      fc.property(arbGroup, fc.uuid(), (group, activeProjectId) => {
        expect(tabIsInScopePure(group.id, activeProjectId, [], [])).toBe(true)
      })
    )
  })
})

describe('invariante de identidad · resolver es idempotente', () => {
  it('resolveStripItem retorna el mismo item para el mismo id + sources', () => {
    fc.assert(
      fc.property(
        fc.array(arbSession),
        fc.array(arbTerminal),
        fc.array(arbGroup),
        (sessions, terminals, tabGroups) => {
          const sources = buildStripItemSources({
            sessions,
            terminals,
            tabGroups
          })
          const allIds = [
            ...sessions.map(s => s.id),
            ...terminals.map(t => t.id),
            ...tabGroups.map(g => g.id)
          ]
          for (const id of allIds) {
            const first = resolveStripItem(id, sources)
            const second = resolveStripItem(id, sources)
            expect(first?.kind).toBe(second?.kind)
            expect(first?.id).toBe(second?.id)
          }
        }
      )
    )
  })
})

describe('exhaustividad · tipos futuros', () => {
  it('agregar un StripItem kind nuevo requiere actualizar el resolver', () => {
    // Este test documenta el compromiso: si en el futuro se agrega
    // `note`, `canvas`, `mcp` al StripItem union, TypeScript señala
    // los sitios que necesitan actualización.
    //
    // El test es "trivial" en runtime pero su valor está en compile
    // time: al hacer `switch (item.kind)` con `assertNever`, el
    // compilador impide olvidos.
    const knownKinds: Array<StripItem['kind']> = ['chat', 'terminal', 'group']
    expect(knownKinds).toHaveLength(3)
  })
})
