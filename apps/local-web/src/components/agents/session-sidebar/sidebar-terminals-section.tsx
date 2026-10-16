import type {
  AgentProject,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import { ChevronDown, MoreHorizontal, Pin } from 'lucide-react'
import { useState } from 'react'

import { TerminalActionsMenu } from '@/components/agents/TerminalActionsMenu'
import { TerminalTypeIcon } from '@/components/agents/TerminalTypeIcon'
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

import { UnreadDot } from './sidebar-session-list'

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
          // Q6: mismo grid + padding que la fila de chat para igualar alto.
          'hover:bg-sidebar-accent/45 group grid grid-cols-[minmax(0,1fr)_2rem] items-center rounded-md px-2 py-1.5',
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
          {/* Q7: pin PRIMERO, mismo gris que la fila de chat. Sólo se renderiza
              cuando el terminal está pinneado (y por tanto aparece en
              la sección Pinned del sidebar).
              FAS-107: pin e icono de tipo viven en slots uniformes
              `size-4` con `place-items-center` para garantizar
              alineación vertical con las filas de chat y group split. */}
          <span
            aria-hidden
            className="grid size-4 shrink-0 place-items-center"
          >
            {isPinned ? (
              <Pin
                aria-label="Pinned"
                className="text-zinc-400 size-3"
                fill="currentColor"
              />
            ) : (
              <TerminalTypeIcon terminalId={term.id} />
            )}
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
        </button>
        {/* Q4: slot derecho unificado con la fila chat (h-6 w-8). El
            UnreadDot vive acá y hover-swap con el ⋯ — nunca overlay
            sobre el ícono del tipo. */}
        <div className="relative h-6 w-8 justify-self-end">
          {hasActivity && !active && !menuOpen ? (
            <span className="pointer-events-none absolute inset-0 flex items-center justify-end pr-0.5 group-hover:opacity-0">
              <UnreadDot />
            </span>
          ) : null}
          <Popover open={menuOpen} onOpenChange={setMenuOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                aria-label={`Actions for ${term.title}`}
                className={cn(
                  'text-muted-foreground hover:text-foreground hover:bg-muted absolute right-0 inset-y-0 my-auto inline-flex items-center justify-center rounded-md p-0.5 transition-opacity',
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
