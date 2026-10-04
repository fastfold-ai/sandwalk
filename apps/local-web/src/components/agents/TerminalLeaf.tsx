import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, TerminalSession } from '@sandwalk/agent-ui-core'
import { type MouseEvent, useCallback } from 'react'

import { TerminalPlaceholder } from '@/components/agents/terminal-layer'
import { TerminalSplitPanelHeader } from '@/components/agents/TerminalSplitPanelHeader'
import type { PaneSplitDirection, PaneSplitTarget } from '@/lib/pane-split'
import { cn } from '@/lib/utils'

import type {
  PaneContextMenuDetail,
  PaneContextMenuHandlers
} from './ChatTilingContainer'

type TerminalLeafProps = {
  terminalId: string
  focused: boolean
  focusPanel: () => void
  client: LocalAgentClient
  terminals: TerminalSession[]
  onSplitPane?: (
    terminalId: string,
    direction: PaneSplitDirection,
    target: PaneSplitTarget
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
  onSplitPane,
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
      if ('stopPropagation' in event) event.stopPropagation()
      const handlers: PaneContextMenuHandlers = {
        onSplitPane: (id, direction, target) =>
          onSplitPane?.(id, direction, target),
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
    [terminalId, onSplitPane, onClose, canClose]
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
      onMouseDownCapture={event => {
        const target = event.target
        if (target instanceof Element && target.closest('[data-pane-action]')) {
          return
        }
        focusPanel()
      }}
      onFocusCapture={focusPanel}
      aria-label={`Terminal pane: ${terminal?.title ?? 'Terminal'}`}
      data-pane-id={terminalId}
      data-pane-kind="terminal"
      data-pane-focused={focused ? 'true' : undefined}
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
        onSplitPane={onSplitPane}
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
