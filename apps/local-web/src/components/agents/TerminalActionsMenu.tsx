import type { AgentProject, TerminalSession } from '@sandwalk/agent-ui-core'
import { Archive, Folder, Pencil, Pin, Trash2 } from 'lucide-react'

import { ConvertTerminalItem } from '@/components/agents/ExternalAgentMenuBlocks'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import {
  TabContextSeparator,
  TabInlineColorRow
} from '@/components/agents/tab-context-menu'

/**
 * FAS-107: peer of `SessionActionsMenu` for terminals. Same layout,
 * same primitives (Popover-friendly buttons + inline color/project
 * pickers) so the terminal ⋯ menu behaves EXACTLY like the chat ⋯ menu
 * — including the way sub-panels stay inside the popover instead of
 * flying out to the side (Radix DropdownMenuSub was the previous
 * approach and its flyouts flipped up when the sidebar was narrow).
 *
 * Export is intentionally omitted (a scrollback export is out of scope
 * for FAS-107). "Inspect chat" doesn't apply to a terminal.
 */
export function TerminalActionsMenu({
  terminal,
  projects,
  tabColor,
  onRename,
  onTogglePin,
  onMoveToProject,
  onSetTabColor,
  onArchive,
  onDelete,
  onConvert
}: {
  terminal: TerminalSession
  projects: AgentProject[]
  tabColor?: string | null
  onRename: () => void
  onTogglePin: () => void
  onMoveToProject: (projectId: string | null) => void
  onSetTabColor: (color: string | null) => void
  onArchive: () => void
  onDelete: () => void
  /** Called right before "Convert … to chat" runs — close the popover. */
  onConvert?: () => void
}) {
  return (
    <>
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onRename}
      >
        <Pencil className="h-3.5 w-3.5" />
        Rename terminal…
      </button>
      <ProjectPicker
        projects={projects}
        value={terminal.projectId}
        noneLabel="No project"
        trigger={
          <button
            type="button"
            className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
          >
            <Folder className="h-3.5 w-3.5" />
            Move to project…
          </button>
        }
        onChange={onMoveToProject}
      />
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onTogglePin}
      >
        <Pin className="h-3.5 w-3.5" />
        {terminal.organizeLabel === 'pinned' ? 'Unpin' : 'Pin'}
      </button>
      <TabContextSeparator />
      <div className="text-muted-foreground/80 px-2 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wide">
        Color
      </div>
      <TabInlineColorRow
        value={tabColor || null}
        onSelect={color => onSetTabColor(color)}
        onClear={() => onSetTabColor(null)}
      />
      <TabContextSeparator />
      <ConvertTerminalItem terminal={terminal} variant="popover" onDone={onConvert} />
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onArchive}
      >
        <Archive className="h-3.5 w-3.5" />
        {terminal.organizeLabel === 'archive' ? 'Unarchive' : 'Archive'}
      </button>
      <button
        type="button"
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20"
        onClick={onDelete}
      >
        <Trash2 className="h-3.5 w-3.5" />
        Delete
      </button>
    </>
  )
}
