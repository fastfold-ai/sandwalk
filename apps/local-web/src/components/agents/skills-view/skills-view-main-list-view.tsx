import type {
  AgentCatalogLeaderboardView,
  AgentCatalogSkill,
  AgentSkill
} from '@sandwalk/agent-ui-core'
import { useState } from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'

import {
  SkillsCatalogResultsSection,
  SkillsInstalledGridSection
} from './skills-view-list-content'
import { SkillsListSidebar } from './skills-view-list-sidebar'
import { SkillsMainListToolbar } from './skills-view-main-list-toolbar'
import { SkillsRemoveDialog } from './skills-view-shared'

export function SkillsMainListView({
  skills,
  loading,
  embedded,
  query,
  categoryFilter,
  authorFilter,
  statusFilter,
  categories,
  authors,
  categoryCounts,
  authorCounts,
  featuredCount,
  enabledCount,
  disabledCount,
  featuredVisible,
  nonFeaturedVisible,
  visible,
  disableEligibleCount,
  enableEligibleCount,
  removeEligibleCount,
  catalogSearchMode,
  catalogSearchEnabled,
  catalogLoading,
  catalogLoadingMore,
  catalogRefreshing,
  catalogError,
  catalogResults,
  catalogTotal,
  catalogHasMore,
  allTimeTotal,
  leaderboardView,
  onLeaderboardViewChange,
  onLoadMoreLeaderboard,
  onRefreshLeaderboard,
  showCatalogEmptyState,
  batchBusy,
  batchToast,
  pendingEnabled,
  pendingRemove,
  removeTarget,
  isCatalogSkillInstalled,
  onQueryChange,
  onCategoryFilterChange,
  onAuthorFilterChange,
  onStatusFilterChange,
  onCatalogSearchModeChange,
  onEnableCatalogSearchMode,
  onOpenImportGithub,
  onOpenImportFile,
  onOpenTrustedSources,
  onOpen,
  onOpenCatalogDetail,
  onToggleEnabled,
  onRemove,
  onSetFilteredEnabled,
  onRemoveFiltered,
  onRemoveDialogOpenChange,
  onConfirmRemove
}: {
  skills: AgentSkill[]
  loading: boolean
  embedded: boolean
  query: string
  categoryFilter: string
  authorFilter: string
  statusFilter: 'all' | 'enabled' | 'disabled'
  categories: string[]
  authors: string[]
  categoryCounts: Record<string, number>
  authorCounts: Record<string, number>
  featuredCount: number
  enabledCount: number
  disabledCount: number
  featuredVisible: AgentSkill[]
  nonFeaturedVisible: AgentSkill[]
  visible: AgentSkill[]
  disableEligibleCount: number
  enableEligibleCount: number
  removeEligibleCount: number
  catalogSearchMode: boolean
  catalogSearchEnabled: boolean
  catalogLoading: boolean
  catalogLoadingMore: boolean
  catalogRefreshing: boolean
  catalogError: string | null
  catalogResults: AgentCatalogSkill[]
  catalogTotal: number
  catalogHasMore: boolean
  allTimeTotal: number
  leaderboardView: AgentCatalogLeaderboardView
  onLeaderboardViewChange: (view: AgentCatalogLeaderboardView) => void
  onLoadMoreLeaderboard: () => void
  onRefreshLeaderboard: () => void
  showCatalogEmptyState: boolean
  batchBusy: boolean
  batchToast: { message: string; tone: 'success' | 'warning' } | null
  pendingEnabled: Record<string, boolean>
  pendingRemove: Record<string, boolean>
  removeTarget:
    | { type: 'single'; name: string }
    | { type: 'filtered'; count: number }
    | null
  isCatalogSkillInstalled: (skill: AgentCatalogSkill) => boolean
  onQueryChange: (value: string) => void
  onCategoryFilterChange: (value: string) => void
  onAuthorFilterChange: (value: string) => void
  onStatusFilterChange: (value: 'all' | 'enabled' | 'disabled') => void
  onCatalogSearchModeChange: (enabled: boolean) => void
  onEnableCatalogSearchMode: () => void
  onOpenImportGithub: () => void
  onOpenImportFile: () => void
  onOpenTrustedSources: () => void
  onOpen: (name: string) => void
  onOpenCatalogDetail: (skill: AgentCatalogSkill) => void
  onToggleEnabled: (name: string, enabled: boolean) => void
  onRemove: (name: string) => void
  onSetFilteredEnabled: (enabled: boolean) => void
  onRemoveFiltered: () => void
  onRemoveDialogOpenChange: (open: boolean) => void
  onConfirmRemove: () => void
}) {
  const [filtersOpen, setFiltersOpen] = useState(false)
  const activeFilterCount =
    (statusFilter !== 'all' ? 1 : 0) +
    (categoryFilter !== 'all' ? 1 : 0) +
    (authorFilter !== 'all' ? 1 : 0)
  const sidebarProps = {
    skills,
    statusFilter,
    categoryFilter,
    authorFilter,
    categories,
    authors,
    categoryCounts,
    authorCounts,
    featuredCount,
    enabledCount,
    disabledCount,
    onStatusFilterChange,
    onCategoryFilterChange,
    onAuthorFilterChange
  }

  return (
    <>
      <ScrollArea className={embedded ? 'h-[min(22rem,45vh)]' : 'flex-1'}>
        <div
          className={
            embedded
              ? 'mx-auto flex w-full max-w-5xl flex-col gap-6 p-1 xl:flex-row'
              : 'mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6 xl:flex-row'
          }
        >
          <div className="min-w-0 flex-1">
            {!embedded ? (
              <div className="mb-4">
                <h2 className="text-2xl font-semibold">Skills</h2>
                <p className="text-muted-foreground mt-1 text-sm">
                  Packaged instructions and scripts the agent can load on demand.
                  Install from the catalog or GitHub, and toggle which are active.
                </p>
              </div>
            ) : null}
            <SkillsMainListToolbar
              query={query}
              catalogSearchMode={catalogSearchMode}
              catalogSearchEnabled={catalogSearchEnabled}
              activeFilterCount={activeFilterCount}
              onOpenFilters={
                catalogSearchMode ? undefined : () => setFiltersOpen(true)
              }
              onQueryChange={onQueryChange}
              onCatalogSearchModeChange={onCatalogSearchModeChange}
              onEnableCatalogSearchMode={onEnableCatalogSearchMode}
              onOpenImportGithub={onOpenImportGithub}
              onOpenImportFile={onOpenImportFile}
              onOpenTrustedSources={onOpenTrustedSources}
            />
            {catalogSearchMode ? (
              <SkillsCatalogResultsSection
                query={query}
                catalogLoading={catalogLoading}
                catalogLoadingMore={catalogLoadingMore}
                catalogRefreshing={catalogRefreshing}
                catalogError={catalogError}
                catalogResults={catalogResults}
                catalogTotal={catalogTotal}
                catalogHasMore={catalogHasMore}
                allTimeTotal={allTimeTotal}
                leaderboardView={leaderboardView}
                onLeaderboardViewChange={onLeaderboardViewChange}
                onLoadMoreLeaderboard={onLoadMoreLeaderboard}
                onRefreshLeaderboard={onRefreshLeaderboard}
                showCatalogEmptyState={showCatalogEmptyState}
                isCatalogSkillInstalled={isCatalogSkillInstalled}
                onOpenCatalogDetail={onOpenCatalogDetail}
              />
            ) : (
              <SkillsInstalledGridSection
                loading={loading}
                visible={visible}
                featuredVisible={featuredVisible}
                nonFeaturedVisible={nonFeaturedVisible}
                categoryFilter={categoryFilter}
                disableEligibleCount={disableEligibleCount}
                enableEligibleCount={enableEligibleCount}
                removeEligibleCount={removeEligibleCount}
                batchBusy={batchBusy}
                pendingEnabled={pendingEnabled}
                pendingRemove={pendingRemove}
                onOpen={onOpen}
                onToggleEnabled={onToggleEnabled}
                onRemove={onRemove}
                onSetFilteredEnabled={onSetFilteredEnabled}
                onRemoveFiltered={onRemoveFiltered}
              />
            )}
          </div>
          {!catalogSearchMode ? (
            <div className="hidden xl:block">
              <SkillsListSidebar {...sidebarProps} />
            </div>
          ) : null}
        </div>
      </ScrollArea>
      {!catalogSearchMode ? (
        <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
          <SheetContent
            side="right"
            className="w-[min(100vw,22rem)] gap-0 overflow-hidden p-0 sm:max-w-[22rem]"
          >
            <SheetHeader className="border-border/60 border-b px-4 py-3">
              <SheetTitle>Filters</SheetTitle>
              <SheetDescription>
                Narrow installed skills by status, category, or author.
              </SheetDescription>
            </SheetHeader>
            <ScrollArea className="h-[calc(100dvh-5.5rem)] px-3 py-3">
              <SkillsListSidebar
                {...sidebarProps}
                className="xl:static xl:max-h-none xl:w-full xl:overflow-visible"
              />
            </ScrollArea>
          </SheetContent>
        </Sheet>
      ) : null}
      {batchToast ? (
        <div
          className={cn(
            'fixed bottom-4 right-4 z-50 max-w-xs rounded-md border px-3 py-2 text-xs shadow-md',
            batchToast.tone === 'warning'
              ? 'border-amber-300/70 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-100'
              : 'border-border/70 bg-background/95 text-foreground'
          )}
          role="status"
          aria-live="polite"
        >
          {batchToast.message}
        </div>
      ) : null}
      <SkillsRemoveDialog
        removeTarget={removeTarget}
        onOpenChange={onRemoveDialogOpenChange}
        onConfirm={onConfirmRemove}
      />
    </>
  )
}
