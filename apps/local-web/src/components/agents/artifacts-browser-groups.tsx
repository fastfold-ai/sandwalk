import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFile } from '@sandwalk/agent-ui-core'
import { ChevronDown, ChevronRight, Folder } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { setWorkspacePathDragData } from '@/components/agents/composer/workspace-path-drag'
import { ScrollArea } from '@/components/ui/scroll-area'
import { getFileIcon } from '@/lib/file-icons'
import { cn, relativeTime } from '@/lib/utils'

import { ArtifactGridThumb } from './ArtifactGridThumb'
import {
  type ArtifactGroup,
  childrenOf,
  compareArtifacts,
  groupRootPath,
  parentDir,
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

function ancestorPaths(path: string): string[] {
  const parts = path.split('/').filter(Boolean)
  const out: string[] = []
  for (let i = 1; i < parts.length; i += 1) {
    out.push(parts.slice(0, i).join('/'))
  }
  return out
}

function ArtifactEntryRow({
  file,
  label,
  depth,
  expanded,
  activePath,
  onToggleExpand,
  onOpen,
  onFileContextMenu
}: {
  file: WorkspaceFile
  label: string
  depth: number
  expanded: boolean
  activePath: string | null
  onToggleExpand?: () => void
  onOpen: (file: WorkspaceFile) => void
  onFileContextMenu: (file: WorkspaceFile, x: number, y: number) => void
}) {
  const draggedRef = useRef(false)
  const isFolder = file.type === 'directory'
  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      className={cn(
        'hover:bg-muted group/file flex w-full cursor-pointer items-center gap-1 rounded py-1 pr-1.5',
        activePath === file.path && 'bg-muted'
      )}
      style={{ paddingLeft: 4 + depth * 12 }}
      onDragStart={event => {
        draggedRef.current = true
        setWorkspacePathDragData(event.dataTransfer, {
          path: file.path,
          type: file.type
        })
      }}
      onDragEnd={() => {
        window.setTimeout(() => {
          draggedRef.current = false
        }, 0)
      }}
      onClick={() => {
        if (draggedRef.current) return
        if (isFolder) {
          onToggleExpand?.()
          return
        }
        onOpen(file)
      }}
      onContextMenu={event => {
        event.preventDefault()
        onFileContextMenu(file, event.clientX, event.clientY)
      }}
      onKeyDown={event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          if (isFolder) {
            onToggleExpand?.()
            return
          }
          onOpen(file)
        }
      }}
    >
      {isFolder ? (
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground inline-flex size-4 shrink-0 items-center justify-center rounded"
          aria-label={expanded ? 'Collapse folder' : 'Expand folder'}
          onClick={event => {
            event.stopPropagation()
            onToggleExpand?.()
          }}
        >
          {expanded ? (
            <ChevronDown className="size-3.5" />
          ) : (
            <ChevronRight className="size-3.5" />
          )}
        </button>
      ) : (
        <span className="inline-flex size-4 shrink-0" aria-hidden />
      )}
      {isFolder ? (
        <Folder className="text-muted-foreground size-3.5 shrink-0" />
      ) : (
        <Icon icon={getFileIcon(file.name)} className="size-3.5 shrink-0" />
      )}
      <span className="min-w-0 flex-1 truncate text-left text-[11px]">
        {label}
      </span>
      <span className="text-muted-foreground w-14 shrink-0 text-right text-[10px] tabular-nums whitespace-nowrap">
        {relativeTime(file.mtime)}
      </span>
    </div>
  )
}

function ArtifactTreeNodes({
  entries,
  parentPath,
  depth,
  expandedDirs,
  activePath,
  onToggleDir,
  onOpenFile,
  onFileContextMenu
}: {
  entries: WorkspaceFile[]
  parentPath: string
  depth: number
  expandedDirs: Record<string, boolean>
  activePath: string | null
  onToggleDir: (path: string) => void
  onOpenFile: (file: WorkspaceFile) => void
  onFileContextMenu: (file: WorkspaceFile, x: number, y: number) => void
}) {
  const children = childrenOf(entries, parentPath)
  return (
    <>
      {children.map(file => {
        const open = Boolean(expandedDirs[file.path])
        return (
          <div key={file.path}>
            <ArtifactEntryRow
              file={file}
              label={file.name}
              depth={depth}
              expanded={open}
              activePath={activePath}
              onToggleExpand={
                file.type === 'directory'
                  ? () => onToggleDir(file.path)
                  : undefined
              }
              onOpen={onOpenFile}
              onFileContextMenu={onFileContextMenu}
            />
            {file.type === 'directory' && open ? (
              <ArtifactTreeNodes
                entries={entries}
                parentPath={file.path}
                depth={depth + 1}
                expandedDirs={expandedDirs}
                activePath={activePath}
                onToggleDir={onToggleDir}
                onOpenFile={onOpenFile}
                onFileContextMenu={onFileContextMenu}
              />
            ) : null}
          </div>
        )
      })}
    </>
  )
}

function ArtifactEntryCard({
  client,
  sessionId,
  file,
  label,
  activePath,
  onOpen,
  onFileContextMenu
}: {
  client: LocalAgentClient
  sessionId: string
  file: WorkspaceFile
  label: string
  activePath: string | null
  onOpen: (file: WorkspaceFile) => void
  onFileContextMenu: (file: WorkspaceFile, x: number, y: number) => void
}) {
  const draggedRef = useRef(false)
  return (
    // div (not button): structure thumbs embed control stubs; nested <button> is invalid HTML.
    <div
      role="button"
      tabIndex={0}
      draggable
      className={cn(
        'hover:bg-muted/60 group/file flex cursor-pointer flex-col items-stretch gap-1.5 rounded-md border border-transparent p-1.5 text-left transition-colors',
        activePath === file.path && 'bg-muted border-border'
      )}
      onDragStart={event => {
        draggedRef.current = true
        setWorkspacePathDragData(event.dataTransfer, {
          path: file.path,
          type: file.type
        })
      }}
      onDragEnd={() => {
        window.setTimeout(() => {
          draggedRef.current = false
        }, 0)
      }}
      onClick={() => {
        if (draggedRef.current) return
        onOpen(file)
      }}
      onKeyDown={event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen(file)
        }
      }}
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
        {label}
      </span>
      <span className="text-muted-foreground px-0.5 text-[10px]">
        {file.type === 'directory'
          ? 'Folder'
          : relativeTime(file.mtime)}
      </span>
    </div>
  )
}

export function ArtifactsBrowserGroups({
  client,
  sessionId,
  visibleGroups,
  viewMode,
  expandedGroups,
  expandedDirs,
  activePath,
  empty,
  searchActive = false,
  onToggleGroup,
  onToggleDir,
  onExpandedDirsChange,
  onOpenFile,
  onFileContextMenu
}: {
  client: LocalAgentClient
  sessionId: string
  visibleGroups: ArtifactGroup[]
  viewMode: ViewMode
  expandedGroups: Record<string, boolean>
  expandedDirs: Record<string, boolean>
  activePath: string | null
  empty: boolean
  /** When true, show filtered matches flat (search). */
  searchActive?: boolean
  onToggleGroup: (id: string) => void
  onToggleDir: (path: string) => void
  onExpandedDirsChange: (
    value:
      | Record<string, boolean>
      | ((current: Record<string, boolean>) => Record<string, boolean>)
  ) => void
  onOpenFile: (file: WorkspaceFile) => void
  onFileContextMenu: (
    file: WorkspaceFile,
    x: number,
    y: number
  ) => void
}) {
  const [gridCwdByGroup, setGridCwdByGroup] = useState<Record<string, string>>(
    {}
  )

  // Keep the open file visible by expanding its ancestor folders.
  useEffect(() => {
    if (!activePath) return
    const parents = ancestorPaths(activePath)
    if (parents.length === 0) return
    onExpandedDirsChange(current => {
      let changed = false
      const next = { ...current }
      for (const path of parents) {
        if (!next[path]) {
          next[path] = true
          changed = true
        }
      }
      return changed ? next : current
    })
  }, [activePath, onExpandedDirsChange])

  const searchItemsByGroup = useMemo(() => {
    if (!searchActive) return null
    return visibleGroups.map(group => ({
      group,
      items: [...group.files]
        .filter(file => file.type === 'file')
        .sort(compareArtifacts)
    }))
  }, [searchActive, visibleGroups])

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
      <div className="space-y-1 p-2">
        {visibleGroups.map(group => {
          const open = expandedGroups[group.id] ?? true
          const stamp = newestMtime(group.files)
          const root = groupRootPath(group.id)
          const searchItems =
            searchItemsByGroup?.find(item => item.group.id === group.id)
              ?.items || []

          return (
            <div key={group.id}>
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground hover:bg-muted flex w-full items-center gap-1 rounded px-1 py-1 text-left text-[11px]"
                onClick={() => onToggleGroup(group.id)}
              >
                {open ? (
                  <ChevronDown className="size-3.5 shrink-0" />
                ) : (
                  <ChevronRight className="size-3.5 shrink-0" />
                )}
                <Folder className="size-3.5 shrink-0 opacity-80" />
                <span className="min-w-0 flex-1 truncate font-medium">
                  {group.title}
                </span>
                <span className="shrink-0 whitespace-nowrap">
                  {group.files.length}
                  {stamp ? ` · ${relativeTime(stamp)}` : ''}
                </span>
              </button>
              {open ? (
                searchActive ? (
                  searchItems.length === 0 ? (
                    <p className="text-muted-foreground px-1.5 py-1 text-[11px]">
                      No matches
                    </p>
                  ) : viewMode === 'grid' ? (
                    <div className="grid grid-cols-2 gap-2 pt-1">
                      {searchItems.map(file => (
                        <ArtifactEntryCard
                          key={file.path}
                          client={client}
                          sessionId={sessionId}
                          file={file}
                          label={
                            root && file.path.startsWith(`${root}/`)
                              ? file.path.slice(root.length + 1)
                              : file.path
                          }
                          activePath={activePath}
                          onOpen={entry => {
                            if (entry.type === 'file') onOpenFile(entry)
                          }}
                          onFileContextMenu={onFileContextMenu}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-0.5">
                      {searchItems.map(file => (
                        <ArtifactEntryRow
                          key={file.path}
                          file={file}
                          label={
                            root && file.path.startsWith(`${root}/`)
                              ? file.path.slice(root.length + 1)
                              : file.path
                          }
                          depth={1}
                          expanded={false}
                          activePath={activePath}
                          onOpen={onOpenFile}
                          onFileContextMenu={onFileContextMenu}
                        />
                      ))}
                    </div>
                  )
                ) : viewMode === 'grid' ? (
                  <GridFolderView
                    client={client}
                    sessionId={sessionId}
                    group={group}
                    root={root}
                    cwd={gridCwdByGroup[group.id] ?? root}
                    activePath={activePath}
                    onNavigate={path =>
                      setGridCwdByGroup(current => ({
                        ...current,
                        [group.id]: path
                      }))
                    }
                    onOpenFile={onOpenFile}
                    onFileContextMenu={onFileContextMenu}
                  />
                ) : childrenOf(group.files, root).length === 0 ? (
                  <p className="text-muted-foreground px-1.5 py-1 text-[11px]">
                    Empty folder
                  </p>
                ) : (
                  <ArtifactTreeNodes
                    entries={group.files}
                    parentPath={root}
                    depth={1}
                    expandedDirs={expandedDirs}
                    activePath={activePath}
                    onToggleDir={onToggleDir}
                    onOpenFile={onOpenFile}
                    onFileContextMenu={onFileContextMenu}
                  />
                )
              ) : null}
            </div>
          )
        })}
      </div>
    </ScrollArea>
  )
}

function GridFolderView({
  client,
  sessionId,
  group,
  root,
  cwd,
  activePath,
  onNavigate,
  onOpenFile,
  onFileContextMenu
}: {
  client: LocalAgentClient
  sessionId: string
  group: ArtifactGroup
  root: string
  cwd: string
  activePath: string | null
  onNavigate: (path: string) => void
  onOpenFile: (file: WorkspaceFile) => void
  onFileContextMenu: (file: WorkspaceFile, x: number, y: number) => void
}) {
  const items = childrenOf(group.files, cwd)
  const relative = root ? cwd.slice(root.length).replace(/^\//, '') : cwd
  const segments = relative.split('/').filter(Boolean)

  return (
    <div className="space-y-1 pt-1">
      {cwd !== root ? (
        <div className="text-muted-foreground flex min-w-0 items-center gap-0.5 px-1 pb-1 text-[11px]">
          <button
            type="button"
            className="hover:text-foreground inline-flex size-5 shrink-0 items-center justify-center rounded"
            title="Go up"
            aria-label="Go up"
            onClick={() => onNavigate(parentDir(cwd) || root)}
          >
            <ChevronRight className="size-3.5 rotate-180" />
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
              <span
                key={path}
                className="inline-flex min-w-0 items-center gap-0.5"
              >
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
      ) : null}
      {items.length === 0 ? (
        <p className="text-muted-foreground px-1.5 py-1 text-[11px]">
          Empty folder
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {items.map(file => (
            <ArtifactEntryCard
              key={file.path}
              client={client}
              sessionId={sessionId}
              file={file}
              label={file.name}
              activePath={activePath}
              onOpen={entry => {
                if (entry.type === 'directory') {
                  onNavigate(entry.path)
                  return
                }
                onOpenFile(entry)
              }}
              onFileContextMenu={onFileContextMenu}
            />
          ))}
        </div>
      )}
    </div>
  )
}
