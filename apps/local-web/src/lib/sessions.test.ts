import type { AgentSession, SessionGroup } from '@sandwalk/agent-ui-core'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  emptySessionChatState,
  groupSessions,
  groupTabItems,
  isLowSignalTitle,
  relativeDayLabel,
  relativeTime
} from './sessions'

function session(
  partial: Partial<AgentSession> & Pick<AgentSession, 'id' | 'title'>
): AgentSession {
  return {
    createdAt: '2026-07-13T10:00:00.000Z',
    updatedAt: '2026-07-13T10:00:00.000Z',
    organizeLabel: null,
    ...partial
  } as AgentSession
}

describe('emptySessionChatState', () => {
  it('returns idle defaults', () => {
    const state = emptySessionChatState()
    expect(state.messages).toEqual([])
    expect(state.runActive).toBe(false)
    expect(state.messagesLoaded).toBe(false)
    expect(state.queuedMessages).toEqual([])
    expect(state.tokenUsage).toEqual({ inputTokens: 0, outputTokens: 0 })
  })
})

describe('relativeTime', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('formats elapsed buckets', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-13T12:00:00.000Z'))
    expect(relativeTime('2026-07-13T11:59:30.000Z')).toBe('now')
    expect(relativeTime('2026-07-13T11:45:00.000Z')).toBe('15m')
    expect(relativeTime('2026-07-13T09:00:00.000Z')).toBe('3h')
    expect(relativeTime('2026-07-11T12:00:00.000Z')).toBe('2d')
  })
})

describe('relativeDayLabel', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('uses Today, Yesterday, then Nd ago', () => {
    vi.useFakeTimers()
    const now = new Date(2026, 6, 13, 15, 0, 0)
    vi.setSystemTime(now)
    expect(relativeDayLabel(new Date(2026, 6, 13, 1, 0, 0).toISOString(), now)).toBe(
      'Today'
    )
    expect(relativeDayLabel(new Date(2026, 6, 12, 23, 0, 0).toISOString(), now)).toBe(
      'Yesterday'
    )
    expect(relativeDayLabel(new Date(2026, 6, 3, 12, 0, 0).toISOString(), now)).toBe(
      '10d ago'
    )
  })
})

describe('isLowSignalTitle', () => {
  it('flags empty and default titles', () => {
    expect(isLowSignalTitle('')).toBe(true)
    expect(isLowSignalTitle('Untitled')).toBe(true)
    expect(isLowSignalTitle('New chat')).toBe(true)
    expect(isLowSignalTitle('Greeting chat about proteins')).toBe(true)
    expect(isLowSignalTitle('KRAS binder screen')).toBe(false)
  })
})

describe('groupSessions', () => {
  it('buckets pinned, archived, and ordinary sessions', () => {
    const groups = groupSessions([
      session({
        id: '1',
        title: 'Pinned',
        organizeLabel: 'pinned',
        updatedAt: '2026-07-13T11:00:00.000Z'
      }),
      session({
        id: '2',
        title: 'Archived',
        organizeLabel: 'archive',
        updatedAt: '2026-07-13T11:00:00.000Z'
      }),
      session({
        id: '3',
        title: 'Today',
        updatedAt: new Date().toISOString()
      })
    ])
    expect(groups.find(g => g.id === 'pinned')?.items).toHaveLength(1)
    expect(groups.find(g => g.id === 'archive')?.items).toHaveLength(1)
    expect(
      groups.filter(g => g.id !== 'pinned' && g.id !== 'archive').flatMap(g => g.items)
        .length
    ).toBe(1)
  })
})

function group(
  id: string,
  chatIds: string[],
  overrides: Partial<SessionGroup> = {}
): SessionGroup {
  return {
    id,
    name: id,
    color: null,
    pinned: false,
    chatIds,
    activeChatId: chatIds[0],
    ...overrides
  } as SessionGroup
}

describe('groupTabItems', () => {
  it('resolves group children from scoped sessions when no wider pool given', () => {
    const scoped = [
      session({ id: 'a', title: 'A' }),
      session({ id: 'b', title: 'B' })
    ]
    const groups = [group('grp_1', ['a', 'b'])]
    const sections = groupTabItems(scoped, groups)
    const groupItem = sections
      .flatMap(s => s.items)
      .find(i => i.kind === 'group')
    if (groupItem?.kind === 'group') {
      expect(groupItem.children.map(c => c.id)).toEqual(['a', 'b'])
    } else {
      throw new Error('expected group item')
    }
  })

  it('resolves foreign group children from the wider pool', () => {
    // Regression guard for the cross-project sidebar bug: when a group
    // contains a chat from another project, the scoped list filters it
    // out, but children should still resolve via the wider pool.
    const scoped = [session({ id: 'a', title: 'A', projectId: 'p1' })]
    const wider = [
      session({ id: 'a', title: 'A', projectId: 'p1' }),
      session({ id: 'b', title: 'B (foreign)', projectId: 'p2' })
    ]
    const groups = [group('grp_1', ['a', 'b'])]
    const sections = groupTabItems(scoped, groups, wider)
    const groupItem = sections
      .flatMap(s => s.items)
      .find(i => i.kind === 'group')
    if (groupItem?.kind === 'group') {
      expect(groupItem.children.map(c => c.id).sort()).toEqual(['a', 'b'])
    } else {
      throw new Error('expected group item')
    }
  })

  it('does NOT surface foreign chats as standalone items', () => {
    // The wider pool is only for group children resolution — it must
    // not leak foreign chats into the flat standalone listing.
    const scoped = [session({ id: 'a', title: 'A' })]
    const wider = [
      session({ id: 'a', title: 'A' }),
      session({ id: 'c', title: 'C (foreign)', projectId: 'p2' })
    ]
    const sections = groupTabItems(scoped, [], wider)
    const chatIds = sections
      .flatMap(s => s.items)
      .filter(i => i.kind === 'chat')
      .map(i => i.id)
    expect(chatIds).toContain('a')
    expect(chatIds).not.toContain('c')
  })

  it('excludes chats that live inside a group from the flat listing', () => {
    const scoped = [
      session({ id: 'a', title: 'A' }),
      session({ id: 'b', title: 'B' }),
      session({ id: 'c', title: 'C' })
    ]
    const groups = [group('grp_1', ['a', 'b'])]
    const sections = groupTabItems(scoped, groups)
    const chatIds = sections
      .flatMap(s => s.items)
      .filter(i => i.kind === 'chat')
      .map(i => i.id)
    expect(chatIds).toEqual(['c'])
  })
})
