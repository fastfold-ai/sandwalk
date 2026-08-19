import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  filterSectionsToUnread,
  readSidebarUnreadFilter,
  writeSidebarUnreadFilter
} from './sidebar-unread-filter'

const chat = (id: string) =>
  ({
    kind: 'chat' as const,
    id,
    session: { id, title: id } as never,
    lastActivity: 1
  })

describe('filterSectionsToUnread', () => {
  it('drops chats that are not unread', () => {
    const next = filterSectionsToUnread(
      [
        {
          id: 'today',
          title: 'Today',
          items: [chat('a'), chat('b')]
        }
      ],
      new Set(['b'])
    )
    expect(next).toEqual([
      {
        id: 'today',
        title: 'Today',
        items: [chat('b')]
      }
    ])
  })

  it('keeps a group only when a child is unread', () => {
    const group = {
      kind: 'group' as const,
      id: 'g1',
      group: { id: 'g1', name: 'Split' } as never,
      children: [
        { id: 'c1', title: 'one' } as never,
        { id: 'c2', title: 'two' } as never
      ],
      lastActivity: 1
    }
    const next = filterSectionsToUnread(
      [{ id: 'today', title: 'Today', items: [group] }],
      new Set(['c2'])
    )
    expect(next[0]?.items[0]).toMatchObject({
      kind: 'group',
      id: 'g1',
      children: [{ id: 'c2' }]
    })
  })

  it('drops empty sections', () => {
    const next = filterSectionsToUnread(
      [{ id: 'today', title: 'Today', items: [chat('a')] }],
      new Set()
    )
    expect(next).toEqual([])
  })
})

describe('sidebar unread filter persistence', () => {
  beforeEach(() => {
    const store = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
      setItem: (key: string, value: string) => {
        store.set(key, value)
      },
      removeItem: (key: string) => {
        store.delete(key)
      }
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('defaults off and persists the toggle', () => {
    expect(readSidebarUnreadFilter()).toBe(false)
    writeSidebarUnreadFilter(true)
    expect(readSidebarUnreadFilter()).toBe(true)
    writeSidebarUnreadFilter(false)
    expect(readSidebarUnreadFilter()).toBe(false)
  })
})
