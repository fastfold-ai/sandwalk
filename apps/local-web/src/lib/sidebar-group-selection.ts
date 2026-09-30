/**
 * Which split row is selected in the sidebar.
 *
 * The shell's `sessionId` is the focused chat inside a split, and the same
 * chat can belong to more than one group. Matching on that id highlights
 * every group that contains it. When a group is open, only that group
 * (and its focused child) is selected.
 */
export function groupRowSelected(input: {
  groupId: string
  activeId: string | null
  openGroupId: string | null
  childIds: string[]
}): boolean {
  if (input.openGroupId) return input.groupId === input.openGroupId
  if (input.groupId === input.activeId) return true
  return input.childIds.some(id => id === input.activeId)
}

export function splitChildSelected(input: {
  groupId: string
  openGroupId: string | null
  childId: string
  activeId: string | null
  activeChildId: string | null
}): boolean {
  if (input.openGroupId && input.groupId !== input.openGroupId) return false
  return input.childId === input.activeChildId || input.childId === input.activeId
}
