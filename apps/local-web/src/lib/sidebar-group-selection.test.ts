import { describe, expect, it } from 'vitest'

import { groupRowSelected, splitChildSelected } from './sidebar-group-selection'

const shared = ['chat-a', 'chat-b']

describe('groupRowSelected', () => {
  it('selects only the open group when the focused chat is in several groups', () => {
    const base = {
      activeId: 'chat-a',
      openGroupId: 'grp_9',
      childIds: shared
    }
    expect(groupRowSelected({ ...base, groupId: 'grp_9' })).toBe(true)
    expect(groupRowSelected({ ...base, groupId: 'grp_8' })).toBe(false)
  })

  it('highlights a group that contains the chat when no group route is open', () => {
    expect(
      groupRowSelected({
        groupId: 'grp_8',
        activeId: 'chat-a',
        openGroupId: null,
        childIds: shared
      })
    ).toBe(true)
  })
})

describe('splitChildSelected', () => {
  it('does not mark the same child active inside a group that is not open', () => {
    expect(
      splitChildSelected({
        groupId: 'grp_8',
        openGroupId: 'grp_9',
        childId: 'chat-a',
        activeId: 'chat-a',
        activeChildId: 'chat-a'
      })
    ).toBe(false)
    expect(
      splitChildSelected({
        groupId: 'grp_9',
        openGroupId: 'grp_9',
        childId: 'chat-a',
        activeId: 'chat-a',
        activeChildId: 'chat-a'
      })
    ).toBe(true)
  })
})
