import {
  Check,
  ChevronDown,
  FilePlus,
  Folder,
  Network,
  Paperclip,
  Plus,
  RefreshCw,
  Upload
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'

import type { ArtifactGroup } from './workspace-utils'

export function useArtifactsBrowserScope(groups: ArtifactGroup[], _totalCount: number) {
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

  return {
    scope,
    setScope,
    menuOpen,
    setMenuOpen,
    visibleGroups,
    visibleCount,
    scopeLabel
  }
}

export function ArtifactsBrowserScopeMenu({
  groups,
  totalCount,
  scope,
  scopeLabel,
  menuOpen,
  onMenuOpenChange,
  onScopeChange,
  onUpload,
  onNewFile,
  onNewFolder,
  onRefresh
}: {
  groups: ArtifactGroup[]
  totalCount: number
  scope: string
  scopeLabel: string
  menuOpen: boolean
  onMenuOpenChange: (open: boolean) => void
  onScopeChange: (scope: string) => void
  onUpload: () => void
  onNewFile: () => void
  onNewFolder: () => void
  onRefresh: () => void
}) {
  return (
    <Popover open={menuOpen} onOpenChange={onMenuOpenChange}>
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
            onScopeChange('all')
            onMenuOpenChange(false)
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
                onScopeChange(group.id)
                onMenuOpenChange(false)
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
            onMenuOpenChange(false)
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
            onMenuOpenChange(false)
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
            onMenuOpenChange(false)
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
            onMenuOpenChange(false)
            onRefresh()
          }}
        >
          <RefreshCw className="size-3.5 shrink-0" />
          <span className="min-w-0 flex-1 truncate">Refresh</span>
        </button>
      </PopoverContent>
    </Popover>
  )
}
