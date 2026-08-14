import type { AgentSession } from '@sandwalk/agent-ui-core'
import { describe, expect, it } from 'vitest'

import {
  mergeRunActiveFromSessions,
  sessionsUnchanged
} from './useAppBootstrapLoaders'
import { emptySessionChatState } from '@/lib/sessions'

function session(overrides: Partial<AgentSession> = {}): AgentSession {
  return {
    id: 'a',
    title: 'One',
    status: 'idle',
    organizeLabel: null,
    projectId: null,
    specialistId: null,
    workspacePath: null,
    lastMessageAt: null,
    createdAt: '2026-07-25T00:00:00Z',
    updatedAt: '2026-07-25T00:00:00Z',
    ...overrides
  } as AgentSession
}

describe('sessionsUnchanged', () => {
  it('treats an identical re-fetch as unchanged', () => {
    expect(sessionsUnchanged([session()], [session()])).toBe(true)
  })

  it('notices a session arriving from the CLI or Slack', () => {
    const before = [session()]
    const after = [session(), session({ id: 'b', title: 'From Slack' })]
    expect(sessionsUnchanged(before, after)).toBe(false)
  })

  it('notices a session disappearing', () => {
    expect(sessionsUnchanged([session(), session({ id: 'b' })], [session()])).toBe(
      false
    )
  })

  it.each([
    ['title', { title: 'Renamed' }],
    ['status', { status: 'running' as const }],
    ['updatedAt', { updatedAt: '2026-07-25T01:00:00Z' }],
    ['lastMessageAt', { lastMessageAt: '2026-07-25T01:00:00Z' }],
    ['organizeLabel', { organizeLabel: 'archive' as const }],
    ['projectId', { projectId: 'proj-1' }]
  ])('notices a changed %s', (_field, change) => {
    expect(sessionsUnchanged([session()], [session(change)])).toBe(false)
  })

  it('is order sensitive, since the sidebar renders in order', () => {
    const a = [session({ id: 'a' }), session({ id: 'b' })]
    const b = [session({ id: 'b' }), session({ id: 'a' })]
    expect(sessionsUnchanged(a, b)).toBe(false)
  })
})

describe('mergeRunActiveFromSessions', () => {
  it('promotes idle chat state when the list says running', () => {
    const current = { a: emptySessionChatState() }
    const next = mergeRunActiveFromSessions(current, [
      session({ status: 'running' })
    ])
    expect(next.a.runActive).toBe(true)
  })

  it('does not demote an optimistic running send from a stale idle list', () => {
    const current = {
      a: { ...emptySessionChatState(), runActive: true }
    }
    const next = mergeRunActiveFromSessions(current, [
      session({ status: 'idle' })
    ])
    expect(next).toBe(current)
    expect(next.a.runActive).toBe(true)
  })
})
