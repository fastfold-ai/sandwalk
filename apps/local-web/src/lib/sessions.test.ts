import type { AgentSession } from '@sandwalk/agent-ui-core'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  emptySessionChatState,
  groupSessions,
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
