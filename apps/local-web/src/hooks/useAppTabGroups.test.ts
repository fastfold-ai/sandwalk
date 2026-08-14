import type { AgentSession, SessionGroup } from '@sandwalk/agent-ui-core'
import { act, renderHook } from '@testing-library/react'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAppTabGroups } from './useAppTabGroups'

vi.mock('@/lib/app-storage', () => ({
  writeTabGroups: vi.fn()
}))

function session(id: string, projectId: string | null = null): AgentSession {
  return {
    id,
    title: id,
    status: 'idle',
    organizeLabel: null,
    projectId,
    specialistId: null,
    workspacePath: null,
    lastMessageAt: null,
    createdAt: '2026-08-14T00:00:00Z',
    updatedAt: '2026-08-14T00:00:00Z'
  } as AgentSession
}

/** Small harness: mounts `useAppTabGroups` with a real `useState` for
 * `allTabGroups` so mutations round-trip through the hook the same way
 * they do in the app. */
function useHarness(sessions: AgentSession[], initial: SessionGroup[] = []) {
  const [allTabGroups, setAllTabGroups] = useState<SessionGroup[]>(initial)
  const setOpenTabIds = vi.fn()
  const store = useAppTabGroups(
    null,
    sessions,
    allTabGroups,
    setAllTabGroups,
    setOpenTabIds
  )
  return { store, allTabGroups }
}

describe('useAppTabGroups.createGroup', () => {
  it('rejects fewer than 2 chats (non-pending)', () => {
    const sessions = [session('a')]
    const { result } = renderHook(() => useHarness(sessions))
    let groupId: string | null = 'x'
    act(() => {
      groupId = result.current.store.createGroup(['a'])
    })
    expect(groupId).toBeNull()
    expect(result.current.store.allTabGroups).toHaveLength(0)
  })

  it('creates a group with 2+ chats', () => {
    const sessions = [session('a'), session('b')]
    const { result } = renderHook(() => useHarness(sessions))
    let groupId: string | null = null
    act(() => {
      groupId = result.current.store.createGroup(['a', 'b'])
    })
    expect(groupId).toMatch(/^grp_/)
    expect(result.current.store.allTabGroups).toHaveLength(1)
    expect(result.current.store.allTabGroups[0].chatIds).toEqual(['a', 'b'])
  })
})

describe('useAppTabGroups.createPendingGroup', () => {
  it('creates a group with 1 chat + isPending=true', () => {
    const sessions = [session('a')]
    const { result } = renderHook(() => useHarness(sessions))
    let groupId: string | null = null
    act(() => {
      groupId = result.current.store.createPendingGroup('a')
    })
    expect(groupId).toMatch(/^grp_/)
    expect(result.current.store.allTabGroups[0].isPending).toBe(true)
    expect(result.current.store.allTabGroups[0].chatIds).toEqual(['a'])
  })

  it('cancels any previous pending group when a new one is created', () => {
    const sessions = [session('a'), session('b')]
    const { result } = renderHook(() => useHarness(sessions))
    act(() => {
      result.current.store.createPendingGroup('a')
    })
    act(() => {
      result.current.store.createPendingGroup('b')
    })
    // Only the last pending survives — old pending gets cleaned up.
    const pending = result.current.store.allTabGroups.filter(g => g.isPending)
    expect(pending).toHaveLength(1)
    expect(pending[0].chatIds).toEqual(['b'])
  })
})

describe('useAppTabGroups.promotePendingGroup', () => {
  it('clears isPending and appends the partner chatId', () => {
    const sessions = [session('a'), session('b')]
    const { result } = renderHook(() => useHarness(sessions))
    let pendingId: string | null = null
    act(() => {
      pendingId = result.current.store.createPendingGroup('a')
    })
    act(() => {
      result.current.store.promotePendingGroup(pendingId!, 'b')
    })
    const group = result.current.store.allTabGroups[0]
    expect(group.isPending).toBe(false)
    expect(group.chatIds).toEqual(['a', 'b'])
    // `promotePendingGroup` preserves the original activeChatId (the
    // source chat 'a'). The caller can override via setGroupActiveChat.
    expect(group.activeChatId).toBe('a')
  })

  it('scrubs the partner from any other groups first', () => {
    const sessions = [session('a'), session('b'), session('c'), session('d')]
    const { result } = renderHook(() => useHarness(sessions))
    let otherGroupId: string | null = null
    let pendingId: string | null = null
    act(() => {
      // Group 1 contains a, b, c
      otherGroupId = result.current.store.createGroup(['a', 'b', 'c'])
    })
    act(() => {
      // Pending group with d
      pendingId = result.current.store.createPendingGroup('d')
    })
    act(() => {
      // Promote pending with `b` — `b` should leave group 1.
      result.current.store.promotePendingGroup(pendingId!, 'b')
    })
    const group1 = result.current.store.allTabGroups.find(
      g => g.id === otherGroupId
    )!
    const group2 = result.current.store.allTabGroups.find(
      g => g.id === pendingId
    )!
    expect(group1.chatIds).not.toContain('b')
    expect(group2.chatIds).toEqual(['d', 'b'])
  })
})

describe('useAppTabGroups.addToGroup / removeFromGroup', () => {
  it('addToGroup scrubs the chat from other groups', () => {
    const sessions = [session('a'), session('b'), session('c')]
    const { result } = renderHook(() => useHarness(sessions))
    let g1: string | null = null
    let g2: string | null = null
    act(() => {
      g1 = result.current.store.createGroup(['a', 'b'])
    })
    act(() => {
      g2 = result.current.store.createGroup(['c'], { isPending: true })
    })
    act(() => {
      result.current.store.addToGroup(g2!, 'a')
    })
    const group1 = result.current.store.allTabGroups.find(g => g.id === g1)!
    const group2 = result.current.store.allTabGroups.find(g => g.id === g2)!
    // addToGroup pulls `a` out of g1 and appends to g2.
    expect(group1.chatIds).not.toContain('a')
    expect(group2.chatIds).toContain('a')
  })

  it('removeFromGroup drops the chat, keeps the group', () => {
    const sessions = [session('a'), session('b'), session('c')]
    const { result } = renderHook(() => useHarness(sessions))
    let groupId: string | null = null
    act(() => {
      groupId = result.current.store.createGroup(['a', 'b', 'c'])
    })
    act(() => {
      result.current.store.removeFromGroup(groupId!, 'b')
    })
    const group = result.current.store.allTabGroups.find(g => g.id === groupId)!
    expect(group.chatIds).toEqual(['a', 'c'])
  })
})

describe('useAppTabGroups.dissolveGroup', () => {
  it('removes the group entirely', () => {
    const sessions = [session('a'), session('b')]
    const { result } = renderHook(() => useHarness(sessions))
    let groupId: string | null = null
    act(() => {
      groupId = result.current.store.createGroup(['a', 'b'])
    })
    act(() => {
      result.current.store.dissolveGroup(groupId!)
    })
    expect(result.current.store.allTabGroups).toHaveLength(0)
  })
})

describe('useAppTabGroups.pruneChatFromGroups', () => {
  it('removes a chat from every group it belongs to', () => {
    const sessions = [session('a'), session('b'), session('c'), session('d')]
    const { result } = renderHook(() => useHarness(sessions))
    act(() => {
      result.current.store.createGroup(['a', 'b', 'c'])
    })
    act(() => {
      result.current.store.createGroup(['a', 'd'])
    })
    act(() => {
      result.current.store.pruneChatFromGroups('a')
    })
    for (const group of result.current.store.allTabGroups) {
      expect(group.chatIds).not.toContain('a')
    }
  })

  it('auto-dissolves a group left with fewer than 2 chats', () => {
    const sessions = [session('a'), session('b')]
    const { result } = renderHook(() => useHarness(sessions))
    act(() => {
      result.current.store.createGroup(['a', 'b'])
    })
    act(() => {
      result.current.store.pruneChatFromGroups('a')
    })
    // Group had [a, b] → now would have [b] → auto-dissolved.
    expect(result.current.store.allTabGroups).toHaveLength(0)
  })
})

describe('useAppTabGroups.setGroupActiveChat', () => {
  it('updates activeChatId when the chat belongs to the group', () => {
    const sessions = [session('a'), session('b')]
    const { result } = renderHook(() => useHarness(sessions))
    let groupId: string | null = null
    act(() => {
      groupId = result.current.store.createGroup(['a', 'b'])
    })
    act(() => {
      result.current.store.setGroupActiveChat(groupId!, 'b')
    })
    expect(result.current.store.allTabGroups[0].activeChatId).toBe('b')
  })

  it('ignores a chat that is not in the group', () => {
    const sessions = [session('a'), session('b'), session('c')]
    const { result } = renderHook(() => useHarness(sessions))
    let groupId: string | null = null
    act(() => {
      groupId = result.current.store.createGroup(['a', 'b'])
    })
    const before = result.current.store.allTabGroups[0].activeChatId
    act(() => {
      // 'c' is not in the group.
      result.current.store.setGroupActiveChat(groupId!, 'c')
    })
    expect(result.current.store.allTabGroups[0].activeChatId).toBe(before)
  })
})

// Suppress noisy React act() warnings for the harness.
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
})
