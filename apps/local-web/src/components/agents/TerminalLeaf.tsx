import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, TerminalSession } from '@sandwalk/agent-ui-core'
import { type MouseEvent, useCallback } from 'react'

import { TerminalPlaceholder } from '@/components/agents/terminal-layer'
import { TerminalSplitPanelHeader } from '@/components/agents/TerminalSplitPanelHeader'
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
  /**
   * FAS-107 P3: parity with ChatLeaf — the panel header exposes the
   * same actions per pane (rename / pin / color / move to project /
   * archive / split L/R/U/D / close pane). Callbacks are prop-drilled
   * from the shell via `ChatTilingContainer`.
   */
  projects?: AgentProject[]
  onRename?: (terminalId: string) => void
  onTogglePin?: (terminalId: string) => void
  onToggleArchive?: (terminalId: string) => void
  onMoveToProject?: (
    terminalId: string,
    projectId: string | null
  ) => void | Promise<void>
}

/**
 * Terminal-as-pane leaf (FAS-107). Peer of `ChatLeaf` inside the tiling
 * tree. Wraps `TerminalPanel` with a header that mirrors
 * `ChatSplitPanelHeader` (same 52px, same focused/unfocused states,
 * same ⋯ menu structure) — see `TerminalSplitPanelHeader` for the
 * action set.
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
  // FAS-107 W1: `client` ya no se consume acá — el xterm vive en el
  // portal host (ver terminal-layer/). Prefixed con `_` para señalar
  // que la prop se mantiene en la firma sólo por compat con callers.
  client: _client,
  terminals,
  onSplit,
  onClose,
  canClose,
  projects,
  onRename,
  onTogglePin,
  onToggleArchive,
  onMoveToProject
}: TerminalLeafProps) {
  const terminal = terminals.find(t => t.id === terminalId) ?? null

  const onContextMenu = useCallback(
    (event: MouseEvent | globalThis.MouseEvent) => {
      event.preventDefault()
      // El wrapper React necesita stopPropagation para no burbujear a
      // ancestros que también manejan contextmenu; para el evento nativo
      // que viene del portal-host, stopPropagation es un no-op del DOM.
      if ('stopPropagation' in event) event.stopPropagation()
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
      aria-label={`Terminal pane: ${terminal?.title ?? 'Terminal'}`}
    >
      <TerminalSplitPanelHeader
        terminal={terminal}
        focused={focused}
        onFocusPanel={focusPanel}
        projects={projects ?? []}
        onRename={onRename}
        onTogglePin={onTogglePin}
        onToggleArchive={onToggleArchive}
        onMoveToProject={onMoveToProject}
        onRemoveFromSplit={canClose ? id => onClose(id) : undefined}
        onSplitLeft={id => onSplit(id, 'horizontal', 'before')}
        onSplitRight={id => onSplit(id, 'horizontal', 'after')}
        onSplitUp={id => onSplit(id, 'vertical', 'before')}
        onSplitDown={id => onSplit(id, 'vertical', 'after')}
      />
      {/* FAS-107 W1: el xterm ya no vive acá. Vive en un layer flotante
          (via portal) que se posiciona sobre este placeholder. Así el
          buffer sobrevive a cambios de tab/split sin conflicto entre
          React reconcile y xterm DOM mutations. Ver terminal-layer/. */}
      <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
        <TerminalPlaceholder
          terminalId={terminalId}
          onFocus={focusPanel}
          onContextMenu={onContextMenu}
        />
      </div>
    </div>
  )
}
