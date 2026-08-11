import type { AgentProject } from '@sandwalk/agent-ui-core'
import {
  Archive,
  Columns2,
  Download,
  FolderInput,
  MailOpen,
  Trash2,
  X
} from 'lucide-react'
import type { ReactNode } from 'react'

import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

export type SidebarBatchBarProps = {
  selectedCount: number
  batchBusy: boolean
  projects: AgentProject[]
  onClearSelection: () => void
  onBatchMarkRead: () => void | Promise<void>
  onBatchArchive: () => void | Promise<void>
  onBatchMove: (projectId: string | null) => void | Promise<void>
  onBatchExport: () => void | Promise<void>
  onBatchDelete: () => void
  onBatchSplitView?: () => void
  canSplitView?: boolean
}

function IconAction({
  label,
  disabled,
  destructive,
  onClick,
  children
}: {
  label: string
  disabled?: boolean
  destructive?: boolean
  onClick?: () => void
  children: ReactNode
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className={cn(
            'size-7 shrink-0 rounded-full text-zinc-800 hover:bg-black/10 hover:text-zinc-950',
            destructive &&
              'text-red-600 hover:bg-red-500/15 hover:text-red-700'
          )}
          disabled={disabled}
          aria-label={label}
          onClick={onClick}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent side="bottom">{label}</TooltipContent>
    </Tooltip>
  )
}

export function SidebarBatchBar({
  selectedCount,
  batchBusy,
  projects,
  onClearSelection,
  onBatchMarkRead,
  onBatchArchive,
  onBatchMove,
  onBatchExport,
  onBatchDelete,
  onBatchSplitView,
  canSplitView
}: SidebarBatchBarProps) {
  if (selectedCount <= 0) return null

  return (
    <TooltipProvider delayDuration={200}>
      <div
        className="pointer-events-none absolute inset-x-2 bottom-full z-20 mb-1.5 flex justify-center"
        role="toolbar"
        aria-label="Session selection actions"
      >
        <div className="animate-in fade-in slide-in-from-bottom-3 fill-mode-both pointer-events-auto flex flex-col items-center gap-1 rounded-2xl bg-zinc-100 px-2.5 py-1.5 text-zinc-900 shadow-lg shadow-black/35 duration-300 ease-out dark:bg-zinc-200 dark:text-zinc-900">
          <span className="text-[10px] font-medium tabular-nums leading-none text-zinc-500">
            {selectedCount} selected
          </span>
          <div className="flex items-center gap-0.5">
            <IconAction
              label="Mark as read"
              disabled={batchBusy}
              onClick={() => void onBatchMarkRead()}
            >
              <MailOpen className="size-3.5" />
            </IconAction>
            <IconAction
              label="Archive"
              disabled={batchBusy}
              onClick={() => void onBatchArchive()}
            >
              <Archive className="size-3.5" />
            </IconAction>
            <ProjectPicker
              projects={projects}
              value={null}
              disabled={batchBusy}
              noneLabel="No project"
              trigger={
                <span>
                  <IconAction label="Move to project" disabled={batchBusy}>
                    <FolderInput className="size-3.5" />
                  </IconAction>
                </span>
              }
              onChange={projectId => {
                void onBatchMove(projectId)
              }}
            />
            <IconAction
              label="Export"
              disabled={batchBusy}
              onClick={() => void onBatchExport()}
            >
              <Download className="size-3.5" />
            </IconAction>
            {onBatchSplitView ? (
              <IconAction
                label="Split view"
                disabled={batchBusy || !canSplitView}
                onClick={onBatchSplitView}
              >
                <Columns2 className="size-3.5" />
              </IconAction>
            ) : null}
            <IconAction
              label="Delete"
              disabled={batchBusy}
              destructive
              onClick={onBatchDelete}
            >
              <Trash2 className="size-3.5" />
            </IconAction>
            <span
              className="mx-0.5 h-3.5 w-px shrink-0 bg-zinc-400/70"
              aria-hidden
            />
            <IconAction
              label="Clear selection"
              disabled={batchBusy}
              onClick={onClearSelection}
            >
              <X className="size-3.5" />
            </IconAction>
          </div>
        </div>
      </div>
    </TooltipProvider>
  )
}
