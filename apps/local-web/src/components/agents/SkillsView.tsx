import type {
  AgentCatalogSkill,
  AgentSkill,
  AgentSkillBatchAction,
  AgentSkillBatchResult,
  AgentSkillDetail,
  AgentSkillSource
} from '@sandwalk/agent-ui-core'

import { DetailPageSkeleton } from '@/components/agents/PageSkeletons'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  catalogSkillInstallCommand,
  catalogSkillInstallTarget,
  type SkillsViewMode
} from '@/lib/skills-catalog'

import { SkillsCatalogDetailView } from './skills-view/skills-view-catalog-detail'
import {
  SkillsImportFileView,
  SkillsImportGithubView,
  SkillsTrustedSourcesView
} from './skills-view/skills-view-import-views'
import { SkillsInstalledDetailView } from './skills-view/skills-view-installed-detail'
import {
  SkillsFeaturedOverview,
  SkillsMainListView
} from './skills-view/skills-view-list'
import { SkillsBreadcrumb } from './skills-view/skills-view-shared'
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
  onGetCatalogDetail,
  onGetCatalogAudit,
  onBulkAction,
  onSetEnabled,
  onRemove,
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
    onGetCatalogDetail,
    onGetCatalogAudit,
    onBulkAction,
    onSetEnabled,
    onRemove
  })

  if (mode === 'import_github') {
    return (
      <SkillsImportGithubView
        githubSource={state.githubSource}
        onGithubSourceChange={state.setGithubSource}
        installing={state.installing}
        onBack={onBack}
        onSubmit={() => void state.submitGithubInstall()}
      />
    )
  }

  if (mode === 'import_file') {
    return (
      <SkillsImportFileView
        uploadFile={state.uploadFile}
        uploadInputRef={state.uploadInputRef}
        onUploadFileChange={state.setUploadFile}
        installing={state.installing}
        onBack={onBack}
        onSubmit={() => void state.submitFileInstall()}
      />
    )
  }

  if (mode === 'trusted_sources') {
    return (
      <SkillsTrustedSourcesView
        trustedSources={state.trustedSources}
        trustedSelected={state.trustedSelected}
        onTrustedSelectedChange={state.setTrustedSelected}
        trustedLoading={state.trustedLoading}
        selectedTrustedSources={state.selectedTrustedSources}
        installing={state.installing}
        onBack={onBack}
        onSubmit={() => void state.submitTrustedInstall()}
      />
    )
  }

  if (mode === 'catalog_detail') {
    const catalogSource = String(
      state.catalogDetail?.source || catalogSkillRoute?.source || ''
    ).trim()
    const catalogSlug = String(
      state.catalogDetail?.slug || catalogSkillRoute?.skill || ''
    ).trim()
    const catalogFiles = state.catalogDetail?.files || []
    const catalogInstallTarget =
      catalogSource && catalogSlug
        ? catalogSkillInstallTarget(catalogSource, catalogSlug, catalogFiles)
        : ''
    const catalogInstallCommand =
      catalogSource && catalogSlug
        ? catalogSkillInstallCommand(catalogSource, catalogSlug, catalogFiles)
        : ''

    return (
      <SkillsCatalogDetailView
        catalogSkillRoute={catalogSkillRoute}
        catalogDetail={state.catalogDetail}
        catalogAudit={state.catalogAudit}
        catalogDetailLoading={state.catalogDetailLoading}
        catalogDetailError={state.catalogDetailError}
        catalogInstallingId={state.catalogInstallingId}
        installing={state.installing}
        catalogInstallError={state.catalogInstallError}
        copiedCatalogInstall={state.copiedCatalogInstall}
        isInstalled={state.checkCatalogSkillInstalled}
        onBack={onBack}
        onCopyInstall={() => {
          if (!catalogInstallCommand) return
          void navigator.clipboard.writeText(catalogInstallCommand).then(() => {
            state.setCopiedCatalogInstall(true)
          })
        }}
        onInstall={() =>
          void state.submitCatalogInstallSource(
            catalogInstallTarget,
            String(state.catalogDetail?.id || catalogSkillRoute?.id || '').trim() ||
              'catalog-detail',
            catalogSlug
          )
        }
      />
    )
  }

  if (mode === 'detail' && detail && state.detailPresentation) {
    return (
      <SkillsInstalledDetailView
        detail={detail}
        catalogSearchEnabled={catalogSearchEnabled}
        localCatalogDetail={state.localCatalogDetail}
        localCatalogAudit={state.localCatalogAudit}
        localCatalogLoading={state.localCatalogLoading}
        detailInstallCommand={state.detailInstallCommand}
        detailGithubUrl={state.detailPresentation.detailGithubUrl}
        detailAuthorUrl={state.detailPresentation.detailAuthorUrl}
        detailIconSource={state.detailPresentation.detailIconSource}
        detailIconInvert={state.detailPresentation.detailIconInvert}
        detailVersionLabel={state.detailPresentation.detailVersionLabel}
        detailUpdatedLabel={state.detailPresentation.detailUpdatedLabel}
        copiedInstall={state.copiedInstall}
        pendingEnabled={state.pendingEnabled}
        pendingRemove={state.pendingRemove}
        batchBusy={state.batchBusy}
        removeTarget={state.removeTarget}
        onBack={onBack}
        onCopyInstall={state.handleCopyInstall}
        onRemove={state.removeSkill}
        onRemoveDialogOpenChange={state.handleRemoveDialogOpenChange}
        onConfirmRemove={() => void state.confirmRemoveSkill()}
        onToggleEnabled={(name, enabled) => void state.setSkillEnabled(name, enabled)}
      />
    )
  }

  if (mode === 'detail') {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10">
          <SkillsBreadcrumb onBack={onBack} />
          <DetailPageSkeleton bare />
        </div>
      </ScrollArea>
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
      catalogError={state.catalogError}
      catalogResults={state.catalogResults}
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
