import { describe, expect, it } from 'vitest'

import { filterSectionsToUnread } from './sidebar-unread-filter'

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
