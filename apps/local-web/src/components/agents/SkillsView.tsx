import type {
  AgentCatalogLeaderboardView,
  AgentCatalogSkill,
  AgentSkill,
  AgentSkillBatchAction,
  AgentSkillBatchResult,
  AgentSkillDetail,
  AgentSkillSource
} from '@sandwalk/agent-ui-core'

import { type SkillsViewMode } from '@/lib/skills-catalog'

import {
  SkillsFeaturedOverview,
  SkillsMainListView
} from './skills-view/skills-view-list'
import { SkillsViewDetailMode } from './skills-view/skills-view-mode-detail'
import {
  SkillsViewCatalogMode,
  SkillsViewImportFileMode,
  SkillsViewImportGithubMode,
  SkillsViewTrustedSourcesMode
} from './skills-view/skills-view-mode-views'
import { useSkillsViewState } from './skills-view/use-skills-view-state'

export function SkillsView({
  mode,
  skills,
  loading = false,
  detail,
  catalogSkillRoute,
  catalogSearchEnabled,
  openCatalogSearchInitially = false,
  featuredOnly = false,
  onShowAll,
  onOpen,
  onOpenCatalogDetail,
  onBack,
  onOpenImportGithub,
  onOpenImportFile,
  onOpenTrustedSources,
  onOpenCatalogSetup,
  onInstall,
  onUpload,
  onLoadSuggestedSources,
  onSearchCatalog,
  onListCatalogLeaderboard,
  onGetCatalogDetail,
  onGetCatalogAudit,
  onBulkAction,
  onSetEnabled,
  onRemove,
  onUpgrade,
  embedded = false
}: {
  mode: SkillsViewMode
  skills: AgentSkill[]
  loading?: boolean
  detail: AgentSkillDetail | null
  catalogSkillRoute: { id: string; source: string; skill: string } | null
  catalogSearchEnabled: boolean
  openCatalogSearchInitially?: boolean
  featuredOnly?: boolean
  onShowAll?: () => void
  onOpen: (name: string) => void
  onOpenCatalogDetail: (skill: AgentCatalogSkill) => void
  onBack: () => void
  onOpenImportGithub: () => void
  onOpenImportFile: () => void
  onOpenTrustedSources: () => void
  onOpenCatalogSetup: () => void
  onInstall: (source: string) => Promise<string[] | void>
  onUpload: (file: File) => Promise<void>
  onLoadSuggestedSources: (signal?: AbortSignal) => Promise<AgentSkillSource[]>
  onSearchCatalog: (
    query: string,
    signal?: AbortSignal
  ) => Promise<AgentCatalogSkill[]>
  onListCatalogLeaderboard: (
    view: AgentCatalogLeaderboardView,
    options?: { page?: number; perPage?: number },
    signal?: AbortSignal
  ) => Promise<{
    data: AgentCatalogSkill[]
    total: number
    allTimeTotal: number
    hasMore: boolean
    page: number
  }>
  onGetCatalogDetail: (
    source: string,
    skill: string,
    signal?: AbortSignal
  ) => Promise<import('@sandwalk/agent-ui-core').AgentCatalogSkillDetail>
  onGetCatalogAudit: (
    source: string,
    skill: string,
    signal?: AbortSignal
  ) => Promise<import('@sandwalk/agent-ui-core').AgentCatalogSkillAudit>
  onBulkAction: (
    action: AgentSkillBatchAction,
    names: string[]
  ) => Promise<AgentSkillBatchResult>
  onSetEnabled: (name: string, enabled: boolean) => Promise<void>
  onRemove: (name: string) => Promise<void>
  onUpgrade: () => Promise<string[]>
  embedded?: boolean
}) {
  const state = useSkillsViewState({
    mode,
    skills,
    detail,
    catalogSkillRoute,
    catalogSearchEnabled,
    openCatalogSearchInitially,
    onOpen,
    onBack,
    onOpenCatalogSetup,
    onInstall,
    onUpload,
    onLoadSuggestedSources,
    onSearchCatalog,
    onListCatalogLeaderboard,
    onGetCatalogDetail,
    onGetCatalogAudit,
    onBulkAction,
    onSetEnabled,
    onRemove,
    onUpgrade
  })

  if (mode === 'import_github') {
    return <SkillsViewImportGithubMode state={state} onBack={onBack} />
  }

  if (mode === 'import_file') {
    return <SkillsViewImportFileMode state={state} onBack={onBack} />
  }

  if (mode === 'trusted_sources') {
    return <SkillsViewTrustedSourcesMode state={state} onBack={onBack} />
  }

  if (mode === 'catalog_detail') {
    return (
      <SkillsViewCatalogMode
        state={state}
        catalogSkillRoute={catalogSkillRoute}
        onBack={onBack}
      />
    )
  }

  if (mode === 'detail' && detail) {
    return (
      <SkillsViewDetailMode
        detail={detail}
        catalogSearchEnabled={catalogSearchEnabled}
        state={state}
        onBack={onBack}
      />
    )
  }

  if (featuredOnly) {
    return (
      <SkillsFeaturedOverview
        skills={skills}
        loading={loading}
        pendingEnabled={state.pendingEnabled}
        pendingRemove={state.pendingRemove}
        batchBusy={state.batchBusy}
        removeTarget={state.removeTarget}
        onShowAll={onShowAll}
        onOpen={onOpen}
        onToggleEnabled={(name, enabled) => void state.setSkillEnabled(name, enabled)}
        onRemove={state.removeSkill}
        onRemoveDialogOpenChange={state.handleRemoveDialogOpenChange}
        onConfirmRemove={() => void state.confirmRemoveSkill()}
      />
    )
  }

  return (
    <SkillsMainListView
      skills={skills}
      loading={loading}
      embedded={embedded}
      query={state.query}
      categoryFilter={state.categoryFilter}
      authorFilter={state.authorFilter}
      statusFilter={state.statusFilter}
      categories={state.listData.categories}
      authors={state.listData.authors}
      categoryCounts={state.listData.categoryCounts}
      authorCounts={state.listData.authorCounts}
      featuredCount={state.listData.featuredCount}
      enabledCount={state.listData.enabledCount}
      disabledCount={state.listData.disabledCount}
      featuredVisible={state.listData.featuredVisible}
      nonFeaturedVisible={state.listData.nonFeaturedVisible}
      visible={state.listData.visible}
      disableEligibleCount={state.listData.disableEligibleCount}
      enableEligibleCount={state.listData.enableEligibleCount}
      removeEligibleCount={state.listData.removeEligibleCount}
      catalogSearchMode={state.catalogSearchMode}
      catalogSearchEnabled={catalogSearchEnabled}
      catalogLoading={state.catalogLoading}
      catalogLoadingMore={state.catalogLoadingMore}
      catalogRefreshing={state.catalogRefreshing}
      catalogError={state.catalogError}
      catalogResults={state.catalogResults}
      catalogTotal={state.catalogTotal}
      catalogHasMore={state.catalogHasMore}
      allTimeTotal={state.allTimeTotal}
      leaderboardView={state.leaderboardView}
      onLeaderboardViewChange={state.setLeaderboardView}
      onLoadMoreLeaderboard={state.loadMoreLeaderboard}
      onRefreshLeaderboard={state.refreshLeaderboard}
      showCatalogEmptyState={state.showCatalogEmptyState}
      batchBusy={state.batchBusy}
      batchToast={state.batchToast}
      pendingEnabled={state.pendingEnabled}
      pendingRemove={state.pendingRemove}
      removeTarget={state.removeTarget}
      isCatalogSkillInstalled={state.checkCatalogSkillInstalled}
      onQueryChange={state.setQuery}
      onCategoryFilterChange={state.setCategoryFilter}
      onAuthorFilterChange={state.setAuthorFilter}
      onStatusFilterChange={state.setStatusFilter}
      onCatalogSearchModeChange={enabled => {
        if (!enabled) {
          state.setCatalogSearchMode(false)
          state.setCatalogResults([])
          state.setCatalogError(null)
        }
      }}
      onEnableCatalogSearchMode={state.enableCatalogSearchMode}
      onOpenImportGithub={onOpenImportGithub}
      onOpenImportFile={onOpenImportFile}
      onOpenTrustedSources={onOpenTrustedSources}
      onOpen={onOpen}
      onOpenCatalogDetail={onOpenCatalogDetail}
      onToggleEnabled={(name, enabled) => void state.setSkillEnabled(name, enabled)}
      onRemove={state.removeSkill}
      onSetFilteredEnabled={enabled => void state.setFilteredEnabled(enabled)}
      onRemoveFiltered={() => void state.removeFiltered()}
      onRemoveDialogOpenChange={state.handleRemoveDialogOpenChange}
      onConfirmRemove={() => void state.confirmRemoveSkill()}
    />
  )
}
