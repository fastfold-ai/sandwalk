import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { TerminalSession } from '@sandwalk/agent-ui-core'
import { SquareTerminal } from 'lucide-react'
import { type MouseEvent, useCallback } from 'react'

import { TerminalPanel } from '@/components/agents/TerminalPanel'
import { cn } from '@/lib/utils'

import type {
  PaneContextMenuDetail,
  PaneContextMenuHandlers
} from './ChatTilingContainer'
import type { SplitDirection } from '@/hooks/useChatTiling'

type TerminalLeafProps = {
  terminalId: string
  focused: boolean
  focusPanel: () => void
  client: LocalAgentClient
  terminals: TerminalSession[]
  onSplit: (
    terminalId: string,
    direction: SplitDirection,
    side: 'before' | 'after'
  ) => void
  onClose: (terminalId: string) => void
  canClose: boolean
}

/**
 * Terminal-as-pane leaf (FAS-107). Peer of `ChatLeaf` inside the tiling
 * tree. Wraps the existing `TerminalPanel` with the same focus ring +
 * right-click split menu behaviour as chat panes, so users can split,
 * close, and resize a terminal like any other item.
 *
 * The focused ring uses an orange accent (matching the picker's
 * "New terminal" card in Fase 4) to distinguish where keystrokes will
 * land — chat = blue, terminal = orange. Precedent: JetBrains coloured
 * tool-window stripes, Warp green in-progress blocks.
 */
export function TerminalLeaf({
  terminalId,
  focused,
  focusPanel,
  client,
  terminals,
  onSplit,
  onClose,
  canClose
}: TerminalLeafProps) {
  const terminal = terminals.find(t => t.id === terminalId) ?? null
  const title = terminal?.title ?? 'Terminal'

  const onContextMenu = useCallback(
    (event: MouseEvent) => {
      event.preventDefault()
      event.stopPropagation()
      const handlers: PaneContextMenuHandlers = {
        onSplitLeft: () => onSplit(terminalId, 'horizontal', 'before'),
        onSplitRight: () => onSplit(terminalId, 'horizontal', 'after'),
        onSplitUp: () => onSplit(terminalId, 'vertical', 'before'),
        onSplitDown: () => onSplit(terminalId, 'vertical', 'after'),
        onClose: canClose ? () => onClose(terminalId) : null
      }
      window.dispatchEvent(
        new CustomEvent<PaneContextMenuDetail>('sandwalk:pane-context-menu', {
          detail: {
            chatId: terminalId,
            x: event.clientX,
            y: event.clientY,
            handlers
          }
        })
      )
    },
    [terminalId, onSplit, onClose, canClose]
  )

  return (
    <div
      className={cn(
        'bg-background relative flex h-full min-w-0 flex-col overflow-hidden rounded-lg border transition-[border-color] duration-300 ease-out',
        // Same hover-ring pattern as ChatLeaf — pseudo-element sits
        // inside the box so `overflow: hidden` doesn't clip it (per
        // CSS 2.2 §11.1.1 outline would be clipped). Orange border
        // when focused so the type is visible at a glance.
        "after:pointer-events-none after:absolute after:inset-0 after:rounded-[inherit] after:border-2 after:border-transparent after:content-[''] after:z-20",
        focused
          ? 'border-orange-500/60'
          : 'border-border/50 hover:after:border-muted-foreground/40'
      )}
      onContextMenu={onContextMenu}
      onMouseDownCapture={focusPanel}
      onFocusCapture={focusPanel}
      aria-label={`Terminal pane: ${title}`}
    >
      <div className="border-border/50 flex h-9 shrink-0 items-center gap-2 border-b px-3">
        <SquareTerminal
          aria-hidden
          className={cn(
            'size-3.5',
            focused ? 'text-orange-500' : 'text-muted-foreground'
          )}
        />
        <span
          className={cn(
            'truncate text-[13px]',
            focused ? 'text-foreground' : 'text-muted-foreground'
          )}
        >
          {title}
        </span>
      </div>
      <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
        <TerminalPanel
          client={client}
          sessionId={terminalId}
          visible
          autoCreateOnEmpty
          className="border-t-0"
        />
      </div>
    </div>
  )
}
