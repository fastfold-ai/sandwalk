import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFile } from '@sandwalk/agent-ui-core'
import { ChevronDown, ChevronLeft, Download, Folder } from 'lucide-react'
import { useMemo, useState } from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'
import { getFileIcon } from '@/lib/file-icons'
import { cn, relativeTime } from '@/lib/utils'

import { ArtifactGridThumb } from './ArtifactGridThumb'
import {
  childrenOf,
  compareArtifacts,
  groupRootPath,
  parentDir,
  type ArtifactGroup,
  type ViewMode
} from './workspace-utils'

function FolderGridThumb() {
  return (
    <div className="bg-muted/25 relative flex aspect-[4/3] w-full items-center justify-center overflow-hidden rounded-md border border-transparent">
      <Folder className="text-muted-foreground size-8 opacity-80" />
    </div>
  )
}

function newestMtime(files: WorkspaceFile[]): string | null {
  let best: string | null = null
  let bestMs = 0
  for (const file of files) {
    if (!file.mtime) continue
    const ms = new Date(file.mtime).getTime()
    if (ms > bestMs) {
      bestMs = ms
      best = file.mtime
    }
  }
  return best
}

function GroupFolderTrail({
  root,
  cwd,
  onNavigate
}: {
  root: string
  cwd: string
  onNavigate: (path: string) => void
}) {
  if (cwd === root) return null
  const relative = root
    ? cwd.slice(root.length).replace(/^\//, '')
    : cwd
  const segments = relative.split('/').filter(Boolean)
  return (
    <div className="text-muted-foreground flex min-w-0 items-center gap-0.5 px-1 pb-1 text-[11px]">
      <button
        type="button"
        className="hover:text-foreground inline-flex size-5 shrink-0 items-center justify-center rounded"
        title="Go up"
        aria-label="Go up"
        onClick={() => onNavigate(parentDir(cwd) || root)}
      >
        <ChevronLeft className="size-3.5" />
      </button>
      <button
        type="button"
        className="hover:text-foreground shrink-0 rounded px-0.5"
        onClick={() => onNavigate(root)}
      >
        {root || 'Root'}
      </button>
      {segments.map((segment, index) => {
        const path = [root, ...segments.slice(0, index + 1)]
          .filter(Boolean)
          .join('/')
        return (
          <span key={path} className="inline-flex min-w-0 items-center gap-0.5">
            <span className="opacity-50">/</span>
            <button
              type="button"
              className="hover:text-foreground truncate rounded px-0.5"
              onClick={() => onNavigate(path)}
            >
              {segment}
            </button>
          </span>
        )
      })}
    </div>
  )
}

function ArtifactEntryRow({
  file,
  activePath,
  onOpen,
  onDownloadFile,
  onFileContextMenu
}: {
  file: WorkspaceFile
  activePath: string | null
  onOpen: (file: WorkspaceFile) => void
  onDownloadFile: (path: string) => void
  onFileContextMenu: (file: WorkspaceFile, x: number, y: number) => void
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      className={cn(
        'hover:bg-muted group/file flex w-full cursor-pointer items-center gap-1.5 rounded px-1.5 py-1.5',
        activePath === file.path && 'bg-muted'
      )}
      onClick={() => onOpen(file)}
      onContextMenu={event => {
        event.preventDefault()
        onFileContextMenu(file, event.clientX, event.clientY)
      }}
      onKeyDown={event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen(file)
        }
      }}
    >
      {file.type === 'directory' ? (
        <Folder className="text-muted-foreground size-3.5 shrink-0" />
      ) : (
        <Icon icon={getFileIcon(file.name)} className="size-3.5 shrink-0" />
      )}
      <span className="min-w-0 flex-1 truncate text-left text-[11px]">
        {file.name}
      </span>
      <div className="relative h-6 w-11 shrink-0">
        <span className="text-muted-foreground pointer-events-none absolute inset-0 flex items-center justify-end pr-0.5 text-[10px] transition-opacity group-hover/file:opacity-0">
          {relativeTime(file.mtime)}
        </span>
        {file.type === 'file' ? (
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
        ) : null}
      </div>
    </div>
  )
}

function ArtifactEntryCard({
  client,
  sessionId,
  file,
  activePath,
  onOpen,
  onFileContextMenu
}: {
  client: LocalAgentClient
  sessionId: string
  file: WorkspaceFile
  activePath: string | null
  onOpen: (file: WorkspaceFile) => void
  onFileContextMenu: (file: WorkspaceFile, x: number, y: number) => void
}) {
  return (
    <button
      type="button"
      className={cn(
        'hover:bg-muted/60 group/file flex flex-col items-stretch gap-1.5 rounded-md border border-transparent p-1.5 text-left transition-colors',
        activePath === file.path && 'bg-muted border-border'
      )}
      onClick={() => onOpen(file)}
      onContextMenu={event => {
        event.preventDefault()
        onFileContextMenu(file, event.clientX, event.clientY)
      }}
    >
      {file.type === 'directory' ? (
        <FolderGridThumb />
      ) : (
        <ArtifactGridThumb
          client={client}
          sessionId={sessionId}
          file={file}
        />
      )}
      <span className="line-clamp-2 w-full px-0.5 text-[11px] leading-tight">
        {file.name}
      </span>
      <span className="text-muted-foreground px-0.5 text-[10px]">
        {file.type === 'directory'
          ? 'Folder'
          : relativeTime(file.mtime)}
      </span>
    </button>
  )
}

export function ArtifactsBrowserGroups({
  client,
  sessionId,
  visibleGroups,
  viewMode,
  expandedGroups,
  activePath,
  empty,
  searchActive = false,
  onToggleGroup,
  onOpenFile,
  onDownloadFile,
  onFileContextMenu
}: {
  client: LocalAgentClient
  sessionId: string
  visibleGroups: ArtifactGroup[]
  viewMode: ViewMode
  expandedGroups: Record<string, boolean>
  activePath: string | null
  empty: boolean
  /** When true, show all matches flat instead of folder drill-down. */
  searchActive?: boolean
  onToggleGroup: (id: string) => void
  onOpenFile: (file: WorkspaceFile) => void
  onDownloadFile: (path: string) => void
  onFileContextMenu: (
    file: WorkspaceFile,
    x: number,
    y: number
  ) => void
}) {
  const [cwdByGroup, setCwdByGroup] = useState<Record<string, string>>({})

  const groupViews = useMemo(() => {
    return visibleGroups.map(group => {
      const root = groupRootPath(group.id)
      const cwd = searchActive ? root : (cwdByGroup[group.id] ?? root)
      const items = searchActive
        ? [...group.files].sort(compareArtifacts)
        : childrenOf(group.files, cwd)
      return { group, root, cwd, items }
    })
  }, [cwdByGroup, searchActive, visibleGroups])

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
        {groupViews.map(({ group, root, cwd, items }) => {
          const open = expandedGroups[group.id] ?? true
          const stamp = newestMtime(group.files)
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
                  {stamp ? ` · ${relativeTime(stamp)}` : ''}
                </span>
              </button>
              {open ? (
                <>
                  {!searchActive ? (
                    <GroupFolderTrail
                      root={root}
                      cwd={cwd}
                      onNavigate={path =>
                        setCwdByGroup(current => ({
                          ...current,
                          [group.id]: path
                        }))
                      }
                    />
                  ) : null}
                  {items.length === 0 ? (
                    <p className="text-muted-foreground px-1.5 py-1 text-[11px]">
                      Empty folder
                    </p>
                  ) : viewMode === 'grid' ? (
                    <div className="grid grid-cols-2 gap-2">
                      {items.map(file => (
                        <ArtifactEntryCard
                          key={file.path}
                          client={client}
                          sessionId={sessionId}
                          file={file}
                          activePath={activePath}
                          onOpen={entry => {
                            if (entry.type === 'directory' && !searchActive) {
                              setCwdByGroup(current => ({
                                ...current,
                                [group.id]: entry.path
                              }))
                              return
                            }
                            if (entry.type === 'file') onOpenFile(entry)
                          }}
                          onFileContextMenu={onFileContextMenu}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-0.5">
                      {items.map(file => (
                        <ArtifactEntryRow
                          key={file.path}
                          file={file}
                          activePath={activePath}
                          onOpen={entry => {
                            if (entry.type === 'directory' && !searchActive) {
                              setCwdByGroup(current => ({
                                ...current,
                                [group.id]: entry.path
                              }))
                              return
                            }
                            if (entry.type === 'file') onOpenFile(entry)
                          }}
                          onDownloadFile={onDownloadFile}
                          onFileContextMenu={onFileContextMenu}
                        />
                      ))}
                    </div>
                  )}
                </>
              ) : null}
            </div>
          )
        })}
      </div>
    </ScrollArea>
  )
}
