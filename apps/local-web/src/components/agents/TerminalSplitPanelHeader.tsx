import type { AgentProject, TerminalSession } from '@sandwalk/agent-ui-core'
import { MoreVertical, Pin, SquareTerminal } from 'lucide-react'
import { useState } from 'react'

import { useSessionTabColors } from '@/components/agents/session-tab-colors'
import { TerminalActionsMenu } from '@/components/agents/TerminalActionsMenu'
import { TerminalTypeIcon } from '@/components/agents/TerminalTypeIcon'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import type { PaneSplitDirection, PaneSplitTarget } from '@/lib/pane-split'
import { cn } from '@/lib/utils'

/**
 * FAS-107 P3: peer of `ChatSplitPanelHeader` for terminal panes. Same
 * height, same layout, same look — just the actions that apply to a
 * terminal (no Files/Preview/CLI toggles, no Inspect chat, no Export).
 *
 * Doctrine: a terminal is a chat with a shell inside — the split-panel
 * header must offer the same "centro de mando" per pane so the user can
 * rename, move, pin, color, archive, convert, split and close the terminal
 * from the header without going to the sidebar.
 *
 * The ⋯ menu is the same `TerminalActionsMenu` the sidebar uses, inside a
 * Popover: Radix `DropdownMenuSub` flyouts open on pointer-move only, which
 * WebKit inside the Tauri window drops often enough that Split Down/Right
 * looked dead. `TabContextSubmenu` opens on click too.
 */
export type TerminalSplitPanelHeaderProps = {
  terminal: TerminalSession | null
  focused: boolean
  onFocusPanel: () => void
  projects: AgentProject[]
  onRename?: (terminalId: string) => void
  onTogglePin?: (terminalId: string) => void
  onToggleArchive?: (terminalId: string) => void
  onMoveToProject?: (
    terminalId: string,
    projectId: string | null
  ) => void | Promise<void>
  /** Removes the terminal from the split (close pane, not delete). */
  onRemoveFromSplit?: (terminalId: string) => void
  onSplitPane?: (
    terminalId: string,
    direction: PaneSplitDirection,
    target: PaneSplitTarget
  ) => void
}

export function TerminalSplitPanelHeader({
  terminal,
  focused,
  onFocusPanel: _onFocusPanel,
  projects,
  onRename,
  onTogglePin,
  onToggleArchive,
  onMoveToProject,
  onRemoveFromSplit,
  onSplitPane
}: TerminalSplitPanelHeaderProps) {
  const { tabColors, setTabColor } = useSessionTabColors()
  const [menuOpen, setMenuOpen] = useState(false)
  const title = terminal?.title || 'Terminal'
  const color = terminal ? tabColors[terminal.id] ?? null : null
  const isPinned = terminal?.organizeLabel === 'pinned'

  const closeThen = (fn?: () => void) => () => {
    setMenuOpen(false)
    fn?.()
  }

  return (
    <div
      className={cn(
        'flex h-[52px] shrink-0 items-center gap-2 border-b px-3 text-[12px] transition-colors',
        focused
          ? 'bg-muted/60 border-border/60 text-foreground'
          : 'bg-muted/25 border-border/30 text-muted-foreground'
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {terminal ? (
          <TerminalTypeIcon
            terminalId={terminal.id}
            className={cn(
              'size-4',
              focused ? 'text-foreground/80' : 'text-muted-foreground'
            )}
          />
        ) : (
          <SquareTerminal
            className={cn(
              'size-4 shrink-0',
              focused ? 'text-foreground/80' : 'text-muted-foreground'
            )}
            aria-hidden
          />
        )}
        {color ? (
          <span
            className="size-2 shrink-0 rounded-full border border-black/10"
            style={{ backgroundColor: color }}
            aria-hidden
          />
        ) : null}
        <span className="min-w-0 flex-1 truncate text-[13px] font-medium">
          {title}
        </span>
        {isPinned ? (
          <Pin
            aria-label="Pinned"
            className="text-muted-foreground/60 size-3 shrink-0"
          />
        ) : null}
      </div>

      <TooltipProvider delayDuration={300}>
        <div className="flex shrink-0 items-center gap-0.5">
          {terminal ? (
            <Popover open={menuOpen} onOpenChange={setMenuOpen}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      className="inline-flex size-7 items-center justify-center rounded-md hover:bg-black/[0.06] dark:hover:bg-white/[0.08]"
                      aria-label="More actions"
                    >
                      <MoreVertical className="size-3.5" />
                    </button>
                  </PopoverTrigger>
                </TooltipTrigger>
                <TooltipContent side="bottom">More</TooltipContent>
              </Tooltip>
              <PopoverContent
                align="end"
                sideOffset={6}
                className="w-52 p-1.5"
                onCloseAutoFocus={event => event.preventDefault()}
              >
                <TerminalActionsMenu
                  terminal={terminal}
                  projects={projects}
                  tabColor={color}
                  onRename={closeThen(() => onRename?.(terminal.id))}
                  onTogglePin={closeThen(() => onTogglePin?.(terminal.id))}
                  onMoveToProject={projectId => {
                    setMenuOpen(false)
                    void onMoveToProject?.(terminal.id, projectId)
                  }}
                  onSetTabColor={value => {
                    setMenuOpen(false)
                    setTabColor(terminal.id, value)
                  }}
                  onArchive={closeThen(() => onToggleArchive?.(terminal.id))}
                  onConvert={closeThen()}
                  onSplitPane={
                    onSplitPane
                      ? (direction, target) => {
                          setMenuOpen(false)
                          onSplitPane(terminal.id, direction, target)
                        }
                      : undefined
                  }
                  onClosePane={
                    onRemoveFromSplit
                      ? closeThen(() => onRemoveFromSplit(terminal.id))
                      : undefined
                  }
                />
              </PopoverContent>
            </Popover>
          ) : null}
        </div>
      </TooltipProvider>
    </div>
  )
}
