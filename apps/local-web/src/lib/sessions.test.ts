import type { AgentSession } from '@sandwalk/agent-ui-core'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  emptySessionChatState,
  groupSessions,
  groupTabItems,
  isLowSignalTitle,
  relativeDayLabel,
  relativeTime,
  visibleSessionIds
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

describe('groupTabItems', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('nests grouped chats and buckets by recency', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 6, 13, 15, 0, 0))
    const today = session({
      id: 't1',
      title: 'Today',
      lastMessageAt: new Date(2026, 6, 13, 14, 0, 0).toISOString()
    })
    const yesterday = session({
      id: 'y1',
      title: 'Yesterday',
      lastMessageAt: new Date(2026, 6, 12, 10, 0, 0).toISOString()
    })
    const older = session({
      id: 'o1',
      title: 'Older',
      lastMessageAt: new Date(2026, 6, 1, 10, 0, 0).toISOString()
    })
    const child = session({
      id: 'c1',
      title: 'Child',
      lastMessageAt: new Date(2026, 6, 13, 14, 30, 0).toISOString()
    })
    const guest = session({
      id: 'g1',
      title: 'Guest',
      lastMessageAt: new Date(2026, 6, 13, 14, 45, 0).toISOString()
    })
    const sections = groupTabItems(
      [today, yesterday, older, child],
      [
        {
          id: 'grp_1',
          name: 'Split',
          color: null,
          pinned: false,
          chatIds: ['c1', 'g1'],
          activeChatId: 'c1'
        }
      ],
      [today, yesterday, older, child, guest]
    )
    expect(sections.find(s => s.id === 'today')?.items.map(i => i.id)).toEqual(
      expect.arrayContaining(['t1', 'grp_1'])
    )
    const group = sections
      .flatMap(s => s.items)
      .find(item => item.kind === 'group' && item.id === 'grp_1')
    expect(group?.kind === 'group' ? group.children.map(c => c.id) : []).toEqual([
      'c1',
      'g1'
    ])
    expect(sections.find(s => s.id === 'yesterday')?.items.map(i => i.id)).toEqual([
      'y1'
    ])
    expect(sections.find(s => s.id === 'older')?.items.map(i => i.id)).toEqual(['o1'])
  })

  it('puts pinned chats and groups in Pinned and lists visible ids', () => {
    const pinnedChat = session({
      id: 'p1',
      title: 'Pinned chat',
      organizeLabel: 'pinned',
      lastMessageAt: '2026-07-13T11:00:00.000Z'
    })
    const archived = session({
      id: 'a1',
      title: 'Archived',
      organizeLabel: 'archive',
      lastMessageAt: '2026-07-13T11:00:00.000Z'
    })
    const child = session({
      id: 'c1',
      title: 'Child',
      lastMessageAt: '2026-07-13T11:00:00.000Z'
    })
    const sections = groupTabItems(
      [pinnedChat, archived, child],
      [
        {
          id: 'grp_pin',
          name: 'Pinned split',
          color: null,
          pinned: true,
          chatIds: ['c1'],
          activeChatId: 'c1'
        }
      ]
    )
    expect(sections.find(s => s.id === 'pinned')?.items.map(i => i.id)).toEqual(
      expect.arrayContaining(['p1', 'grp_pin'])
    )
    expect(sections.find(s => s.id === 'archive')?.items.map(i => i.id)).toEqual([
      'a1'
    ])
    expect(visibleSessionIds(sections, { archive: true })).toEqual(
      expect.arrayContaining(['p1', 'grp_pin', 'c1'])
    )
    expect(visibleSessionIds(sections, { archive: true })).not.toContain('a1')
  })
})
