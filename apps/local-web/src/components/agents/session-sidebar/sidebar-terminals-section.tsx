import type {
  AgentProject,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import { ChevronDown, MoreHorizontal, Pin, SquareTerminal } from 'lucide-react'
import { useState } from 'react'

import { TerminalActionsMenu } from '@/components/agents/TerminalActionsMenu'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  clearTerminalActivity,
  useTerminalHasActivity
} from '@/lib/terminal-attention'
import { cn } from '@/lib/utils'

/**
 * FAS-107 GF6: terminals of the active project as a section INSIDE the
 * regular sidebar list (styled identically to Today / Yesterday / …).
 * Rendered by `AgentSessionSidebar` right above `SidebarSessionList`, so
 * to the user it looks like just another section of the same list.
 */
export function SidebarTerminalsSection({
  terminals,
  activeId,
  openTerminal,
  onCloseTerminal,
  projects,
  onMoveToProject
}: {
  terminals: TerminalSession[]
  activeId: string | null
  openTerminal: (terminalId: string) => void
  onCloseTerminal?: (terminalId: string) => void
  /** FAS-107 GF8: projects list for the "Move to project" sub-menu. */
  projects?: AgentProject[]
  onMoveToProject?: (
    terminalId: string,
    projectId: string | null
  ) => void | Promise<void>
}) {
  const [collapsed, setCollapsed] = useState(false)
  if (terminals.length === 0) return null
  return (
    <div className="space-y-0.5">
      <button
        type="button"
        className="text-muted-foreground/80 hover:text-foreground group/sec flex w-full items-center gap-1.5 rounded-md px-2 py-0.5 text-left text-[12px]"
        aria-expanded={!collapsed}
        aria-label={collapsed ? 'Expand Terminals' : 'Collapse Terminals'}
        onClick={() => setCollapsed(c => !c)}
      >
        <span className="min-w-0 truncate">Terminals</span>
        <span
          className="bg-muted text-foreground/70 inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded px-1 text-[10px] font-semibold tabular-nums"
          aria-hidden
        >
          {terminals.length}
        </span>
        <ChevronDown
          className={cn(
            'size-3.5 shrink-0 transition-[opacity,transform]',
            collapsed
              ? '-rotate-90 opacity-100'
              : 'opacity-0 group-hover/sec:opacity-100'
          )}
          aria-hidden
        />
      </button>
      {collapsed ? null : (
        <ul className="space-y-px">
          {terminals.map(term => (
            <TerminalRowInner
              key={term.id}
              term={term}
              active={term.id === activeId}
              onOpen={() => {
                clearTerminalActivity(term.id)
                openTerminal(term.id)
              }}
              onClose={onCloseTerminal}
              projects={projects ?? []}
              onMoveToProject={onMoveToProject}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * Terminal row exported for the inline mixed-list renderer in
 * `sidebar-session-list.tsx`. Keeps a single source of truth for the
 * row anatomy (icon, activity dot, action menu).
 *
 * P4+P5 fix: uses `Popover` + `TerminalActionsMenu` (parity with the
 * chat row) so the menu opens pegged to the ⋯ trigger and its
 * sub-panels (color, project) render inline instead of as Radix
 * `DropdownMenuSub` flyouts that flipped up when the sidebar was
 * narrow. Right-click on the whole row also opens the menu — parity
 * with the chat row.
 */
export function SidebarTerminalRow({
  terminal,
  active,
  onOpen,
  onClose,
  projects,
  onMoveToProject,
  onRename,
  onTogglePin,
  onToggleArchive,
  onSetColor,
  colorValue
}: {
  terminal: TerminalSession
  active: boolean
  onOpen: (terminalId: string) => void
  onClose?: (terminalId: string) => void
  projects: AgentProject[]
  onMoveToProject?: (
    terminalId: string,
    projectId: string | null
  ) => void | Promise<void>
  onRename?: (terminalId: string) => void
  onTogglePin?: (terminalId: string) => void
  onToggleArchive?: (terminalId: string) => void
  onSetColor?: (terminalId: string, color: string | null) => void
  colorValue?: string | null
}) {
  const term = terminal
  return (
    <TerminalRowInner
      term={term}
      active={active}
      onOpen={() => {
        clearTerminalActivity(term.id)
        onOpen(term.id)
      }}
      onClose={onClose}
      projects={projects}
      onMoveToProject={onMoveToProject}
      onRename={onRename}
      onTogglePin={onTogglePin}
      onToggleArchive={onToggleArchive}
      onSetColor={onSetColor}
      colorValue={colorValue}
    />
  )
}

function TerminalRowInner({
  term,
  active,
  onOpen,
  onClose,
  projects,
  onMoveToProject,
  onRename,
  onTogglePin,
  onToggleArchive,
  onSetColor,
  colorValue
}: {
  term: TerminalSession
  active: boolean
  onOpen: () => void
  onClose?: (terminalId: string) => void
  projects: AgentProject[]
  onMoveToProject?: (
    terminalId: string,
    projectId: string | null
  ) => void | Promise<void>
  onRename?: (terminalId: string) => void
  onTogglePin?: (terminalId: string) => void
  onToggleArchive?: (terminalId: string) => void
  onSetColor?: (terminalId: string, color: string | null) => void
  colorValue?: string | null
}) {
  const hasActivity = useTerminalHasActivity(term.id)
  const isPinned = term.organizeLabel === 'pinned'
  const [menuOpen, setMenuOpen] = useState(false)
  return (
    <li>
      <div
        className={cn(
          'hover:bg-sidebar-accent/45 group grid grid-cols-[minmax(0,1fr)_auto] items-center rounded-md px-2 py-1.5',
          active && 'bg-sidebar-accent/55'
        )}
        onContextMenu={event => {
          // P4: right-click anywhere on the row opens the same menu the
          // ⋯ trigger would — parity with the chat row.
          event.preventDefault()
          setMenuOpen(true)
        }}
      >
        <button
          type="button"
          className="flex min-w-0 items-center gap-1.5 text-left"
          onClick={onOpen}
        >
          <span className="relative shrink-0">
            <SquareTerminal className="size-3.5 text-orange-500" />
            {hasActivity && !active ? (
              <span
                aria-label="New output"
                className="absolute -right-0.5 -top-0.5 size-1.5 rounded-full bg-orange-500 shadow-[0_0_0_1px_var(--background)]"
              />
            ) : null}
          </span>
          {colorValue ? (
            <span
              aria-hidden
              className="size-2 shrink-0 rounded-full border border-black/10"
              style={{ backgroundColor: colorValue }}
            />
          ) : null}
          <span className="text-foreground/90 min-w-0 truncate text-[13px]">
            {term.title}
          </span>
          {isPinned ? (
            <Pin
              aria-label="Pinned"
              className="text-muted-foreground/60 size-3 shrink-0"
            />
          ) : null}
        </button>
        <div className="relative flex items-center gap-0.5">
          <Popover open={menuOpen} onOpenChange={setMenuOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                aria-label={`Actions for ${term.title}`}
                className={cn(
                  'text-muted-foreground hover:text-foreground hover:bg-muted shrink-0 rounded p-0.5 transition-opacity',
                  menuOpen
                    ? 'opacity-100'
                    : 'opacity-0 group-hover:opacity-100'
                )}
                onClick={e => e.stopPropagation()}
              >
                <MoreHorizontal className="size-3.5" />
              </button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-52 p-1.5">
              <TerminalActionsMenu
                terminal={term}
                projects={projects}
                tabColor={colorValue || null}
                onRename={() => {
                  setMenuOpen(false)
                  onRename?.(term.id)
                }}
                onTogglePin={() => {
                  setMenuOpen(false)
                  onTogglePin?.(term.id)
                }}
                onMoveToProject={projectId => {
                  setMenuOpen(false)
                  void onMoveToProject?.(term.id, projectId)
                }}
                onSetTabColor={color => {
                  setMenuOpen(false)
                  onSetColor?.(term.id, color)
                }}
                onArchive={() => {
                  setMenuOpen(false)
                  onToggleArchive?.(term.id)
                }}
                onDelete={() => {
                  setMenuOpen(false)
                  onClose?.(term.id)
                }}
              />
            </PopoverContent>
          </Popover>
        </div>
      </div>
    </li>
  )
}
