import type { AgentProject, TerminalSession } from '@sandwalk/agent-ui-core'
import { Archive, Folder, Pencil, Pin, Trash2, X } from 'lucide-react'

import { ConvertTerminalItem } from '@/components/agents/ExternalAgentMenuBlocks'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { SplitMenuBlock } from '@/components/agents/split-menu'
import {
  TabContextItem,
  TabContextSeparator,
  TabInlineColorRow
} from '@/components/agents/tab-context-menu'
import type { PaneSplitDirection, PaneSplitTarget } from '@/lib/pane-split'

/**
 * FAS-107: peer of `SessionActionsMenu` for terminals. Same primitives and
 * row density as the tab context menu so the sidebar ⋯ menu, the split
 * pane header ⋯ menu and the tab right-click menu look identical.
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
  onConvert,
  onSplitPane,
  onClosePane
}: {
  terminal: TerminalSession
  projects: AgentProject[]
  tabColor?: string | null
  onRename: () => void
  onTogglePin: () => void
  onMoveToProject: (projectId: string | null) => void
  onSetTabColor: (color: string | null) => void
  onArchive: () => void
  /** Sidebar only — destructive, so the split header leaves it out. */
  onDelete?: () => void
  /** Called right before a "Convert to…" action runs — close the popover. */
  onConvert?: () => void
  /** Split pane header: Split Down / Split Right flyouts. */
  onSplitPane?: (direction: PaneSplitDirection, target: PaneSplitTarget) => void
  /** Split pane header: remove this terminal from the split (not delete). */
  onClosePane?: () => void
}) {
  return (
    <>
      <TabContextItem icon={<Pencil />} label="Rename terminal…" onClick={onRename} />
      <ProjectPicker
        projects={projects}
        value={terminal.projectId}
        noneLabel="No project"
        trigger={
          <button
            type="button"
            role="menuitem"
            className="hover:bg-muted flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-xs [&_svg]:size-3"
          >
            <Folder />
            <span className="min-w-0 flex-1 truncate">Move to project…</span>
          </button>
        }
        onChange={onMoveToProject}
      />
      <TabContextItem
        icon={<Pin />}
        label={terminal.organizeLabel === 'pinned' ? 'Unpin' : 'Pin'}
        onClick={onTogglePin}
      />
      <TabContextSeparator />
      <div className="text-muted-foreground/80 px-2 pb-0.5 pt-0.5 text-[10px] font-semibold uppercase tracking-wide">
        Color
      </div>
      <TabInlineColorRow
        value={tabColor || null}
        onSelect={color => onSetTabColor(color)}
        onClear={() => onSetTabColor(null)}
      />
      <TabContextSeparator />
      <ConvertTerminalItem terminal={terminal} onDone={onConvert} />
      <TabContextItem
        icon={<Archive />}
        label={terminal.organizeLabel === 'archive' ? 'Unarchive' : 'Archive'}
        onClick={onArchive}
      />
      {onSplitPane ? (
        <>
          <TabContextSeparator />
          <SplitMenuBlock
            sourceId={terminal.id}
            onSplitPane={(_id, direction, target) => onSplitPane(direction, target)}
            trailingSeparator={false}
          />
        </>
      ) : null}
      {onClosePane ? (
        <>
          <TabContextSeparator />
          <TabContextItem icon={<X />} label="Close pane" onClick={onClosePane} />
        </>
      ) : null}
      {onDelete ? (
        <>
          <TabContextSeparator />
          <TabContextItem icon={<Trash2 />} label="Delete" destructive onClick={onDelete} />
        </>
      ) : null}
    </>
  )
}
