import type { AgentSession } from '@sandwalk/agent-ui-core'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  applyChatDateBoosts,
  setChatDateBoosts
} from './chat-date-boost'

function session(
  id: string,
  overrides: Partial<AgentSession> = {}
): AgentSession {
  return {
    id,
    title: id,
    status: 'idle',
    organizeLabel: null,
    projectId: null,
    specialistId: null,
    workspacePath: null,
    lastMessageAt: null,
    createdAt: '2026-08-14T00:00:00Z',
    updatedAt: '2026-08-14T00:00:00Z',
    ...overrides
  } as AgentSession
}

beforeEach(() => {
  localStorage.clear()
})
afterEach(() => {
  localStorage.clear()
})

describe('setChatDateBoosts', () => {
  it('no-op on empty ids array', () => {
    setChatDateBoosts([], '2026-08-14T10:00:00Z')
    expect(localStorage.getItem('sandwalk.chat-date-boost')).toBeNull()
  })

  it('stores the same iso for each id', () => {
    const iso = '2026-08-14T10:00:00Z'
    setChatDateBoosts(['a', 'b'], iso)
    const raw = localStorage.getItem('sandwalk.chat-date-boost')
    expect(raw).not.toBeNull()
    const parsed = JSON.parse(raw!)
    expect(parsed).toEqual({ a: iso, b: iso })
  })

  it('merges new boosts with existing ones', () => {
    setChatDateBoosts(['a'], '2026-08-14T10:00:00Z')
    setChatDateBoosts(['b'], '2026-08-14T11:00:00Z')
    const parsed = JSON.parse(localStorage.getItem('sandwalk.chat-date-boost')!)
    expect(parsed.a).toBe('2026-08-14T10:00:00Z')
    expect(parsed.b).toBe('2026-08-14T11:00:00Z')
  })
})

describe('applyChatDateBoosts', () => {
  it('returns the original array when no boosts exist', () => {
    const sessions = [session('a')]
    const result = applyChatDateBoosts(sessions)
    expect(result).toBe(sessions) // same reference
  })

  it('overrides lastMessageAt for chats with active boosts', () => {
    setChatDateBoosts(['a'], '2026-08-14T10:00:00Z')
    const result = applyChatDateBoosts([
      session('a', { lastMessageAt: '2026-08-13T09:00:00Z' })
    ])
    expect(result[0].lastMessageAt).toBe('2026-08-14T10:00:00Z')
  })

  it('leaves unrelated chats untouched', () => {
    setChatDateBoosts(['a'], '2026-08-14T10:00:00Z')
    const result = applyChatDateBoosts([
      session('a', { lastMessageAt: '2026-08-13T09:00:00Z' }),
      session('b', { lastMessageAt: '2026-08-13T09:00:00Z' })
    ])
    expect(result[1].lastMessageAt).toBe('2026-08-13T09:00:00Z')
  })

  it('clears a boost when server activity has caught up or passed it', () => {
    setChatDateBoosts(['a'], '2026-08-14T10:00:00Z')
    const result = applyChatDateBoosts([
      session('a', { lastMessageAt: '2026-08-14T12:00:00Z' })
    ])
    // The server value is newer than the boost — return as-is + clear storage.
    expect(result[0].lastMessageAt).toBe('2026-08-14T12:00:00Z')
    expect(localStorage.getItem('sandwalk.chat-date-boost')).toBeNull()
  })

  it('falls back to updatedAt when lastMessageAt is null', () => {
    setChatDateBoosts(['a'], '2026-08-14T10:00:00Z')
    const result = applyChatDateBoosts([
      session('a', {
        lastMessageAt: null,
        updatedAt: '2026-08-14T12:00:00Z'
      })
    ])
    // updatedAt (12:00) is newer than boost (10:00) → clear + return as-is.
    expect(result[0].lastMessageAt).toBeNull()
  })
})
