import type {
  AgentProject,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import {
  Archive,
  ArchiveRestore,
  ChevronDown,
  Folder,
  MoreHorizontal,
  Palette,
  Pencil,
  Pin,
  PinOff,
  SquareTerminal,
  X
} from 'lucide-react'
import { useState } from 'react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  clearTerminalActivity,
  useTerminalHasActivity
} from '@/lib/terminal-attention'
import { cn } from '@/lib/utils'

// Palette matches the chat sidebar tab colors so users see one system.
const TERMINAL_TAB_COLORS: Array<{ id: string; hex: string; label: string }> = [
  { id: 'red', hex: '#ef4444', label: 'Red' },
  { id: 'orange', hex: '#f97316', label: 'Orange' },
  { id: 'amber', hex: '#f59e0b', label: 'Amber' },
  { id: 'green', hex: '#22c55e', label: 'Green' },
  { id: 'cyan', hex: '#06b6d4', label: 'Cyan' },
  { id: 'blue', hex: '#3b82f6', label: 'Blue' },
  { id: 'violet', hex: '#8b5cf6', label: 'Violet' },
  { id: 'pink', hex: '#ec4899', label: 'Pink' }
]

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
 * row anatomy (icon, activity dot, action menu, delete).
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
  const isArchived = term.organizeLabel === 'archive'
  return (
    <li>
      <div
        className={cn(
          'hover:bg-sidebar-accent/45 group grid grid-cols-[minmax(0,1fr)_auto] items-center rounded-md px-2 py-1.5',
          active && 'bg-sidebar-accent/55'
        )}
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
        <div className="flex items-center gap-0.5">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label={`Actions for ${term.title}`}
                className="text-muted-foreground hover:text-foreground hover:bg-muted hidden shrink-0 rounded p-0.5 group-hover:inline-flex"
                onClick={e => e.stopPropagation()}
              >
                <MoreHorizontal className="size-3.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="min-w-[200px]"
              onCloseAutoFocus={e => e.preventDefault()}
            >
              {onRename ? (
                <DropdownMenuItem onSelect={() => onRename(term.id)}>
                  <Pencil className="mr-2 size-3.5" />
                  <span>Rename</span>
                </DropdownMenuItem>
              ) : null}
              {onTogglePin ? (
                <DropdownMenuItem onSelect={() => onTogglePin(term.id)}>
                  {isPinned ? (
                    <PinOff className="mr-2 size-3.5" />
                  ) : (
                    <Pin className="mr-2 size-3.5" />
                  )}
                  <span>{isPinned ? 'Unpin' : 'Pin'}</span>
                </DropdownMenuItem>
              ) : null}
              {onSetColor ? (
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    <Palette className="mr-2 size-3.5" />
                    <span>Set color</span>
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent className="min-w-[160px]">
                    <DropdownMenuItem
                      onSelect={() => onSetColor(term.id, null)}
                    >
                      <span
                        aria-hidden
                        className="mr-2 size-3 rounded-full border border-black/10"
                      />
                      <span>None</span>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    {TERMINAL_TAB_COLORS.map(c => (
                      <DropdownMenuItem
                        key={c.id}
                        onSelect={() => onSetColor(term.id, c.hex)}
                      >
                        <span
                          aria-hidden
                          className="mr-2 size-3 rounded-full border border-black/10"
                          style={{ backgroundColor: c.hex }}
                        />
                        <span>{c.label}</span>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
              ) : null}
              {onMoveToProject ? (
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    <Folder className="mr-2 size-3.5" />
                    <span>Move to project</span>
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent className="min-w-[180px]">
                    <DropdownMenuItem
                      onSelect={() => void onMoveToProject(term.id, null)}
                    >
                      <span>No project</span>
                    </DropdownMenuItem>
                    {projects.length > 0 ? (
                      <DropdownMenuSeparator />
                    ) : null}
                    {projects.map(p => (
                      <DropdownMenuItem
                        key={p.id}
                        onSelect={() => void onMoveToProject(term.id, p.id)}
                      >
                        <span className="truncate">{p.name}</span>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
              ) : null}
              {onToggleArchive ? (
                <DropdownMenuItem onSelect={() => onToggleArchive(term.id)}>
                  {isArchived ? (
                    <ArchiveRestore className="mr-2 size-3.5" />
                  ) : (
                    <Archive className="mr-2 size-3.5" />
                  )}
                  <span>{isArchived ? 'Unarchive' : 'Archive'}</span>
                </DropdownMenuItem>
              ) : null}
              {onClose ? (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onSelect={() => onClose(term.id)}
                  >
                    <X className="mr-2 size-3.5" />
                    <span>Delete terminal</span>
                  </DropdownMenuItem>
                </>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </li>
  )
}
