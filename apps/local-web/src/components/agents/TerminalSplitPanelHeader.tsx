import type { AgentProject, TerminalSession } from '@sandwalk/agent-ui-core'
import {
  Archive,
  ArrowDownToLine,
  ArrowLeftToLine,
  ArrowRightToLine,
  ArrowUpToLine,
  Folder,
  MoreVertical,
  Pencil,
  Pin,
  SquareTerminal,
  X
} from 'lucide-react'
import { useState } from 'react'

import { ProjectMetaHover } from '@/components/agents/ChatSplitPanelHeader'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { useSessionTabColors } from '@/components/agents/session-tab-colors'
import { TabInlineColorRow } from '@/components/agents/tab-context-menu'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

/**
 * FAS-107 P3: peer of `ChatSplitPanelHeader` for terminal panes. Same
 * height, same layout, same look — just the actions that apply to a
 * terminal (no Files/Preview/CLI toggles, no Inspect chat, no Export).
 *
 * Doctrine: a terminal is a chat with a shell inside — the split-panel
 * header must offer the same "centro de mando" per pane so the user can
 * rename, move, pin, color, archive, split and close the terminal from
 * the header without going to the sidebar.
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
  onSplitLeft?: (terminalId: string) => void
  onSplitRight?: (terminalId: string) => void
  onSplitUp?: (terminalId: string) => void
  onSplitDown?: (terminalId: string) => void
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
  onSplitLeft,
  onSplitRight,
  onSplitUp,
  onSplitDown
}: TerminalSplitPanelHeaderProps) {
  const { tabColors, setTabColor } = useSessionTabColors()
  const [menuOpen, setMenuOpen] = useState(false)
  const title = terminal?.title || 'Terminal'
  const color = terminal ? tabColors[terminal.id] ?? null : null
  const isPinned = terminal?.organizeLabel === 'pinned'
  const isArchived = terminal?.organizeLabel === 'archive'
  // X2 Fix 2: chip del proyecto visible + popover con la ficha, igual al
  // header del chat. Antes el terminal no mostraba el proyecto asignado en
  // el header del split, rompiendo paridad.
  const project = terminal?.projectId
    ? projects.find(p => p.id === terminal.projectId) || null
    : null

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
        <SquareTerminal
          className={cn(
            'size-4 shrink-0',
            focused ? 'text-orange-500' : 'text-muted-foreground'
          )}
          aria-hidden
        />
        {color ? (
          <span
            className="size-2 shrink-0 rounded-full border border-black/10"
            style={{ backgroundColor: color }}
            aria-hidden
          />
        ) : null}
        <div className="flex min-w-0 flex-1 flex-col leading-tight">
          <span className="truncate text-[13px] font-medium">{title}</span>
          <ProjectMetaHover project={project} />
        </div>
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
            <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      className="inline-flex size-7 items-center justify-center rounded-md hover:bg-black/[0.06] dark:hover:bg-white/[0.08]"
                      aria-label="More actions"
                    >
                      <MoreVertical className="size-3.5" />
                    </button>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                <TooltipContent side="bottom">More</TooltipContent>
              </Tooltip>
              <DropdownMenuContent
                align="end"
                sideOffset={6}
                className="w-56 p-1"
                onCloseAutoFocus={event => event.preventDefault()}
              >
                {onRename ? (
                  <DropdownMenuItem
                    className="gap-2 text-[13px]"
                    onSelect={() => onRename(terminal.id)}
                  >
                    <Pencil className="size-3.5" />
                    Rename terminal…
                  </DropdownMenuItem>
                ) : null}
                {onMoveToProject && projects.length > 0 ? (
                  <ProjectPicker
                    projects={projects}
                    value={terminal.projectId}
                    noneLabel="No project"
                    trigger={
                      <button
                        type="button"
                        role="menuitem"
                        className="hover:bg-muted flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-[13px]"
                      >
                        <Folder className="size-3.5" />
                        Move to project…
                      </button>
                    }
                    onChange={projectId => {
                      void onMoveToProject(terminal.id, projectId)
                    }}
                  />
                ) : null}
                {onTogglePin ? (
                  <DropdownMenuItem
                    className="gap-2 text-[13px]"
                    onSelect={() => onTogglePin(terminal.id)}
                  >
                    <Pin className="size-3.5" />
                    {isPinned ? 'Unpin' : 'Pin'}
                  </DropdownMenuItem>
                ) : null}
                <div className="px-2 py-1.5">
                  <div className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase tracking-wide">
                    Color
                  </div>
                  <TabInlineColorRow
                    value={color}
                    onSelect={value => setTabColor(terminal.id, value)}
                    onClear={() => setTabColor(terminal.id, null)}
                  />
                </div>
                {onToggleArchive ? (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="gap-2 text-[13px]"
                      onSelect={() => onToggleArchive(terminal.id)}
                    >
                      <Archive className="size-3.5" />
                      {isArchived ? 'Unarchive' : 'Archive'}
                    </DropdownMenuItem>
                  </>
                ) : null}
                {onSplitLeft || onSplitRight || onSplitUp || onSplitDown ? (
                  <>
                    <DropdownMenuSeparator />
                    {onSplitLeft ? (
                      <DropdownMenuItem
                        className="gap-2 text-[13px]"
                        onSelect={() => onSplitLeft(terminal.id)}
                      >
                        <ArrowLeftToLine className="size-3.5" />
                        Split left
                      </DropdownMenuItem>
                    ) : null}
                    {onSplitRight ? (
                      <DropdownMenuItem
                        className="gap-2 text-[13px]"
                        onSelect={() => onSplitRight(terminal.id)}
                      >
                        <ArrowRightToLine className="size-3.5" />
                        Split right
                      </DropdownMenuItem>
                    ) : null}
                    {onSplitUp ? (
                      <DropdownMenuItem
                        className="gap-2 text-[13px]"
                        onSelect={() => onSplitUp(terminal.id)}
                      >
                        <ArrowUpToLine className="size-3.5" />
                        Split up
                      </DropdownMenuItem>
                    ) : null}
                    {onSplitDown ? (
                      <DropdownMenuItem
                        className="gap-2 text-[13px]"
                        onSelect={() => onSplitDown(terminal.id)}
                      >
                        <ArrowDownToLine className="size-3.5" />
                        Split down
                      </DropdownMenuItem>
                    ) : null}
                  </>
                ) : null}
                {onRemoveFromSplit ? (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="gap-2 text-[13px]"
                      onSelect={() => onRemoveFromSplit(terminal.id)}
                    >
                      <X className="size-3.5" />
                      Close pane
                    </DropdownMenuItem>
                  </>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
        </div>
      </TooltipProvider>
    </div>
  )
}
