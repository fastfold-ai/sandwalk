import type { SessionGroup } from '@sandwalk/agent-ui-core'
import { describe, expect, it } from 'vitest'

import { resolveStripActive, resolveStripActiveId } from './strip-active'

const group = (id: string): SessionGroup =>
  ({
    id,
    name: 'Group',
    color: null,
    pinned: false,
    chatIds: [],
    activeChatId: 'chat_x'
  }) as unknown as SessionGroup

describe('resolveStripActive', () => {
  it('prioriza el grupo activo sobre cualquier ruta', () => {
    const result = resolveStripActive(
      { sessionId: 'chat_x', terminalId: 'term_y' },
      group('grp_1')
    )
    expect(result).toEqual({ id: 'grp_1', kind: 'group' })
  })

  it('reconoce terminales cuando no hay grupo', () => {
    const result = resolveStripActive(
      { sessionId: null, terminalId: 'term_y' },
      null
    )
    expect(result).toEqual({ id: 'term_y', kind: 'terminal' })
  })

  it('reconoce chats cuando no hay grupo ni terminal', () => {
    const result = resolveStripActive(
      { sessionId: 'chat_x', terminalId: null },
      null
    )
    expect(result).toEqual({ id: 'chat_x', kind: 'chat' })
  })

  it('detecta grupos que se filtraron a sessionId (edge case)', () => {
    const result = resolveStripActive(
      { sessionId: 'grp_1', terminalId: null },
      null
    )
    expect(result).toEqual({ id: 'grp_1', kind: 'group' })
  })

  it('devuelve null cuando no hay nada activo', () => {
    const result = resolveStripActive(
      { sessionId: null, terminalId: null },
      null
    )
    expect(result).toBeNull()
  })

  it('el terminal gana sobre sessionId cuando ambos existen (ruta terminal)', () => {
    // Puede darse si el router deja rastros — el terminal debe ganar
    // porque su ruta es más específica.
    const result = resolveStripActive(
      { sessionId: 'chat_x', terminalId: 'term_y' },
      null
    )
    expect(result).toEqual({ id: 'term_y', kind: 'terminal' })
  })
})

describe('resolveStripActiveId', () => {
  it('devuelve solo el id', () => {
    expect(
      resolveStripActiveId(
        { sessionId: null, terminalId: 'term_y' },
        null
      )
    ).toBe('term_y')
  })

  it('devuelve null si no hay active', () => {
    expect(
      resolveStripActiveId(
        { sessionId: null, terminalId: null },
        null
      )
    ).toBeNull()
  })
})
