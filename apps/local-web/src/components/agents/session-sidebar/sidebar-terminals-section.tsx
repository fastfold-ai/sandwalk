import type { TerminalSession } from '@sandwalk/agent-ui-core'
import { ChevronDown, ChevronRight, SquareTerminal } from 'lucide-react'
import { useState } from 'react'

import {
  clearTerminalActivity,
  useTerminalHasActivity
} from '@/lib/terminal-attention'
import { cn } from '@/lib/utils'

/**
 * Sidebar section that lists terminals of the active project (FAS-107
 * GF6). Rendered right below the chat sections in `AgentSessionSidebar`.
 *
 * MVP scope: click-to-open + delete affordance. Pin / rename / color /
 * move-to-project + activity dot land in GF7/GF8/GF9.
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
    <div className="border-border/40 flex flex-col border-t px-2 py-2">
      <button
        type="button"
        className="text-muted-foreground hover:text-foreground flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium uppercase tracking-wide"
        onClick={() => setCollapsed(c => !c)}
      >
        {collapsed ? (
          <ChevronRight className="size-3" />
        ) : (
          <ChevronDown className="size-3" />
        )}
        <span>Terminals</span>
        <span className="text-muted-foreground/60 ml-1 text-[10px]">
          {terminals.length}
        </span>
      </button>
      {!collapsed ? (
        <ul className="mt-1 flex flex-col">
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
      ) : null}
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
          'group flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[13px] transition-colors',
          active
            ? 'bg-orange-500/10 text-foreground'
            : 'hover:bg-muted/60 text-foreground/80'
        )}
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
        <span className="min-w-0 flex-1 truncate">{term.title}</span>
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
            ×
          </button>
        ) : null}
      </div>
    </li>
  )
}
