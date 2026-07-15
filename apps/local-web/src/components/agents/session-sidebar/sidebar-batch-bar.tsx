import type { AgentProject } from '@sandwalk/agent-ui-core'
import {
  Archive,
  Download,
  Folder,
  Trash2,
  X
} from 'lucide-react'

import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { Button } from '@/components/ui/button'

export type SidebarBatchBarProps = {
  selectedCount: number
  batchBusy: boolean
  projects: AgentProject[]
  onClearSelection: () => void
  onBatchArchive: () => void | Promise<void>
  onBatchMove: (projectId: string | null) => void | Promise<void>
  onBatchExport: () => void | Promise<void>
  onBatchDelete: () => void
}

export function SidebarBatchBar({
  selectedCount,
  batchBusy,
  projects,
  onClearSelection,
  onBatchArchive,
  onBatchMove,
  onBatchExport,
  onBatchDelete
}: SidebarBatchBarProps) {
  if (selectedCount <= 0) return null

  return (
    <div className="border-border/60 mx-2 mb-1 space-y-2 rounded-lg border bg-sidebar-accent/40 px-2.5 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-foreground text-[12px] font-medium">
          {selectedCount} selected
        </span>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground inline-flex size-6 items-center justify-center rounded-md"
          aria-label="Clear selection"
          disabled={batchBusy}
          onClick={onClearSelection}
        >
          <X className="size-3.5" />
        </button>
      </div>
      <div className="flex flex-wrap gap-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 px-2 text-[11px]"
          disabled={batchBusy}
          onClick={() => void onBatchArchive()}
        >
          <Archive className="size-3" />
          Archive
        </Button>
        <ProjectPicker
          projects={projects}
          value={null}
          disabled={batchBusy}
          noneLabel="No project"
          trigger={
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 px-2 text-[11px]"
              disabled={batchBusy}
            >
              <Folder className="size-3" />
              Move
            </Button>
          }
          onChange={projectId => {
            void onBatchMove(projectId)
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 px-2 text-[11px]"
          disabled={batchBusy}
          onClick={() => void onBatchExport()}
        >
          <Download className="size-3" />
          Export
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="text-destructive hover:text-destructive h-7 px-2 text-[11px]"
          disabled={batchBusy}
          onClick={onBatchDelete}
        >
          <Trash2 className="size-3" />
          Delete
        </Button>
      </div>
      <p className="text-muted-foreground text-[10px] leading-snug">
        Shift+click range · ⌘/Ctrl+click toggle · Esc clears
      </p>
    </div>
  )
}
