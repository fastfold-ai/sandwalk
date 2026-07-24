import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFile } from '@sandwalk/agent-ui-core'
import {
  Download,
  FilePlus,
  FolderPlus,
  LayoutGrid,
  List,
  ListTree,
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
import { ArtifactsBrowserPathFooter } from './artifacts-browser-path-footer'
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
  flatMode = false,
  expandedGroups,
  activePath,
  empty,
  workspacePath = null,
  onQueryChange,
  onViewModeChange,
  onFlatModeChange,
  onToggleGroup,
  onOpenFile,
  onDownloadFile,
  onDownloadAll,
  onUpload,
  onNewFile,
  onNewFolder,
  onRefresh,
  refreshing = false,
  onFileContextMenu
}: {
  client: LocalAgentClient
  sessionId: string
  groups: ArtifactGroup[]
  totalCount: number
  query: string
  viewMode: ViewMode
  flatMode?: boolean
  expandedGroups: Record<string, boolean>
  activePath: string | null
  empty: boolean
  workspacePath?: string | null
  onQueryChange: (value: string) => void
  onViewModeChange: (mode: ViewMode) => void
  onFlatModeChange?: (flat: boolean) => void
  onToggleGroup: (id: string) => void
  onOpenFile: (file: WorkspaceFile) => void
  onDownloadFile: (path: string) => void
  onDownloadAll: () => void
  onUpload: () => void
  onNewFile: () => void
  onNewFolder: () => void
  onRefresh: () => void
  refreshing?: boolean
  onFileContextMenu: (file: WorkspaceFile, x: number, y: number) => void
}) {
  const scopeState = useArtifactsBrowserScope(groups, totalCount)
  const flatten = flatMode || query.trim().length > 0

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
          {onFlatModeChange ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className={cn('size-6', flatMode && 'bg-muted')}
              title={
                flatMode
                  ? 'Show folders (narrow)'
                  : 'Expand all folders (show every file)'
              }
              aria-label={
                flatMode ? 'Show folders' : 'Expand all folders'
              }
              aria-pressed={flatMode}
              onClick={() => onFlatModeChange(!flatMode)}
            >
              <ListTree className="size-3.5" />
            </Button>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-6"
            title="Refresh artifacts"
            aria-label="Refresh artifacts"
            disabled={refreshing}
            onClick={onRefresh}
          >
            <RefreshCw
              className={cn('size-3.5', refreshing && 'animate-spin')}
            />
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
        searchActive={flatten}
        onToggleGroup={onToggleGroup}
        onOpenFile={onOpenFile}
        onDownloadFile={onDownloadFile}
        onFileContextMenu={onFileContextMenu}
      />
      <ArtifactsBrowserPathFooter
        workspacePath={workspacePath}
        relativePath={activePath}
      />
    </div>
  )
}
