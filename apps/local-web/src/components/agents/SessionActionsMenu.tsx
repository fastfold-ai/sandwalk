import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Archive,
  Download,
  Folder,
  Pencil,
  Pin,
  Search,
  Trash2
} from 'lucide-react'

import { ProjectPicker } from '@/components/agents/ProjectPicker'
import {
  TabContextSeparator,
  TabInlineColorRow
} from '@/components/agents/tab-context-menu'

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
  onDelete
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
}) {
  return (
    <>
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onRename}
      >
        <Pencil className="h-3.5 w-3.5" />
        Rename
      </button>
      <ProjectPicker
        projects={projects}
        value={session.projectId}
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
        {session.organizeLabel === 'pinned' ? 'Unpin' : 'Pin'}
      </button>
      <TabContextSeparator />
      <TabInlineColorRow
        value={tabColor || null}
        onSelect={color => onSetTabColor(color)}
        onClear={() => onSetTabColor(null)}
      />
      <TabContextSeparator />
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onExport}
      >
        <Download className="h-3.5 w-3.5" />
        Export transcript
      </button>
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onInspect}
      >
        <Search className="h-3.5 w-3.5" />
        Inspect chat
      </button>
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onArchive}
      >
        <Archive className="h-3.5 w-3.5" />
        {session.organizeLabel === 'archive' ? 'Unarchive' : 'Archive'}
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
