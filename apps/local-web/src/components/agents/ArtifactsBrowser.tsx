import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFile } from '@sandwalk/agent-ui-core'
import {
  Download,
  FilePlus,
  FolderPlus,
  LayoutGrid,
  List,
  MoreHorizontal,
  RefreshCw,
  Search,
  Upload
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'

import { ArtifactsBrowserGroups } from './artifacts-browser-groups'
import {
  ArtifactsBrowserScopeMenu,
  useArtifactsBrowserScope
} from './artifacts-browser-toolbar'
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
  const scopeState = useArtifactsBrowserScope(groups, totalCount)

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2 px-2 py-2">
        <ArtifactsBrowserScopeMenu
          groups={groups}
          totalCount={totalCount}
          scope={scopeState.scope}
          scopeLabel={scopeState.scopeLabel}
          menuOpen={scopeState.menuOpen}
          onMenuOpenChange={scopeState.setMenuOpen}
          onScopeChange={scopeState.setScope}
          onUpload={onUpload}
          onNewFile={onNewFile}
          onNewFolder={onNewFolder}
          onRefresh={onRefresh}
        />

        <div className="bg-muted/40 border-border/60 flex h-8 w-full items-center gap-1 rounded-md border px-1.5">
          <Search className="text-muted-foreground size-3.5 shrink-0" />
          <input
            value={query}
            onChange={event => onQueryChange(event.target.value)}
            placeholder="Search artifacts..."
            className="text-foreground placeholder:text-muted-foreground min-w-0 flex-1 bg-transparent text-xs outline-none"
          />
          <span className="text-muted-foreground shrink-0 whitespace-nowrap pr-0.5 text-[11px]">
            {scopeState.visibleCount} artifact
            {scopeState.visibleCount === 1 ? '' : 's'}
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
                disabled={scopeState.visibleCount === 0}
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

      <ArtifactsBrowserGroups
        client={client}
        sessionId={sessionId}
        visibleGroups={scopeState.visibleGroups}
        viewMode={viewMode}
        expandedGroups={expandedGroups}
        activePath={activePath}
        empty={empty}
        onToggleGroup={onToggleGroup}
        onOpenFile={onOpenFile}
        onDownloadFile={onDownloadFile}
      />
    </div>
  )
}
