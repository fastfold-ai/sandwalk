import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFile } from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronDown,
  Download,
  FilePlus,
  Folder,
  FolderPlus,
  LayoutGrid,
  List,
  MoreHorizontal,
  Network,
  Paperclip,
  Plus,
  RefreshCw,
  Search,
  Upload
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { getFileIcon } from '@/lib/file-icons'
import { cn, relativeTime } from '@/lib/utils'

import { ArtifactGridThumb } from './ArtifactGridThumb'
import type { ArtifactGroup, ViewMode } from './workspace-utils'

export function ArtifactsBrowser({
  client,
  sessionId,
  groups,
  totalCount,
  query,
  viewMode,
  expandedGroups,
  activePath,
  empty,
  onQueryChange,
  onViewModeChange,
  onToggleGroup,
  onOpenFile,
  onDownloadFile,
  onDownloadAll,
  onUpload,
  onNewFile,
  onNewFolder,
  onRefresh
}: {
  client: LocalAgentClient
  sessionId: string
  groups: ArtifactGroup[]
  totalCount: number
  query: string
  viewMode: ViewMode
  expandedGroups: Record<string, boolean>
  activePath: string | null
  empty: boolean
  onQueryChange: (value: string) => void
  onViewModeChange: (mode: ViewMode) => void
  onToggleGroup: (id: string) => void
  onOpenFile: (file: WorkspaceFile) => void
  onDownloadFile: (path: string) => void
  onDownloadAll: () => void
  onUpload: () => void
  onNewFile: () => void
  onNewFolder: () => void
  onRefresh: () => void
}) {
  const [scope, setScope] = useState<string>('all')
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (scope === 'all') return
    if (!groups.some(group => group.id === scope)) setScope('all')
  }, [groups, scope])

  const visibleGroups = useMemo(() => {
    if (scope === 'all') return groups
    return groups.filter(group => group.id === scope)
  }, [groups, scope])

  const visibleCount = useMemo(
    () => visibleGroups.reduce((sum, group) => sum + group.files.length, 0),
    [visibleGroups]
  )

  const scopeLabel =
    scope === 'all'
      ? 'Artifacts'
      : groups.find(group => group.id === scope)?.title || 'Artifacts'

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2 px-2 py-2">
        <Popover open={menuOpen} onOpenChange={setMenuOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="hover:bg-muted inline-flex h-8 max-w-full items-center gap-1.5 rounded-md px-2 text-xs font-medium"
            >
              <Network className="size-3.5 shrink-0" />
              <span className="truncate">{scopeLabel}</span>
              <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-64 p-1.5">
            <div className="text-muted-foreground px-2 py-1 text-[10px] font-medium uppercase tracking-wide">
              Artifacts
            </div>
            <button
              type="button"
              className={cn(
                'hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                scope === 'all' && 'bg-muted'
              )}
              onClick={() => {
                setScope('all')
                setMenuOpen(false)
              }}
            >
              <Network className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">All artifacts</span>
              {scope === 'all' ? (
                <Check className="size-3.5 shrink-0 text-sky-500" />
              ) : null}
              <span className="text-muted-foreground shrink-0 text-xs">
                {totalCount}
              </span>
            </button>
            {groups.map(group => {
              const icon =
                group.id === 'Your uploads' ? (
                  <Paperclip className="size-3.5 shrink-0" />
                ) : (
                  <Folder className="size-3.5 shrink-0" />
                )
              return (
                <button
                  key={group.id}
                  type="button"
                  className={cn(
                    'hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                    scope === group.id && 'bg-muted'
                  )}
                  onClick={() => {
                    setScope(group.id)
                    setMenuOpen(false)
                  }}
                >
                  {icon}
                  <span className="min-w-0 flex-1 truncate">{group.title}</span>
                  {scope === group.id ? (
                    <Check className="size-3.5 shrink-0 text-sky-500" />
                  ) : null}
                  <span className="text-muted-foreground shrink-0 text-xs">
                    {group.files.length}
                  </span>
                </button>
              )
            })}
            <div className="bg-border my-1.5 h-px" />
            <div className="text-muted-foreground px-2 py-1 text-[10px] font-medium uppercase tracking-wide">
              This computer
            </div>
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              onClick={() => {
                setMenuOpen(false)
                onUpload()
              }}
            >
              <Upload className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">Upload files…</span>
            </button>
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              onClick={() => {
                setMenuOpen(false)
                onNewFile()
              }}
            >
              <FilePlus className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">New file…</span>
            </button>
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              onClick={() => {
                setMenuOpen(false)
                onNewFolder()
              }}
            >
              <Plus className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">Add folder…</span>
            </button>
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              onClick={() => {
                setMenuOpen(false)
                onRefresh()
              }}
            >
              <RefreshCw className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">Refresh</span>
            </button>
          </PopoverContent>
        </Popover>

        <div className="bg-muted/40 border-border/60 flex h-8 w-full items-center gap-1 rounded-md border px-1.5">
          <Search className="text-muted-foreground size-3.5 shrink-0" />
          <input
            value={query}
            onChange={event => onQueryChange(event.target.value)}
            placeholder="Search artifacts..."
            className="text-foreground placeholder:text-muted-foreground min-w-0 flex-1 bg-transparent text-xs outline-none"
          />
          <span className="text-muted-foreground shrink-0 whitespace-nowrap pr-0.5 text-[11px]">
            {visibleCount} artifact{visibleCount === 1 ? '' : 's'}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={cn('size-6', viewMode === 'grid' && 'bg-muted')}
            title="Grid view"
            onClick={() => onViewModeChange('grid')}
          >
            <LayoutGrid className="size-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={cn('size-6', viewMode === 'list' && 'bg-muted')}
            title="List view"
            onClick={() => onViewModeChange('list')}
          >
            <List className="size-3.5" />
          </Button>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-6"
                title="More actions"
              >
                <MoreHorizontal className="size-3.5" />
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-48 p-1.5">
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm disabled:opacity-40"
                disabled={visibleCount === 0}
                onClick={onDownloadAll}
              >
                <Download className="size-3.5" />
                Download artifacts…
              </button>
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                onClick={onUpload}
              >
                <Upload className="size-3.5" />
                Upload files…
              </button>
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                onClick={onNewFile}
              >
                <FilePlus className="size-3.5" />
                New file…
              </button>
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                onClick={onNewFolder}
              >
                <FolderPlus className="size-3.5" />
                New folder…
              </button>
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                onClick={onRefresh}
              >
                <RefreshCw className="size-3.5" />
                Refresh
              </button>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      {empty ? (
        <div className="text-muted-foreground/70 flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-3 text-center">
          <Folder className="size-9 opacity-70" />
          <p className="text-xs">No files yet</p>
        </div>
      ) : visibleGroups.length === 0 ? (
        <div className="text-muted-foreground/70 flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-3 text-center">
          <Folder className="size-9 opacity-70" />
          <p className="text-xs">No artifacts in this scope</p>
        </div>
      ) : (
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
      )}
    </div>
  )
}
