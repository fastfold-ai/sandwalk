import type { PaneNode } from '@sandwalk/agent-ui-core'

/**
 * Pure operations on the tiling tree (Warp / iTerm2 model). Each
 * function returns a new tree — no in-place mutation — so React can
 * treat state updates as immutable and re-render predictably.
 */

export type SplitDirection = 'horizontal' | 'vertical'

/**
 * Build the default tree for a group: a single horizontal branch whose
 * children are the chats in the given order, with equal ratios. When
 * there's only one chat, we return a bare `chat` leaf — a branch with a
 * single child is redundant and would collapse immediately.
 */
export function buildDefaultTree(chatIds: string[]): PaneNode {
  if (chatIds.length === 0) {
    return { type: 'chat', chatId: '' }
  }
  if (chatIds.length === 1) {
    return { type: 'chat', chatId: chatIds[0] }
  }
  return {
    type: 'branch',
    direction: 'horizontal',
    ratios: equalRatios(chatIds.length),
    children: chatIds.map(id => ({ type: 'chat', chatId: id } as PaneNode))
  }
}

export function equalRatios(n: number): number[] {
  if (n <= 0) return []
  const share = 1 / n
  return Array.from({ length: n }, () => share)
}

/**
 * Collect chat ids in tree traversal order. Handy for computing the
 * chatIds array on the group and for reconciliation.
 */
export function extractChatIds(node: PaneNode): string[] {
  if (node.type === 'chat') return node.chatId ? [node.chatId] : []
  return node.children.flatMap(extractChatIds)
}

/**
 * Split the pane holding `targetChatId` in the requested direction and
 * insert a new pane holding `newChatId` on the requested side. If the
 * parent branch already runs in the requested direction, we insert as a
 * sibling with equal ratios; otherwise we wrap the target in a new
 * branch of the requested direction.
 *
 * `side` decides where the new pane lands: 'after' means right (for
 * horizontal) or below (for vertical). 'before' is the mirror.
 */
export function splitPane(
  tree: PaneNode,
  targetChatId: string,
  direction: SplitDirection,
  newChatId: string,
  side: 'before' | 'after' = 'after'
): PaneNode {
  // Special case: the whole tree is a single chat pane.
  if (tree.type === 'chat') {
    if (tree.chatId !== targetChatId) return tree
    const newLeaf: PaneNode = { type: 'chat', chatId: newChatId }
    const children =
      side === 'after' ? [tree, newLeaf] : [newLeaf, tree]
    return {
      type: 'branch',
      direction,
      ratios: equalRatios(2),
      children
    }
  }
  return splitInBranch(tree, targetChatId, direction, newChatId, side)
}

function splitInBranch(
  branch: PaneNode & { type: 'branch' },
  targetChatId: string,
  direction: SplitDirection,
  newChatId: string,
  side: 'before' | 'after'
): PaneNode {
  const index = branch.children.findIndex(child => containsChat(child, targetChatId))
  if (index === -1) return branch
  const child = branch.children[index]
  // The target lives deeper — recurse; the branch stays unchanged
  // structurally, only the affected child is replaced.
  if (child.type === 'branch' && !isLeafOf(child, targetChatId)) {
    const newChild = splitInBranch(child, targetChatId, direction, newChatId, side)
    const nextChildren = branch.children.slice()
    nextChildren[index] = newChild
    return { ...branch, children: nextChildren }
  }
  // The target is a direct chat child (or a wrapper we can flatten).
  if (branch.direction === direction) {
    // Same direction as the parent branch → insert as a sibling with
    // equal ratios so the split feels balanced instead of squishing the
    // existing chats.
    const newLeaf: PaneNode = { type: 'chat', chatId: newChatId }
    const insertAt = side === 'after' ? index + 1 : index
    const nextChildren = branch.children.slice()
    nextChildren.splice(insertAt, 0, newLeaf)
    return {
      ...branch,
      ratios: equalRatios(nextChildren.length),
      children: nextChildren
    }
  }
  // Perpendicular split → wrap the target in a new branch of the
  // requested direction and place both panes there with equal ratios.
  const newLeaf: PaneNode = { type: 'chat', chatId: newChatId }
  const wrapperChildren =
    side === 'after' ? [child, newLeaf] : [newLeaf, child]
  const wrapper: PaneNode = {
    type: 'branch',
    direction,
    ratios: equalRatios(2),
    children: wrapperChildren
  }
  const nextChildren = branch.children.slice()
  nextChildren[index] = wrapper
  return { ...branch, children: nextChildren }
}

function containsChat(node: PaneNode, chatId: string): boolean {
  if (node.type === 'chat') return node.chatId === chatId
  return node.children.some(c => containsChat(c, chatId))
}

function isLeafOf(node: PaneNode, chatId: string): boolean {
  return node.type === 'chat' && node.chatId === chatId
}

/**
 * Remove the pane holding `chatId`. When a branch is left with a single
 * child, the child bubbles up and replaces the branch (Warp's collapse
 * behaviour). Returns null when the whole tree becomes empty — the
 * caller decides what to do (dissolve the group, usually).
 */
export function closePane(tree: PaneNode, chatId: string): PaneNode | null {
  if (tree.type === 'chat') {
    return tree.chatId === chatId ? null : tree
  }
  const nextChildren: PaneNode[] = []
  for (const child of tree.children) {
    const kept = closePane(child, chatId)
    if (kept !== null) nextChildren.push(kept)
  }
  if (nextChildren.length === 0) return null
  if (nextChildren.length === 1) return nextChildren[0]
  // Preserve existing ratios for surviving children where possible; new
  // children (there are none in close, but keep the code stable) fall
  // back to equal ratios.
  const keptRatios = filterKeptRatios(tree, chatId)
  const ratios =
    keptRatios.length === nextChildren.length
      ? renormalize(keptRatios)
      : equalRatios(nextChildren.length)
  return { ...tree, ratios, children: nextChildren }
}

function filterKeptRatios(
  branch: PaneNode & { type: 'branch' },
  chatId: string
): number[] {
  const result: number[] = []
  branch.children.forEach((child, index) => {
    const kept = closePane(child, chatId)
    if (kept !== null) result.push(branch.ratios[index] ?? 0)
  })
  return result
}

function renormalize(ratios: number[]): number[] {
  const sum = ratios.reduce((acc, r) => acc + r, 0)
  if (sum <= 0) return equalRatios(ratios.length)
  return ratios.map(r => r / sum)
}

/**
 * Replace the ratios of a specific branch identified by a path of child
 * indices from the root. Used when the user drags a divider — react-
 * resizable-panels reports the new sizes as percentages that we
 * translate directly to ratios.
 */
export function setBranchRatios(
  tree: PaneNode,
  path: number[],
  ratios: number[]
): PaneNode {
  if (path.length === 0) {
    if (tree.type !== 'branch') return tree
    if (ratios.length !== tree.children.length) return tree
    return { ...tree, ratios: renormalize(ratios) }
  }
  if (tree.type !== 'branch') return tree
  const [head, ...rest] = path
  const child = tree.children[head]
  if (!child) return tree
  const nextChildren = tree.children.slice()
  nextChildren[head] = setBranchRatios(child, rest, ratios)
  return { ...tree, children: nextChildren }
}

/**
 * Reconcile a persisted tree against the current chatIds list. Chats
 * missing from the tree are appended as new sibling panes at the root;
 * panes whose chatId no longer exists in the group are removed and the
 * layout is collapsed. Returns the (possibly rebuilt) tree.
 */
export function reconcileTree(tree: PaneNode, chatIds: string[]): PaneNode {
  const known = new Set(chatIds)
  let current: PaneNode | null = pruneUnknown(tree, known)
  if (current === null) return buildDefaultTree(chatIds)
  const existing = new Set(extractChatIds(current))
  const missing = chatIds.filter(id => !existing.has(id))
  for (const chatId of missing) {
    current = appendChatAtRoot(current, chatId)
  }
  return current
}

function pruneUnknown(tree: PaneNode, known: Set<string>): PaneNode | null {
  if (tree.type === 'chat') {
    return known.has(tree.chatId) ? tree : null
  }
  const nextChildren: PaneNode[] = []
  const nextRatios: number[] = []
  tree.children.forEach((child, i) => {
    const kept = pruneUnknown(child, known)
    if (kept !== null) {
      nextChildren.push(kept)
      nextRatios.push(tree.ratios[i] ?? 0)
    }
  })
  if (nextChildren.length === 0) return null
  if (nextChildren.length === 1) return nextChildren[0]
  return { ...tree, children: nextChildren, ratios: renormalize(nextRatios) }
}

function appendChatAtRoot(tree: PaneNode, chatId: string): PaneNode {
  const leaf: PaneNode = { type: 'chat', chatId }
  if (tree.type === 'chat') {
    return {
      type: 'branch',
      direction: 'horizontal',
      ratios: equalRatios(2),
      children: [tree, leaf]
    }
  }
  if (tree.direction === 'horizontal') {
    const nextChildren = [...tree.children, leaf]
    return {
      ...tree,
      ratios: equalRatios(nextChildren.length),
      children: nextChildren
    }
  }
  // Root is a vertical branch — wrap it and add the new chat to the right.
  return {
    type: 'branch',
    direction: 'horizontal',
    ratios: equalRatios(2),
    children: [tree, leaf]
  }
}
