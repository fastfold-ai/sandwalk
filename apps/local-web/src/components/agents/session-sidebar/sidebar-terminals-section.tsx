import type { TerminalSession } from '@sandwalk/agent-ui-core'
import { ChevronDown, SquareTerminal, X } from 'lucide-react'
import { useState } from 'react'

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
  onCloseTerminal
}: {
  terminals: TerminalSession[]
  activeId: string | null
  openTerminal: (terminalId: string) => void
  onCloseTerminal?: (terminalId: string) => void
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
            <TerminalRow
              key={term.id}
              term={term}
              active={term.id === activeId}
              onOpen={() => {
                clearTerminalActivity(term.id)
                openTerminal(term.id)
              }}
              onClose={onCloseTerminal}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function TerminalRow({
  term,
  active,
  onOpen,
  onClose
}: {
  term: TerminalSession
  active: boolean
  onOpen: () => void
  onClose?: (terminalId: string) => void
}) {
  const hasActivity = useTerminalHasActivity(term.id)
  return (
    <li>
      <div
        className={cn(
          // Match the visual anatomy of a chat row so the user reads
          // this as the same list, just with a terminal glyph.
          'hover:bg-sidebar-accent/45 group grid grid-cols-[minmax(0,1fr)_2rem] items-center rounded-md px-2 py-1.5',
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
          <span className="text-foreground/90 min-w-0 truncate text-[13px]">
            {term.title}
          </span>
        </button>
        <div className="flex items-center justify-end">
          {onClose ? (
            <button
              type="button"
              aria-label={`Delete ${term.title}`}
              className="text-muted-foreground hover:text-destructive hidden shrink-0 rounded p-0.5 group-hover:inline-flex"
              onClick={e => {
                e.stopPropagation()
                onClose(term.id)
              }}
            >
              <X className="size-3" />
            </button>
          ) : null}
        </div>
      </div>
    </li>
  )
}
