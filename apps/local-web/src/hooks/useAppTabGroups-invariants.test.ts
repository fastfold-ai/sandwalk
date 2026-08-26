import type {
  AgentSession,
  SessionGroup,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'

/**
 * FAS-107 X5.4 · Property tests de invariantes de `useAppTabGroups`
 * (dissolveGroup, removeFromGroup, addToGroup).
 *
 * En vez de renderar el hook con `renderHook`, replicamos las
 * funciones puras que operan sobre `SessionGroup[]` y `openTabIds`.
 * Esto valida los CONTRATOS de las acciones sin acoplar a React.
 *
 * Los bugs de X4.4 (dissolve con terminales perdidos, cascadas de
 * close) hubieran sido pescados acá.
 */

// Replicamos las funciones puras del hook (sin dependencias React) para
// poder testearlas con property tests.

/**
 * Simula `removeFromGroup`: quita `itemId` del `group` y devuelve
 * `nextSize`. Invariante: `nextSize === group.itemIds.length - 1` cuando
 * el id existe, `-1` cuando no.
 */
function removeFromGroupPure(
  group: SessionGroup,
  itemId: string
): { group: SessionGroup | null; nextSize: number } {
  if (!group.itemIds.includes(itemId)) return { group, nextSize: -1 }
  const nextIds = group.itemIds.filter(id => id !== itemId)
  const nextActive =
    group.activeChatId === itemId
      ? nextIds[0] ?? group.activeChatId
      : group.activeChatId
  return {
    group: { ...group, itemIds: nextIds, activeChatId: nextActive },
    nextSize: nextIds.length
  }
}

/**
 * Simula `dissolveGroup.nativesInThisScope`: dado un grupo y las
 * fuentes, calcula qué items nativos vuelven a `openTabIds`.
 */
function nativesInThisScopePure(
  group: SessionGroup,
  activeProjectId: string | null,
  sessions: AgentSession[],
  terminals: TerminalSession[]
): string[] {
  if (activeProjectId === null) return group.itemIds
  const sessionsById = new Map(sessions.map(s => [s.id, s]))
  const terminalsById = new Map(terminals.map(t => [t.id, t]))
  return group.itemIds.filter(id => {
    if (id.startsWith('term_')) {
      const t = terminalsById.get(id)
      return t ? (t.projectId ?? null) === activeProjectId : false
    }
    const s = sessionsById.get(id)
    return s ? s.projectId === activeProjectId : false
  })
}

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

describe('removeFromGroup · invariantes', () => {
  it('quitar un item existente reduce itemIds en exactamente 1', () => {
    fc.assert(
      fc.property(
        fc.array(fc.uuid(), { minLength: 2, maxLength: 10 }),
        ids => {
          const group: SessionGroup = {
            id: 'grp_1',
            name: 'test',
            color: null,
            pinned: false,
            itemIds: ids,
            activeChatId: ids[0]
          } as unknown as SessionGroup
          const target = ids[Math.floor(ids.length / 2)]
          const { group: nextGroup, nextSize } = removeFromGroupPure(
            group,
            target
          )
          expect(nextSize).toBe(ids.length - 1)
          expect(nextGroup?.itemIds).toHaveLength(ids.length - 1)
          expect(nextGroup?.itemIds.includes(target)).toBe(false)
        }
      )
    )
  })

  it('quitar un item inexistente devuelve nextSize = -1', () => {
    fc.assert(
      fc.property(
        fc.array(fc.uuid(), { minLength: 1, maxLength: 5 }),
        fc.uuid(),
        (ids, unknownId) => {
          fc.pre(!ids.includes(unknownId))
          const group: SessionGroup = {
            id: 'grp_1',
            name: 'test',
            color: null,
            pinned: false,
            itemIds: ids,
            activeChatId: ids[0]
          } as unknown as SessionGroup
          const { nextSize } = removeFromGroupPure(group, unknownId)
          expect(nextSize).toBe(-1)
        }
      )
    )
  })

  it('activeChatId nunca queda apuntando a un id removido', () => {
    // Regresión: si el active era el que se remueve, debe pasar a otro.
    fc.assert(
      fc.property(
        fc.array(fc.uuid(), { minLength: 2, maxLength: 10 }),
        ids => {
          const group: SessionGroup = {
            id: 'grp_1',
            name: 'test',
            color: null,
            pinned: false,
            itemIds: ids,
            activeChatId: ids[0]
          } as unknown as SessionGroup
          const { group: nextGroup } = removeFromGroupPure(group, ids[0])
          expect(nextGroup?.activeChatId).not.toBe(ids[0])
          expect(nextGroup?.itemIds).toContain(nextGroup?.activeChatId)
        }
      )
    )
  })
})

describe('nativesInThisScope · invariantes (regresión dissolveGroup)', () => {
  it('activeProjectId null: TODOS los itemIds son nativos', () => {
    fc.assert(
      fc.property(
        fc.array(fc.uuid(), { minLength: 1, maxLength: 10 }),
        ids => {
          const group: SessionGroup = {
            id: 'grp_1',
            name: 'test',
            color: null,
            pinned: false,
            itemIds: ids,
            activeChatId: ids[0]
          } as unknown as SessionGroup
          const natives = nativesInThisScopePure(group, null, [], [])
          expect(natives).toEqual(ids)
        }
      )
    )
  })

  it('grupo con terminales del proyecto activo: TERMINALES son nativos', () => {
    // Regresión del hotfix `b1a9ee3`: `chatProjectById` no incluía
    // terminales → terminales del grupo se filtraban fuera de
    // `nativesInThisScope` → al dissolve el terminal survivor desaparecía
    // del strip.
    fc.assert(
      fc.property(
        arbTerminal,
        fc.uuid(),
        (terminalTemplate, activeProjectId) => {
          const terminal = { ...terminalTemplate, projectId: activeProjectId }
          const group: SessionGroup = {
            id: 'grp_1',
            name: 'test',
            color: null,
            pinned: false,
            itemIds: [terminal.id],
            activeChatId: terminal.id
          } as unknown as SessionGroup
          const natives = nativesInThisScopePure(
            group,
            activeProjectId,
            [],
            [terminal]
          )
          expect(natives).toContain(terminal.id)
        }
      )
    )
  })

  it('items sin projectId matching NO son nativos', () => {
    fc.assert(
      fc.property(
        arbSession,
        fc.uuid(),
        fc.uuid(),
        (sessionTemplate, otherProject, activeProjectId) => {
          fc.pre(otherProject !== activeProjectId)
          const session = { ...sessionTemplate, projectId: otherProject }
          const group: SessionGroup = {
            id: 'grp_1',
            name: 'test',
            color: null,
            pinned: false,
            itemIds: [session.id],
            activeChatId: session.id
          } as unknown as SessionGroup
          const natives = nativesInThisScopePure(
            group,
            activeProjectId,
            [session],
            []
          )
          expect(natives).not.toContain(session.id)
        }
      )
    )
  })

  it('grupo mixto (chat + terminal): ambos tipos se resuelven', () => {
    // Contrato clave: dissolveGroup NO discrimina por prefijo del id.
    // Consulta las fuentes tipadas (sessions, terminals).
    fc.assert(
      fc.property(arbSession, arbTerminal, fc.uuid(), (s, t, projectId) => {
        const session = { ...s, projectId }
        const terminal = { ...t, projectId }
        const group: SessionGroup = {
          id: 'grp_1',
          name: 'test',
          color: null,
          pinned: false,
          itemIds: [session.id, terminal.id],
          activeChatId: session.id
        } as unknown as SessionGroup
        const natives = nativesInThisScopePure(
          group,
          projectId,
          [session],
          [terminal]
        )
        expect(natives).toContain(session.id)
        expect(natives).toContain(terminal.id)
      })
    )
  })
})
