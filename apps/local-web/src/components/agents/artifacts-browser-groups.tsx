import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFile } from '@sandwalk/agent-ui-core'
import { ChevronDown, Download, Folder } from 'lucide-react'

import { ScrollArea } from '@/components/ui/scroll-area'
import { getFileIcon } from '@/lib/file-icons'
import { cn, relativeTime } from '@/lib/utils'

import { ArtifactGridThumb } from './ArtifactGridThumb'
import type { ArtifactGroup, ViewMode } from './workspace-utils'

export function ArtifactsBrowserGroups({
  client,
  sessionId,
  visibleGroups,
  viewMode,
  expandedGroups,
  activePath,
  empty,
  onToggleGroup,
  onOpenFile,
  onDownloadFile
}: {
  client: LocalAgentClient
  sessionId: string
  visibleGroups: ArtifactGroup[]
  viewMode: ViewMode
  expandedGroups: Record<string, boolean>
  activePath: string | null
  empty: boolean
  onToggleGroup: (id: string) => void
  onOpenFile: (file: WorkspaceFile) => void
  onDownloadFile: (path: string) => void
}) {
  if (empty) {
    return (
      <div className="text-muted-foreground/70 flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-3 text-center">
        <Folder className="size-9 opacity-70" />
        <p className="text-xs">No files yet</p>
      </div>
    )
  }

  if (visibleGroups.length === 0) {
    return (
      <div className="text-muted-foreground/70 flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-3 text-center">
        <Folder className="size-9 opacity-70" />
        <p className="text-xs">No artifacts in this scope</p>
      </div>
    )
  }

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="space-y-2 p-2">
        {visibleGroups.map(group => {
          const open = expandedGroups[group.id] ?? true
          return (
            <div key={group.id} className="space-y-1">
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground flex w-full items-center justify-between rounded px-1 py-1 text-left text-[11px]"
                onClick={() => onToggleGroup(group.id)}
              >
                <span className="inline-flex min-w-0 items-center gap-1 font-medium">
                  <ChevronDown
                    className={cn(
                      'size-3.5 shrink-0 transition-transform',
                      !open && '-rotate-90'
                    )}
                  />
                  <span className="truncate">{group.title}</span>
                </span>
                <span>
                  {group.files.length}
                  {group.files[0]?.mtime
                    ? ` · ${relativeTime(group.files[0].mtime)}`
                    : ''}
                </span>
              </button>
              {open ? (
                viewMode === 'grid' ? (
                  <div className="grid grid-cols-2 gap-2">
                    {group.files.map(file => (
                      <button
                        key={file.path}
                        type="button"
                        className={cn(
                          'hover:bg-muted/60 group/file flex flex-col items-stretch gap-1.5 rounded-md border border-transparent p-1.5 text-left transition-colors',
                          activePath === file.path &&
                            'bg-muted border-border'
                        )}
                        onClick={() => onOpenFile(file)}
                      >
                        <ArtifactGridThumb
                          client={client}
                          sessionId={sessionId}
                          file={file}
                        />
                        <span className="line-clamp-2 w-full px-0.5 text-[11px] leading-tight">
                          {file.name}
                        </span>
                        <span className="text-muted-foreground px-0.5 text-[10px]">
                          {relativeTime(file.mtime)}
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-0.5">
                    {group.files.map(file => (
                      <div
                        key={file.path}
                        role="button"
                        tabIndex={0}
                        className={cn(
                          'hover:bg-muted group/file flex w-full cursor-pointer items-center gap-1.5 rounded px-1.5 py-1.5',
                          activePath === file.path && 'bg-muted'
                        )}
                        onClick={() => onOpenFile(file)}
                        onKeyDown={event => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            onOpenFile(file)
                          }
                        }}
                      >
                        <Icon
                          icon={getFileIcon(file.name)}
                          className="size-3.5 shrink-0"
                        />
                        <span className="min-w-0 flex-1 truncate text-left text-[11px]">
                          {file.name}
                        </span>
                        <div className="relative h-6 w-11 shrink-0">
                          <span className="text-muted-foreground pointer-events-none absolute inset-0 flex items-center justify-end pr-0.5 text-[10px] transition-opacity group-hover/file:opacity-0">
                            {relativeTime(file.mtime)}
                          </span>
                          <button
                            type="button"
                            className="text-muted-foreground hover:text-foreground absolute inset-y-0 right-0 inline-flex size-6 items-center justify-center rounded opacity-0 transition-opacity group-hover/file:opacity-100"
                            title="Download"
                            onClick={event => {
                              event.stopPropagation()
                              onDownloadFile(file.path)
                            }}
                          >
                            <Download className="size-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )
              ) : null}
            </div>
          )
        })}
      </div>
    </ScrollArea>
  )
}
