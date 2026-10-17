import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Archive,
  Copy,
  Download,
  Folder,
  Pencil,
  Pin,
  Search,
  Trash2
} from 'lucide-react'

import { ContinueInSubmenu } from '@/components/agents/ExternalAgentMenuBlocks'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import {
  TabContextItem,
  TabContextSeparator,
  TabInlineColorRow
} from '@/components/agents/tab-context-menu'
import { duplicateChat } from '@/lib/duplicate-chat'

/**
 * Sidebar ⋯ menu for a chat. Same primitives and row density as the tab
 * context menu (`TabContextItem`, flyout for Continue in…) so the two
 * surfaces look and behave identically.
 */
export function SessionActionsMenu({
  session,
  projects,
  tabColor,
  onRename,
  onTogglePin,
  onMoveToProject,
  onSetTabColor,
  onExport,
  onInspect,
  onArchive,
  onDelete,
  onContinueIn,
  onDuplicate
}: {
  session: AgentSession
  projects: AgentProject[]
  tabColor?: string | null
  onRename: () => void
  onTogglePin: () => void
  onMoveToProject: (projectId: string | null) => void
  onSetTabColor: (color: string | null) => void
  onExport: () => void
  onInspect: () => void
  onArchive: () => void
  onDelete: () => void
  /** Called right before a "Continue in <CLI>" row runs — close the popover. */
  onContinueIn?: () => void
  /** Called right before Duplicate runs — close the popover. */
  onDuplicate?: () => void
}) {
  return (
    <>
      <TabContextItem icon={<Pencil />} label="Rename chat…" onClick={onRename} />
      <TabContextItem
        icon={<Copy />}
        label="Duplicate chat"
        onClick={() => {
          onDuplicate?.()
          void duplicateChat(session)
        }}
      />
      <ProjectPicker
        projects={projects}
        value={session.projectId}
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
        label={session.organizeLabel === 'pinned' ? 'Unpin' : 'Pin'}
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
      <TabContextItem icon={<Download />} label="Export transcript" onClick={onExport} />
      <TabContextItem icon={<Search />} label="Inspect chat" onClick={onInspect} />
      <ContinueInSubmenu session={session} onClose={() => onContinueIn?.()} />
      <TabContextItem
        icon={<Archive />}
        label={session.organizeLabel === 'archive' ? 'Unarchive' : 'Archive'}
        onClick={onArchive}
      />
      <TabContextSeparator />
      <TabContextItem icon={<Trash2 />} label="Delete" destructive onClick={onDelete} />
    </>
  )
}
