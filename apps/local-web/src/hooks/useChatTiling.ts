import type { PaneNode, WorkspaceItemRef } from '@sandwalk/agent-ui-core'

/**
 * Pure operations on the tiling tree (Warp / iTerm2 model). Each
 * function returns a new tree — no in-place mutation — so React can
 * treat state updates as immutable and re-render predictably.
 *
 * FAS-107 generalizes leaves to any pane-able item (chat or terminal
 * today, files/preview later). The chat-only API is preserved as a thin
 * wrapper over the mixed-type primitives so existing callers keep
 * working without touching every call site.
 */

export type SplitDirection = 'horizontal' | 'vertical'

/** True when the node represents a single pane (any kind), false when it is a branch. */
export function isLeafPane(
  node: PaneNode
): node is
  | { type: 'chat'; chatId: string }
  | { type: 'terminal'; terminalId: string }
  | { type: 'ref'; ref: WorkspaceItemRef } {
  return node.type === 'chat' || node.type === 'terminal' || node.type === 'ref'
}

/**
 * Extract the typed item reference from a leaf pane, or null when the
 * node is a branch (or a legacy chat leaf with an empty id, which the
 * builder uses as a sentinel for "no chat yet").
 */
export function leafItemRef(node: PaneNode): WorkspaceItemRef | null {
  if (node.type === 'chat') {
    return node.chatId ? { kind: 'chat', id: node.chatId } : null
  }
  if (node.type === 'terminal') {
    return node.terminalId ? { kind: 'terminal', id: node.terminalId } : null
  }
  if (node.type === 'ref') return node.ref
  return null
}

/** Just the id, without kind. Handy when the caller already knows the kind or doesn't care. */
export function leafItemId(node: PaneNode): string | null {
  const ref = leafItemRef(node)
  return ref?.id ?? null
}

/**
 * Build the default tree for a group: a single horizontal branch whose
 * children are the given items in order, with equal ratios. When there
 * is only one item, we return a bare leaf.
 */
export function buildDefaultTree(chatIds: string[]): PaneNode {
  if (chatIds.length === 0) {
    return { type: 'chat', chatId: '' }
  }
  if (chatIds.length === 1) {
    return idToLeaf(chatIds[0])
  }
  return {
    type: 'branch',
    direction: 'horizontal',
    ratios: equalRatios(chatIds.length),
    children: chatIds.map(idToLeaf)
  }
}

/** Same as `buildDefaultTree` but for mixed-type item refs (FAS-107). */
export function buildDefaultTreeFromRefs(refs: WorkspaceItemRef[]): PaneNode {
  if (refs.length === 0) return { type: 'chat', chatId: '' }
  if (refs.length === 1) return refToLeaf(refs[0])
  return {
    type: 'branch',
    direction: 'horizontal',
    ratios: equalRatios(refs.length),
    children: refs.map(refToLeaf)
  }
}

function refToLeaf(ref: WorkspaceItemRef): PaneNode {
  if (ref.kind === 'chat') return { type: 'chat', chatId: ref.id }
  return { type: 'terminal', terminalId: ref.id }
}

/**
 * Build a leaf from a plain id, inferring the kind from its prefix.
 * FAS-107: terminals are `term_*`; everything else is treated as a chat.
 * Used by `buildDefaultTree` / `splitPane` / `reconcileTree` so the tree
 * always carries the right leaf type — the renderer no longer has to
 * discriminate chat vs terminal by looking up the id in a live list.
 */
function idToLeaf(id: string): PaneNode {
  return id.startsWith('term_')
    ? { type: 'terminal', terminalId: id }
    : { type: 'chat', chatId: id }
}

export function equalRatios(n: number): number[] {
  if (n <= 0) return []
  const share = 1 / n
  return Array.from({ length: n }, () => share)
}

/**
 * Collect chat ids in tree traversal order. Terminal leaves are skipped
 * to keep the return shape compatible with existing chat-only callers.
 * New callers should prefer `extractItemRefs` for mixed-type trees.
 */
export function extractChatIds(node: PaneNode): string[] {
  return extractItemRefs(node)
    .filter(ref => ref.kind === 'chat')
    .map(ref => ref.id)
}

/** Collect every leaf's typed reference in traversal order (FAS-107). */
export function extractItemRefs(node: PaneNode): WorkspaceItemRef[] {
  if (node.type === 'branch') return node.children.flatMap(extractItemRefs)
  const ref = leafItemRef(node)
  return ref ? [ref] : []
}

/**
 * Split the pane holding `targetId` in the requested direction and
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
  // FAS-107: infer the kind from the id prefix so a `term_*` insertion
  // becomes a terminal leaf (not a chat leaf that would then crash the
  // renderer when looked up as a session).
  const newRef: WorkspaceItemRef = newChatId.startsWith('term_')
    ? { kind: 'terminal', id: newChatId }
    : { kind: 'chat', id: newChatId }
  return splitPaneWithRef(tree, targetChatId, direction, newRef, side)
}

/**
 * Mixed-type variant of `splitPane`. `targetId` matches any leaf (chat
 * or terminal); `newRef` becomes the newly inserted leaf regardless of
 * kind. Callers building a Split-with-Terminal action from the picker
 * hit this path.
 */
export function splitPaneWithRef(
  tree: PaneNode,
  targetId: string,
  direction: SplitDirection,
  newRef: WorkspaceItemRef,
  side: 'before' | 'after' = 'after'
): PaneNode {
  if (isLeafPane(tree)) {
    if (leafItemId(tree) !== targetId) return tree
    const newLeaf = refToLeaf(newRef)
    const children = side === 'after' ? [tree, newLeaf] : [newLeaf, tree]
    return {
      type: 'branch',
      direction,
      ratios: equalRatios(2),
      children
    }
  }
  return splitInBranch(tree, targetId, direction, newRef, side)
}

function splitInBranch(
  branch: PaneNode & { type: 'branch' },
  targetId: string,
  direction: SplitDirection,
  newRef: WorkspaceItemRef,
  side: 'before' | 'after'
): PaneNode {
  const index = branch.children.findIndex(child => containsItem(child, targetId))
  if (index === -1) return branch
  const child = branch.children[index]
  // The target lives deeper — recurse; the branch stays unchanged
  // structurally, only the affected child is replaced.
  if (child.type === 'branch' && !isLeafOf(child, targetId)) {
    const newChild = splitInBranch(child, targetId, direction, newRef, side)
    const nextChildren = branch.children.slice()
    nextChildren[index] = newChild
    return { ...branch, children: nextChildren }
  }
  const newLeaf = refToLeaf(newRef)
  // Same direction as the parent branch → insert as a sibling with
  // equal ratios so the split feels balanced instead of squishing the
  // existing panes.
  if (branch.direction === direction) {
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
  // requested direction.
  const wrapperChildren = side === 'after' ? [child, newLeaf] : [newLeaf, child]
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

function containsItem(node: PaneNode, itemId: string): boolean {
  if (node.type === 'branch') {
    return node.children.some(c => containsItem(c, itemId))
  }
  return leafItemId(node) === itemId
}

function isLeafOf(node: PaneNode, itemId: string): boolean {
  return isLeafPane(node) && leafItemId(node) === itemId
}

/**
 * Remove the pane holding `itemId`. When a branch is left with a single
 * child, the child bubbles up and replaces the branch (Warp's collapse
 * behaviour). Returns null when the whole tree becomes empty — the
 * caller decides what to do (dissolve the group, usually).
 *
 * Works for any leaf kind. The parameter name `chatId` is kept for
 * backwards compatibility with existing call sites; semantically it is
 * an item id.
 */
export function closePane(tree: PaneNode, chatId: string): PaneNode | null {
  if (isLeafPane(tree)) {
    return leafItemId(tree) === chatId ? null : tree
  }
  const nextChildren: PaneNode[] = []
  for (const child of tree.children) {
    const kept = closePane(child, chatId)
    if (kept !== null) nextChildren.push(kept)
  }
  if (nextChildren.length === 0) return null
  if (nextChildren.length === 1) return nextChildren[0]
  const keptRatios = filterKeptRatios(tree, chatId)
  const ratios =
    keptRatios.length === nextChildren.length
      ? renormalize(keptRatios)
      : equalRatios(nextChildren.length)
  return { ...tree, ratios, children: nextChildren }
}

function filterKeptRatios(
  branch: PaneNode & { type: 'branch' },
  itemId: string
): number[] {
  const result: number[] = []
  branch.children.forEach((child, index) => {
    const kept = closePane(child, itemId)
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
 *
 * Non-chat leaves (terminals) are preserved untouched — reconcileTree
 * only prunes/adds chat leaves. To reconcile against a mixed-type list
 * of refs, use `reconcileTreeFromRefs`.
 */
export function reconcileTree(tree: PaneNode, chatIds: string[]): PaneNode {
  const known = new Set(chatIds)
  // FAS-107: use the item-based prune so a terminal leaf whose id lives
  // in `chatIds` is preserved instead of dropped as an "unknown chat".
  let current: PaneNode | null = pruneUnknownItemIds(tree, known)
  if (current === null) return buildDefaultTree(chatIds)
  const existing = new Set(
    extractItemRefs(current).map(ref => ref.id)
  )
  const missing = chatIds.filter(id => !existing.has(id))
  for (const id of missing) {
    // Infer the leaf kind from the id prefix so a `term_*` id is added
    // as a terminal leaf, never as a chat pointing at a nonexistent chat.
    current = appendLeafAtRoot(current, idToLeaf(id))
  }
  return current
}

function pruneUnknownItemIds(
  tree: PaneNode,
  knownIds: Set<string>
): PaneNode | null {
  if (isLeafPane(tree)) {
    const id = leafItemId(tree)
    if (!id) return null
    return knownIds.has(id) ? tree : null
  }
  return pruneBranch(tree, node => pruneUnknownItemIds(node, knownIds))
}

/** Mixed-type variant of `reconcileTree` (FAS-107). */
export function reconcileTreeFromRefs(
  tree: PaneNode,
  refs: WorkspaceItemRef[]
): PaneNode {
  const known = new Map(refs.map(ref => [ref.id, ref.kind] as const))
  let current: PaneNode | null = pruneUnknownItems(tree, known)
  if (current === null) return buildDefaultTreeFromRefs(refs)
  const existingIds = new Set(extractItemRefs(current).map(r => r.id))
  const missing = refs.filter(ref => !existingIds.has(ref.id))
  for (const ref of missing) {
    current = appendLeafAtRoot(current, refToLeaf(ref))
  }
  return current
}

function pruneUnknownChats(tree: PaneNode, known: Set<string>): PaneNode | null {
  if (tree.type === 'chat') return known.has(tree.chatId) ? tree : null
  // Terminals & typed refs are preserved regardless of the chat-only known set.
  if (tree.type === 'terminal' || tree.type === 'ref') return tree
  return pruneBranch(tree, node => pruneUnknownChats(node, known))
}

function pruneUnknownItems(
  tree: PaneNode,
  known: Map<string, WorkspaceItemRef['kind']>
): PaneNode | null {
  if (isLeafPane(tree)) {
    const ref = leafItemRef(tree)
    if (!ref) return null
    const kind = known.get(ref.id)
    if (kind && kind === ref.kind) return tree
    return null
  }
  return pruneBranch(tree, node => pruneUnknownItems(node, known))
}

function pruneBranch(
  branch: PaneNode & { type: 'branch' },
  visit: (node: PaneNode) => PaneNode | null
): PaneNode | null {
  const nextChildren: PaneNode[] = []
  const nextRatios: number[] = []
  branch.children.forEach((child, i) => {
    const kept = visit(child)
    if (kept !== null) {
      nextChildren.push(kept)
      nextRatios.push(branch.ratios[i] ?? 0)
    }
  })
  if (nextChildren.length === 0) return null
  if (nextChildren.length === 1) return nextChildren[0]
  return { ...branch, children: nextChildren, ratios: renormalize(nextRatios) }
}

function appendLeafAtRoot(tree: PaneNode, leaf: PaneNode): PaneNode {
  if (isLeafPane(tree)) {
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
  // Root is a vertical branch — wrap it and add the new pane to the right.
  return {
    type: 'branch',
    direction: 'horizontal',
    ratios: equalRatios(2),
    children: [tree, leaf]
  }
}
