import type {
  AgentSession,
  SessionGroup,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import fc from 'fast-check'
import { describe, expect, it } from 'vitest'

import { buildSessionSidebarModel, computeShowSessionTabs } from './app-display'

/**
 * FAS-107 X5.4 · Property tests de invariantes del sistema strip/sidebar.
 *
 * A diferencia de X5.3 (que testeaba el resolver `StripItem` puro), acá
 * testeamos contratos generales del sistema — las funciones que arman
 * el modelo del sidebar y deciden si mostrar el strip.
 *
 * Cada test valida una propiedad matemática sobre miles de
 * combinaciones al azar. Los bugs de la jornada X4.4 (el cruce visual
 * "New Chat", cascadas de close, dissolve con terminales perdidos)
 * hubieran sido pescados acá.
 */

// Arbitraries.

const arbSession: fc.Arbitrary<AgentSession> = fc
  .record({
    id: fc.uuid(),
    title: fc.string(),
    projectId: fc.option(fc.uuid(), { nil: null }),
    status: fc.constant('idle' as const),
    organizeLabel: fc.constantFrom(null, 'pinned' as const, 'archive' as const)
  })
  .map(rec => rec as unknown as AgentSession)

const arbTerminal: fc.Arbitrary<TerminalSession> = fc
  .record({
    id: fc.uuid().map(u => `term_${u}`),
    title: fc.string(),
    projectId: fc.option(fc.uuid(), { nil: null }),
    organizeLabel: fc.constantFrom(null, 'pinned' as const, 'archive' as const)
  })
  .map(rec => rec as unknown as TerminalSession)

const arbGroup = (sessionIds: string[]): fc.Arbitrary<SessionGroup> =>
  fc
    .record({
      id: fc.uuid().map(u => `grp_${u}`),
      name: fc.string(),
      color: fc.constant(null),
      pinned: fc.boolean(),
      itemIds: fc
        .subarray(sessionIds, { minLength: 1 })
        .filter(arr => arr.length > 0),
      activeChatId: fc.constantFrom(...sessionIds)
    })
    .map(rec => rec as unknown as SessionGroup)

describe('buildSessionSidebarModel · invariantes del strip', () => {
  it('openTabs.length nunca excede openTabIds.length', () => {
    fc.assert(
      fc.property(
        fc.array(arbSession),
        fc.array(arbTerminal),
        fc.array(fc.uuid()),
        (sessions, terminals, extraIds) => {
          const openTabIds = [
            ...sessions.map(s => s.id),
            ...terminals.map(t => t.id),
            ...extraIds
          ]
          const model = buildSessionSidebarModel({
            sessions,
            tabGroups: [],
            activeProjectId: null,
            openTabIds,
            terminals
          })
          expect(model.openTabs.length).toBeLessThanOrEqual(openTabIds.length)
        }
      )
    )
  })

  it('todo id en openTabs también está en openTabIds', () => {
    fc.assert(
      fc.property(
        fc.array(arbSession),
        fc.array(arbTerminal),
        (sessions, terminals) => {
          const openTabIds = [
            ...sessions.map(s => s.id),
            ...terminals.map(t => t.id)
          ]
          const model = buildSessionSidebarModel({
            sessions,
            tabGroups: [],
            activeProjectId: null,
            openTabIds,
            terminals
          })
          for (const item of model.openTabs) {
            expect(openTabIds).toContain(item.id)
          }
        }
      )
    )
  })

  it('sin activeProjectId, openTabs contiene TODOS los ids resolubles', () => {
    // Regresión del bug X4.4-hotfix `53f515d`: `openTabs` no incluía
    // terminales → cuando la strip tenía solo terminales, la app creía
    // que había 0 tabs.
    fc.assert(
      fc.property(
        fc.array(arbSession),
        fc.array(arbTerminal),
        (sessions, terminals) => {
          const openTabIds = [
            ...sessions.map(s => s.id),
            ...terminals.map(t => t.id)
          ]
          const model = buildSessionSidebarModel({
            sessions,
            tabGroups: [],
            activeProjectId: null,
            openTabIds,
            terminals
          })
          expect(model.openTabs.length).toBe(openTabIds.length)
        }
      )
    )
  })

  it('openTabs no tiene ids duplicados', () => {
    fc.assert(
      fc.property(
        fc.array(arbSession),
        fc.array(arbTerminal),
        (sessions, terminals) => {
          const openTabIds = [
            ...sessions.map(s => s.id),
            ...terminals.map(t => t.id)
          ]
          const model = buildSessionSidebarModel({
            sessions,
            tabGroups: [],
            activeProjectId: null,
            openTabIds,
            terminals
          })
          const ids = model.openTabs.map(t => t.id)
          expect(new Set(ids).size).toBe(ids.length)
        }
      )
    )
  })

  it('kind de cada openTab coincide con su fuente real', () => {
    fc.assert(
      fc.property(
        fc.array(arbSession),
        fc.array(arbTerminal),
        (sessions, terminals) => {
          const sessionIds = new Set(sessions.map(s => s.id))
          const terminalIds = new Set(terminals.map(t => t.id))
          const openTabIds = [
            ...sessions.map(s => s.id),
            ...terminals.map(t => t.id)
          ]
          const model = buildSessionSidebarModel({
            sessions,
            tabGroups: [],
            activeProjectId: null,
            openTabIds,
            terminals
          })
          for (const item of model.openTabs) {
            if (item.kind === 'chat') {
              expect(sessionIds.has(item.id)).toBe(true)
            } else if (item.kind === 'terminal') {
              expect(terminalIds.has(item.id)).toBe(true)
            }
          }
        }
      )
    )
  })

  it('filtro por scope: chat visible solo si projectId matchea o es activeSessionId', () => {
    fc.assert(
      fc.property(
        fc.array(arbSession, { minLength: 1 }),
        fc.uuid(),
        (sessions, activeProjectId) => {
          const openTabIds = sessions.map(s => s.id)
          const model = buildSessionSidebarModel({
            sessions,
            tabGroups: [],
            activeProjectId,
            openTabIds,
            terminals: []
          })
          for (const item of model.openTabs) {
            if (item.kind === 'chat') {
              const matches = item.session.projectId === activeProjectId
              const isActive = item.id === undefined // no active
              expect(matches || isActive).toBe(true)
            }
          }
        }
      )
    )
  })

  it('terminales del proyecto activo aparecen en openTabs, los de otros no', () => {
    fc.assert(
      fc.property(
        fc.array(arbTerminal, { minLength: 1 }),
        fc.uuid(),
        (terminals, activeProjectId) => {
          const openTabIds = terminals.map(t => t.id)
          const model = buildSessionSidebarModel({
            sessions: [],
            tabGroups: [],
            activeProjectId,
            openTabIds,
            terminals
          })
          for (const item of model.openTabs) {
            if (item.kind === 'terminal') {
              expect(item.terminal.projectId ?? null).toBe(activeProjectId)
            }
          }
        }
      )
    )
  })
})

describe('buildSessionSidebarModel · grupos con miembros mixtos', () => {
  it('un grupo con al menos un chat del scope activo aparece en openTabs', () => {
    fc.assert(
      fc.property(
        fc.array(arbSession, { minLength: 2, maxLength: 5 }),
        fc.uuid(),
        (sessions, activeProjectId) => {
          const targetSession = { ...sessions[0], projectId: activeProjectId }
          const allSessions = [targetSession, ...sessions.slice(1)]
          const group: SessionGroup = {
            id: 'grp_test',
            name: 'test',
            color: null,
            pinned: false,
            itemIds: allSessions.map(s => s.id),
            activeChatId: targetSession.id
          } as unknown as SessionGroup
          const openTabIds = [group.id]
          const model = buildSessionSidebarModel({
            sessions: allSessions,
            tabGroups: [group],
            activeProjectId,
            openTabIds,
            terminals: []
          })
          const found = model.openTabs.find(t => t.id === group.id)
          expect(found).toBeDefined()
          expect(found?.kind).toBe('group')
        }
      )
    )
  })
})

describe('computeShowSessionTabs · invariantes de decisión visual', () => {
  it('si hay al menos 1 openTab en ruta agente, showSessionTabs es true', () => {
    // Regresión del "New Chat" fantasma: si openTabs.length > 0 y no
    // estamos en dashboard/home/etc, el strip DEBE mostrarse.
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 20 }), openTabsLength => {
        const result = computeShowSessionTabs({
          isDashboard: false,
          isHome: false,
          isLibrary: false,
          isSites: false,
          isProjectHome: false,
          isSkills: false,
          isIntegrations: false,
          sessionId: null,
          openTabsLength
        })
        expect(result).toBe(true)
      })
    )
  })

  it('en dashboard/home/etc, showSessionTabs es false sin importar openTabs', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 20 }), openTabsLength => {
        const result = computeShowSessionTabs({
          isDashboard: true,
          isHome: false,
          isLibrary: false,
          isSites: false,
          isProjectHome: false,
          isSkills: false,
          isIntegrations: false,
          sessionId: null,
          openTabsLength
        })
        expect(result).toBe(false)
      })
    )
  })

  it('a blank New Agent still shows the tab strip', () => {
    expect(
      computeShowSessionTabs({
        isDashboard: false,
        isHome: false,
        isLibrary: false,
        isSites: false,
        isProjectHome: false,
        isSkills: false,
        isIntegrations: false,
        sessionId: 'new',
        openTabsLength: 0
      })
    ).toBe(true)
  })

  it('con sesión real activa, showSessionTabs es true aunque openTabsLength = 0', () => {
    fc.assert(
      fc.property(
        fc.uuid().filter(id => !['home', 'new'].includes(id)),
        realSessionId => {
          const result = computeShowSessionTabs({
            isDashboard: false,
            isHome: false,
            isLibrary: false,
            isSites: false,
            isProjectHome: false,
            isSkills: false,
            isIntegrations: false,
            sessionId: realSessionId,
            openTabsLength: 0
          })
          expect(result).toBe(true)
        }
      )
    )
  })
})
