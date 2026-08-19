import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  PaneNode,
  SessionGroup
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
import { SplitChatPickerPanel } from '@/components/agents/SplitChatPickerPanel'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import {
  buildDefaultTree,
  reconcileTree,
  setBranchRatios,
  type SplitDirection,
  splitPane} from '@/hooks/useChatTiling'
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
  }
  onLayoutChange: (fingerprint: string, tree: PaneNode) => void
  onCloseChat: (chatId: string) => void
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
  onCloseChat
}: ChatTilingContainerProps) {
  const chatIds = group.chatIds
  const activeChatId = group.activeChatId
  const isPending = Boolean(group.isPending)
  const fingerprint = useMonitorFingerprint()

  const [pickerRequest, setPickerRequest] = useState<PickerRequest | null>(null)

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
      onCloseChat(chatId)
    },
    [onCloseChat]
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
      setPickerRequest(null)
    },
    [pickerRequest, pickerContext, isPending, baseTree, commitTree]
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
        renderLeaf={(chatId, focused, focusPanel) =>
          chatId === PICKER_CELL_ID ? (
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
          ) : (
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
            key={paneKey(child, i)}
            child={child}
            i={i}
            path={path}
            isLast={isLast}
            defaultSize={(node.ratios[i] ?? 1 / node.children.length) * 100}
            direction={node.direction}
            onBranchLayout={onBranchLayout}
            renderLeaf={renderLeaf}
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
  activeChatId: string
  pickerActive: boolean
  onFocus: (chatId: string) => void
}) {
  return (
    <>
      <ResizablePanel
        id={`pane-${paneKey(child, i)}`}
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

function paneKey(node: PaneNode, index: number): string {
  if (node.type === 'chat') return `chat-${node.chatId}-${index}`
  return `branch-${node.direction}-${index}-${node.children.length}`
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
  const headerProps = buildHeaderProps(chatId, focused, focusPanel)
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
  if (!pickerContext) return null
  return (
    <div className="bg-background border-border/50 relative flex h-full min-w-0 flex-col overflow-hidden rounded-lg border">
      <button
        type="button"
        onClick={onCancel}
        aria-label="Cancel"
        className="text-muted-foreground hover:text-foreground hover:bg-muted absolute right-2 top-2 z-10 inline-flex size-7 items-center justify-center rounded-md"
      >
        <X className="size-4" />
      </button>
      <div className="flex h-full min-h-0 min-w-0 flex-col items-center justify-center gap-3 overflow-hidden p-4">
        <h2 className="text-foreground shrink-0 text-center text-[14px] font-medium">
          Pick a chat for the split
        </h2>
        <SplitChatPickerPanel
          client={pickerContext.client}
          sourceChatId={sourceChatId}
          activeProjectId={pickerContext.activeProjectId}
          projects={projects}
          allTabGroups={pickerContext.allTabGroups}
          cachedSessions={sessions}
          onPick={onPick}
        />
      </div>
    </div>
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
