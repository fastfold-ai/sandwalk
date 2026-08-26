import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  PaneNode,
  SessionGroup,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import { X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  ChatSplitPanelHeader,
  type ChatSplitPanelHeaderProps
} from '@/components/agents/ChatSplitPanelHeader'
import {
  SessionChatMount,
  type SessionChatMountProps
} from '@/components/agents/SessionChatMount'
import { SplitPicker } from '@/components/agents/SplitPicker'
import { TerminalLeaf } from '@/components/agents/TerminalLeaf'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import {
  buildDefaultTree,
  extractChatIds,
  isLeafPane,
  leafItemId,
  reconcileTree,
  setBranchRatios,
  type SplitDirection,
  splitPane
} from '@/hooks/useChatTiling'
import { useMonitorFingerprint } from '@/lib/monitor-fingerprint'
import { cn } from '@/lib/utils'

/**
 * Reserved chatId for the transient picker pane. Real chat ids are UUIDs
 * or `draft_*`, so this prefix can never collide.
 */
const PICKER_CELL_ID = '__picker__'

type PickerRequest = {
  targetChatId: string
  direction: SplitDirection
  side: 'before' | 'after'
}

export type ChatTilingContainerProps = {
  group: SessionGroup
  sessions: AgentSession[]
  buildMountProps: (
    chatId: string
  ) => Omit<SessionChatMountProps, 'perSessionArgs'> & {
    perSessionArgs: SessionChatMountProps['perSessionArgs']
  }
  onFocusChat: (chatId: string) => void
  buildHeaderProps: (
    chatId: string,
    focused: boolean,
    onFocusPanel: () => void
  ) => ChatSplitPanelHeaderProps
  projects: AgentProject[]
  pickerContext?: {
    client: LocalAgentClient
    activeProjectId: string | null
    allTabGroups: SessionGroup[]
    onPickPartner: (chatId: string) => void
    onCancelPending: () => void
    onAddChat: (chatId: string) => void
    /**
     * Create a blank new chat and return its id. The container feeds the
     * id back through the shared `handlePicked` flow (promote pending /
     * add-to-group + close picker + update tree), so the caller stays
     * uninvolved with layout side effects. Return `null` on failure to
     * keep the picker open for retry.
     */
    onPickNewChat?: () => Promise<string | null>
    /** Same contract as `onPickNewChat` but for terminals (FAS-107). */
    onPickTerminal?: () => Promise<string | null>
  }
  onLayoutChange: (fingerprint: string, tree: PaneNode) => void
  onCloseChat: (chatId: string) => void
  /**
   * Terminal-as-first-class-item support (FAS-107). Populate to enable
   * rendering `type:'terminal'` leaves alongside chat leaves. Leaving
   * these undefined keeps the container chat-only, matching pre-107
   * behaviour.
   */
  terminals?: TerminalSession[]
  terminalClient?: LocalAgentClient
  onCloseTerminal?: (terminalId: string) => void
  /**
   * FAS-107 P3: parity with chat panes — the terminal split header
   * exposes rename / pin / archive / move to project. Callbacks are
   * optional; when absent the corresponding menu items don't render.
   */
  onRenameTerminal?: (terminalId: string) => void
  onToggleTerminalOrganizeLabel?: (
    terminalId: string,
    label: 'pinned' | 'archive'
  ) => void | Promise<void>
  onMoveTerminalToProject?: (
    terminalId: string,
    projectId: string | null
  ) => void | Promise<void>
}

/**
 * Tiling container inspired by Warp. Renders `group.layout` as a
 * recursive tree of `ResizablePanelGroup`s — leaves are chat panes,
 * branches are horizontal/vertical splits with resizable dividers.
 * Splits never overlap, never leave gaps, and always fill 100% of the
 * canvas.
 */
export function ChatTilingContainer({
  group,
  sessions,
  buildMountProps,
  onFocusChat,
  buildHeaderProps,
  projects,
  pickerContext,
  onLayoutChange,
  onCloseChat,
  terminals,
  terminalClient,
  onCloseTerminal,
  onRenameTerminal,
  onToggleTerminalOrganizeLabel,
  onMoveTerminalToProject
}: ChatTilingContainerProps) {
  const chatIds = group.itemIds
  const activeChatId = group.activeChatId
  const isPending = Boolean(group.isPending)
  const fingerprint = useMonitorFingerprint()

  const [pickerRequest, setPickerRequest] = useState<PickerRequest | null>(null)

  // Reset the picker whenever the active group changes — otherwise a
  // half-opened picker in group A survives a jump to group B and back,
  // pointing at a target chat that may not exist in the new tree.
  useEffect(() => {
    setPickerRequest(null)
  }, [group.id])

  // Also drop the picker if its target chat was removed from the group
  // by any code path (server-side prune, close-pane, etc.).
  useEffect(() => {
    if (
      pickerRequest &&
      pickerRequest.targetChatId !== PICKER_CELL_ID &&
      !chatIds.includes(pickerRequest.targetChatId)
    ) {
      setPickerRequest(null)
    }
  }, [chatIds, pickerRequest])

  // Pending groups always render as a two-pane split: the source chat on
  // one side and the picker on the other. Once the user picks, the tree
  // stays two-pane and the picker turns into a real chat.
  useEffect(() => {
    if (isPending && chatIds.length === 1 && !pickerRequest) {
      setPickerRequest({
        targetChatId: chatIds[0],
        direction: 'horizontal',
        side: 'after'
      })
    }
    if (!isPending && pickerRequest?.targetChatId === PICKER_CELL_ID) {
      setPickerRequest(null)
    }
  }, [isPending, chatIds, pickerRequest])

  // Reconciled base tree — persisted layout, patched to match the current
  // chatIds list. Falls back to the default row when the group has no
  // saved layout for this monitor.
  const baseTree = useMemo(() => {
    const saved = group.layout?.perMonitor?.[fingerprint]
    if (saved) return reconcileTree(saved, chatIds)
    return buildDefaultTree(chatIds)
  }, [group.layout, fingerprint, chatIds])

  // The tree we actually render. When a picker is showing we splice in a
  // transient placeholder pane so it participates in the tiling.
  const renderTree = useMemo(() => {
    if (!pickerRequest) return baseTree
    return splitPane(
      baseTree,
      pickerRequest.targetChatId,
      pickerRequest.direction,
      PICKER_CELL_ID,
      pickerRequest.side
    )
  }, [baseTree, pickerRequest])

  const commitTree = useCallback(
    (nextTree: PaneNode) => {
      // Never persist a tree that still holds the picker placeholder.
      const cleaned = stripPicker(nextTree)
      if (!cleaned) return
      onLayoutChange(fingerprint, cleaned)
    },
    [fingerprint, onLayoutChange]
  )

  const handleSplit = useCallback(
    (
      chatId: string,
      direction: SplitDirection,
      side: 'before' | 'after' = 'after'
    ) => {
      if (!pickerContext) return
      setPickerRequest({ targetChatId: chatId, direction, side })
    },
    [pickerContext]
  )

  const handleClose = useCallback(
    (chatId: string) => {
      // Before removing the pane, move focus to a surviving sibling so
      // the split doesn't end up with `activeChatId` pointing at a chat
      // that no longer exists. Pick the previous chat in tree order, or
      // fall back to the next one when the closed pane was first.
      const ids = extractChatIds(baseTree)
      const idx = ids.indexOf(chatId)
      const nextFocus =
        idx > 0 ? ids[idx - 1] : idx === 0 && ids.length > 1 ? ids[1] : null
      if (nextFocus && nextFocus !== chatId) onFocusChat(nextFocus)
      onCloseChat(chatId)
    },
    [baseTree, onFocusChat, onCloseChat]
  )

  const handleFocus = useCallback(
    (chatId: string) => {
      if (chatId !== activeChatId) onFocusChat(chatId)
    },
    [activeChatId, onFocusChat]
  )

  const handleBranchLayout = useCallback(
    (path: number[], sizesPct: number[]) => {
      const ratios = sizesPct.map(pct => pct / 100)
      // `onLayout` from react-resizable-panels fires on every mount and
      // every window resize, not just when the user drags a divider.
      // Bail out if the new ratios are within 0.1% of the current ones —
      // otherwise every mount/resize would rewrite `group.layout` to
      // localStorage even though nothing meaningful changed.
      const currentRatios = getBranchRatiosAt(baseTree, path)
      if (currentRatios && ratiosAreClose(currentRatios, ratios)) return
      const next = setBranchRatios(baseTree, path, ratios)
      if (next === baseTree) return
      commitTree(next)
    },
    [baseTree, commitTree]
  )

  const handlePicked = useCallback(
    (pickedChatId: string) => {
      if (!pickerRequest || !pickerContext) return
      if (isPending) {
        pickerContext.onPickPartner(pickedChatId)
      } else {
        pickerContext.onAddChat(pickedChatId)
      }
      const nextTree = splitPane(
        baseTree,
        pickerRequest.targetChatId,
        pickerRequest.direction,
        pickedChatId,
        pickerRequest.side
      )
      commitTree(nextTree)
      // X4.4 · autofocus al pane recién agregado. Antes el active del
      // grupo se quedaba en el pane original y el user tenía que hacer
      // click sobre el nuevo para escribir. Comparalo con `handleClose`
      // que ya llama `onFocusChat(nextFocus)` al cerrar un pane.
      onFocusChat(pickedChatId)
      setPickerRequest(null)
    },
    [pickerRequest, pickerContext, isPending, baseTree, commitTree, onFocusChat]
  )

  const handleCancelPicker = useCallback(() => {
    if (isPending && pickerContext) {
      pickerContext.onCancelPending()
    }
    setPickerRequest(null)
  }, [isPending, pickerContext])

  // Global keyboard shortcuts (Warp-style).
  useEffect(() => {
    if (!pickerContext) return
    const handler = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey
      if (!meta) return
      // The embedded xterm terminal binds its own ⌘W/⌘D — if the user is
      // typing in a terminal pane the shortcut belongs to that widget,
      // not to the split view. Never fight over an event that already
      // has an owner.
      const active = document.activeElement
      if (active && active.closest('.xterm')) return
      const key = e.key.toLowerCase()
      if (key === 'd') {
        e.preventDefault()
        const target = activeChatId
        if (!target) return
        const direction: SplitDirection = e.shiftKey ? 'vertical' : 'horizontal'
        setPickerRequest({ targetChatId: target, direction, side: 'after' })
      } else if (key === 'w' && chatIds.length > 1) {
        // Never close the last chat with the shortcut — the user should
        // dissolve the group explicitly to avoid accidents.
        e.preventDefault()
        handleClose(activeChatId)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [pickerContext, activeChatId, chatIds.length, handleClose])

  if (chatIds.length === 0) return null

  return (
    <div className="relative flex h-full min-h-0 min-w-0 flex-1 overflow-hidden p-2">
      <PaneRenderer
        node={renderTree}
        path={[]}
        onBranchLayout={handleBranchLayout}
        renderLeaf={(chatId, focused, focusPanel) => {
          if (chatId === PICKER_CELL_ID) {
            return (
              <PickerLeaf
                sourceChatId={
                  pickerRequest?.targetChatId ?? chatIds[0] ?? ''
                }
                projects={projects}
                sessions={sessions}
                pickerContext={pickerContext}
                onPick={handlePicked}
                onCancel={handleCancelPicker}
              />
            )
          }
          // Terminals share the `chatIds` slot for backwards-compat with
          // the tab-groups store, but must render as terminal leaves.
          // Detect by matching against the fetched terminals list; if
          // matched, delegate to TerminalLeaf.
          const asTerminal = terminals?.find(t => t.id === chatId)
          if (asTerminal && terminalClient && onCloseTerminal) {
            return (
              <TerminalLeaf
                terminalId={chatId}
                focused={focused}
                focusPanel={focusPanel}
                client={terminalClient}
                terminals={terminals}
                onSplit={handleSplit}
                onClose={onCloseTerminal}
                canClose={chatIds.length > 1}
                projects={projects}
                onRename={onRenameTerminal}
                onTogglePin={
                  onToggleTerminalOrganizeLabel
                    ? id =>
                        void onToggleTerminalOrganizeLabel(id, 'pinned')
                    : undefined
                }
                onToggleArchive={
                  onToggleTerminalOrganizeLabel
                    ? id =>
                        void onToggleTerminalOrganizeLabel(id, 'archive')
                    : undefined
                }
                onMoveToProject={onMoveTerminalToProject}
              />
            )
          }
          return (
            <ChatLeaf
              chatId={chatId}
              focused={focused}
              focusPanel={focusPanel}
              sessions={sessions}
              buildMountProps={buildMountProps}
              buildHeaderProps={buildHeaderProps}
              onSplit={handleSplit}
              onClose={handleClose}
              canClose={chatIds.length > 1}
            />
          )
        }}
        renderTerminalLeaf={
          terminalClient && onCloseTerminal
            ? (terminalId, focused, focusPanel) => (
                <TerminalLeaf
                  terminalId={terminalId}
                  focused={focused}
                  focusPanel={focusPanel}
                  client={terminalClient}
                  terminals={terminals ?? []}
                  onSplit={handleSplit}
                  onClose={onCloseTerminal}
                  canClose={chatIds.length > 1}
                  projects={projects}
                  onRename={onRenameTerminal}
                  onTogglePin={
                    onToggleTerminalOrganizeLabel
                      ? id =>
                          void onToggleTerminalOrganizeLabel(id, 'pinned')
                      : undefined
                  }
                  onToggleArchive={
                    onToggleTerminalOrganizeLabel
                      ? id =>
                          void onToggleTerminalOrganizeLabel(id, 'archive')
                      : undefined
                  }
                  onMoveToProject={onMoveTerminalToProject}
                />
              )
            : undefined
        }
        activeChatId={activeChatId}
        pickerActive={Boolean(pickerRequest)}
        onFocus={handleFocus}
      />
    </div>
  )
}

function stripPicker(node: PaneNode): PaneNode | null {
  if (node.type === 'chat') {
    return node.chatId === PICKER_CELL_ID ? null : node
  }
  // Terminal & typed-ref leaves are never the picker sentinel — keep as-is.
  if (node.type === 'terminal' || node.type === 'ref') return node
  const nextChildren: PaneNode[] = []
  const nextRatios: number[] = []
  node.children.forEach((child, i) => {
    const kept = stripPicker(child)
    if (kept !== null) {
      nextChildren.push(kept)
      nextRatios.push(node.ratios[i] ?? 0)
    }
  })
  if (nextChildren.length === 0) return null
  if (nextChildren.length === 1) return nextChildren[0]
  const sum = nextRatios.reduce((a, r) => a + r, 0)
  const normalized =
    sum > 0
      ? nextRatios.map(r => r / sum)
      : nextChildren.map(() => 1 / nextChildren.length)
  return { ...node, children: nextChildren, ratios: normalized }
}

/**
 * Recursive renderer: a branch turns into a `ResizablePanelGroup` and a
 * leaf turns into a `ResizablePanel` holding either a chat mount or the
 * picker. `path` accumulates child indices from the root so the caller
 * can identify which branch was resized.
 */
function PaneRenderer({
  node,
  path,
  onBranchLayout,
  renderLeaf,
  renderTerminalLeaf,
  activeChatId,
  pickerActive,
  onFocus
}: {
  node: PaneNode
  path: number[]
  onBranchLayout: (path: number[], sizesPct: number[]) => void
  renderLeaf: (
    chatId: string,
    focused: boolean,
    focusPanel: () => void
  ) => React.ReactNode
  renderTerminalLeaf?: (
    terminalId: string,
    focused: boolean,
    focusPanel: () => void
  ) => React.ReactNode
  activeChatId: string
  pickerActive: boolean
  onFocus: (chatId: string) => void
}) {
  if (node.type === 'chat') {
    const focused = node.chatId === activeChatId && !pickerActive
    return (
      <div
        className="h-full w-full"
        onMouseDownCapture={() => onFocus(node.chatId)}
        onFocusCapture={() => onFocus(node.chatId)}
      >
        {renderLeaf(node.chatId, focused, () => onFocus(node.chatId))}
      </div>
    )
  }
  if (node.type === 'terminal') {
    const focused = node.terminalId === activeChatId && !pickerActive
    // Fallback: if the container was mounted without terminal support,
    // just render an empty div so we don't crash on legacy layouts that
    // somehow contain a terminal leaf.
    if (!renderTerminalLeaf) return <div className="h-full w-full" />
    return (
      <div
        className="h-full w-full"
        onMouseDownCapture={() => onFocus(node.terminalId)}
        onFocusCapture={() => onFocus(node.terminalId)}
      >
        {renderTerminalLeaf(node.terminalId, focused, () =>
          onFocus(node.terminalId)
        )}
      </div>
    )
  }
  if (node.type === 'ref') {
    const id = node.ref.id
    const focused = id === activeChatId && !pickerActive
    if (node.ref.kind === 'terminal') {
      if (!renderTerminalLeaf) return <div className="h-full w-full" />
      return (
        <div
          className="h-full w-full"
          onMouseDownCapture={() => onFocus(id)}
          onFocusCapture={() => onFocus(id)}
        >
          {renderTerminalLeaf(id, focused, () => onFocus(id))}
        </div>
      )
    }
    return (
      <div
        className="h-full w-full"
        onMouseDownCapture={() => onFocus(id)}
        onFocusCapture={() => onFocus(id)}
      >
        {renderLeaf(id, focused, () => onFocus(id))}
      </div>
    )
  }
  return (
    <ResizablePanelGroup
      direction={node.direction}
      className="gap-1"
      onLayout={sizes => onBranchLayout(path, sizes)}
    >
      {node.children.map((child, i) => {
        const isLast = i === node.children.length - 1
        return (
          <PaneGroupSlot
            key={paneKey(child)}
            child={child}
            i={i}
            path={path}
            isLast={isLast}
            defaultSize={(node.ratios[i] ?? 1 / node.children.length) * 100}
            direction={node.direction}
            onBranchLayout={onBranchLayout}
            renderLeaf={renderLeaf}
            renderTerminalLeaf={renderTerminalLeaf}
            activeChatId={activeChatId}
            pickerActive={pickerActive}
            onFocus={onFocus}
          />
        )
      })}
    </ResizablePanelGroup>
  )
}

function PaneGroupSlot({
  child,
  i,
  path,
  isLast,
  defaultSize,
  direction,
  onBranchLayout,
  renderLeaf,
  renderTerminalLeaf,
  activeChatId,
  pickerActive,
  onFocus
}: {
  child: PaneNode
  i: number
  path: number[]
  isLast: boolean
  defaultSize: number
  direction: SplitDirection
  onBranchLayout: (path: number[], sizesPct: number[]) => void
  renderLeaf: (
    chatId: string,
    focused: boolean,
    focusPanel: () => void
  ) => React.ReactNode
  renderTerminalLeaf?: (
    terminalId: string,
    focused: boolean,
    focusPanel: () => void
  ) => React.ReactNode
  activeChatId: string
  pickerActive: boolean
  onFocus: (chatId: string) => void
}) {
  return (
    <>
      <ResizablePanel
        id={`pane-${paneKey(child)}`}
        order={i}
        defaultSize={defaultSize}
        minSize={5}
        className="min-w-0 min-h-0"
      >
        <PaneRenderer
          node={child}
          path={[...path, i]}
          onBranchLayout={onBranchLayout}
          renderLeaf={renderLeaf}
          renderTerminalLeaf={renderTerminalLeaf}
          activeChatId={activeChatId}
          pickerActive={pickerActive}
          onFocus={onFocus}
        />
      </ResizablePanel>
      {!isLast ? (
        <ResizableHandle
          withHandle={false}
          className={cn(
            'bg-transparent',
            direction === 'horizontal' ? 'w-1' : 'h-1'
          )}
        />
      ) : null}
    </>
  )
}

/**
 * React key generator for a pane. MUST be stable across renders even when
 * the pane's index inside its parent branch changes (e.g. a new sibling
 * is inserted to its left after a split). If we mixed the index in, React
 * would treat the same chat as a different element and remount its
 * SessionChatMount — killing SSE streams and scroll position.
 *
 * Leaves are keyed by `chatId` alone (unique inside a group). Branches
 * are keyed by their contents (direction + sorted chat ids of their
 * descendants), so a branch's identity survives adds/removes as long as
 * its "membership" hasn't changed.
 */
function paneKey(node: PaneNode): string {
  if (node.type === 'chat') return `chat-${node.chatId}`
  if (node.type === 'terminal') return `terminal-${node.terminalId}`
  if (node.type === 'ref') return `${node.ref.kind}-${node.ref.id}`
  const descendants = branchDescendantIds(node).sort().join('|')
  return `branch-${node.direction}-${descendants}`
}

function branchDescendantIds(node: PaneNode): string[] {
  if (isLeafPane(node)) {
    const id = leafItemId(node)
    return id ? [id] : []
  }
  return node.children.flatMap(branchDescendantIds)
}

/**
 * Look up the ratios array of the branch at `path`. Returns null when
 * the path is invalid or the target isn't a branch (leaf can't have
 * ratios). Used by `handleBranchLayout` to no-op layout callbacks that
 * only report the existing shape.
 */
function getBranchRatiosAt(node: PaneNode, path: number[]): number[] | null {
  let cursor: PaneNode = node
  for (const idx of path) {
    if (cursor.type !== 'branch') return null
    const child = cursor.children[idx]
    if (!child) return null
    cursor = child
  }
  return cursor.type === 'branch' ? cursor.ratios : null
}

/**
 * True when two ratio arrays are equivalent within 0.1% per slot. Guards
 * `onLayout` against no-op mount/resize floods.
 */
function ratiosAreClose(a: number[], b: number[], epsilon = 0.001): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) {
    if (Math.abs(a[i] - b[i]) > epsilon) return false
  }
  return true
}

function ChatLeaf({
  chatId,
  focused,
  focusPanel,
  sessions,
  buildMountProps,
  buildHeaderProps,
  onSplit,
  onClose,
  canClose
}: {
  chatId: string
  focused: boolean
  focusPanel: () => void
  sessions: AgentSession[]
  buildMountProps: ChatTilingContainerProps['buildMountProps']
  buildHeaderProps: ChatTilingContainerProps['buildHeaderProps']
  onSplit: (
    chatId: string,
    direction: SplitDirection,
    side: 'before' | 'after'
  ) => void
  onClose: (chatId: string) => void
  canClose: boolean
}) {
  const props = buildMountProps(chatId)
  const chatSession = sessions.find(s => s.id === chatId) || null
  // The parent-built header props don't know about the tiling tree, so
  // we inject the four split handlers here — they mirror the right-click
  // context menu entries and let ellipsis-menu users add panes without
  // discovering the right-click gesture. `onRemoveFromSplit` already
  // handles "Close pane" in that menu, so we don't duplicate it here.
  //
  // INVARIANT: this override is what makes `Split left/right/up/down`
  // appear in the ellipsis menu. The parent `buildSplitHeaderProps`
  // documents the same invariant — DO NOT drop this override without
  // also lifting the split handlers into the builder.
  const baseHeaderProps = buildHeaderProps(chatId, focused, focusPanel)
  const headerProps: ChatSplitPanelHeaderProps = {
    ...baseHeaderProps,
    onSplitLeft: (id: string) => onSplit(id, 'horizontal', 'before'),
    onSplitRight: (id: string) => onSplit(id, 'horizontal', 'after'),
    onSplitUp: (id: string) => onSplit(id, 'vertical', 'before'),
    onSplitDown: (id: string) => onSplit(id, 'vertical', 'after')
  }
  return (
    <div
      className={cn(
        'bg-background relative flex h-full min-w-0 flex-col overflow-hidden rounded-lg border transition-[border-color] duration-300 ease-out',
        // Hover ring lives on a dedicated `::after` pseudo-element,
        // not on `outline` — per CSS 2.2 §11.1.1 `overflow: hidden`
        // clips the outline, so a plain `hover:outline` never paints.
        // The pseudo sits inside the box (respecting overflow-hidden),
        // its own border draws at the inner edge, and `z-20` keeps it
        // above the transcript fade gradients and sticky headers that
        // otherwise occlude any inset ring/box-shadow.
        "after:pointer-events-none after:absolute after:inset-0 after:rounded-[inherit] after:border-2 after:border-transparent after:content-[''] after:z-20",
        focused
          ? 'border-primary/60'
          : 'border-border/50 hover:after:border-muted-foreground/40'
      )}
      onContextMenu={e => {
        // Right-click on the pane opens the split menu — this is the
        // primary Warp-style discovery path for adding chats.
        e.preventDefault()
        e.stopPropagation()
        openPaneContextMenu(chatId, e, {
          onSplitLeft: () => onSplit(chatId, 'horizontal', 'before'),
          onSplitRight: () => onSplit(chatId, 'horizontal', 'after'),
          onSplitUp: () => onSplit(chatId, 'vertical', 'before'),
          onSplitDown: () => onSplit(chatId, 'vertical', 'after'),
          onClose: canClose ? () => onClose(chatId) : null
        })
      }}
      aria-label={`Chat pane for ${chatSession?.title || 'session'}`}
    >
      <ChatSplitPanelHeader {...headerProps} />
      <div className="flex h-full min-w-0 flex-1 flex-col">
        <SessionChatMount {...props} splitMode={{ focused }} />
      </div>
    </div>
  )
}

function PickerLeaf({
  sourceChatId,
  projects,
  sessions,
  pickerContext,
  onPick,
  onCancel
}: {
  sourceChatId: string
  projects: AgentProject[]
  sessions: AgentSession[]
  pickerContext: ChatTilingContainerProps['pickerContext']
  onPick: (chatId: string) => void
  onCancel: () => void
}) {
  // Keyboard escape closes the whole picker — never falls back to
  // "return to step 1"; that path is reserved for the explicit Back
  // button so Esc keeps its "cancel the split" semantics.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.preventDefault()
      onCancel()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onCancel])
  if (!pickerContext) return null
  const ctxOnPickTerminal = pickerContext.onPickTerminal
  const ctxOnPickNewChat = pickerContext.onPickNewChat
  return (
    <SplitPicker
      client={pickerContext.client}
      sourceChatId={sourceChatId}
      activeProjectId={pickerContext.activeProjectId}
      projects={projects}
      allTabGroups={pickerContext.allTabGroups}
      cachedSessions={sessions}
      onPickChat={onPick}
      onPickNewChat={async () => {
        // Delegate to the app (creates the chat, does optimistic
        // state updates), then feed the id into the shared handlePicked
        // flow so pending/add + tree update + picker reset stay in one
        // place. If the app returned null (create failed), leave the
        // picker open so the user can retry.
        if (!ctxOnPickNewChat) {
          onCancel()
          return
        }
        const id = await ctxOnPickNewChat()
        if (id) onPick(id)
      }}
      onPickTerminal={async () => {
        if (!ctxOnPickTerminal) {
          onCancel()
          return
        }
        const id = await ctxOnPickTerminal()
        if (id) onPick(id)
      }}
      onCancel={onCancel}
    />
  )
}

/**
 * Tiny helper that dispatches a right-click on a pane through a shared
 * DOM-based context menu. Kept as a function (not JSX) because the menu
 * lives outside the component tree and reads its handlers from the last
 * event context.
 */
function openPaneContextMenu(
  chatId: string,
  event: React.MouseEvent,
  handlers: PaneContextMenuHandlers
) {
  window.dispatchEvent(
    new CustomEvent<PaneContextMenuDetail>('sandwalk:pane-context-menu', {
      detail: {
        chatId,
        x: event.clientX,
        y: event.clientY,
        handlers
      }
    })
  )
}

export type PaneContextMenuHandlers = {
  onSplitLeft: () => void
  onSplitRight: () => void
  onSplitUp: () => void
  onSplitDown: () => void
  onClose: (() => void) | null
}

export type PaneContextMenuDetail = {
  chatId: string
  x: number
  y: number
  handlers: PaneContextMenuHandlers
}

// The listener + menu component are exported from a sibling file so this
// file stays focused on the tiling logic; keep the module import here so
// the tree-shaker keeps them together.
export { PaneContextMenu } from './PaneContextMenu'
