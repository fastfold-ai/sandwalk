import type {
  AgentCatalogSkill,
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentSkill,
  AgentSkillBatchAction,
  AgentSkillBatchResult,
  AgentSkillDetail,
  AgentSkillSource
} from '@sandwalk/agent-ui-core'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react'

import {
  DetailPageSkeleton,
} from '@/components/agents/PageSkeletons'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  catalogCoordsFromInstalledSkill,
  catalogSkillInstallCommand,
  catalogSkillInstallTarget,
  formatSkillInstallError,
  skillInstallSource,
  type SkillsViewMode
} from '@/lib/skills-catalog'

import { SkillsCatalogDetailView } from './skills-view/skills-view-catalog-detail'
import {
  SkillsImportFileView,
  SkillsImportGithubView,
  SkillsTrustedSourcesView
} from './skills-view/skills-view-import-views'
import {
  resolveInstalledDetailPresentation,
  SkillsInstalledDetailView
} from './skills-view/skills-view-installed-detail'
import {
  SkillsFeaturedOverview,
  SkillsMainListView
} from './skills-view/skills-view-list'
import { SkillsBreadcrumb } from './skills-view/skills-view-shared'
import {
  buildInstalledSkillIndex,
  computeSkillsListData,
  isCatalogSkillInstalled
} from './skills-view/skills-view-utils'

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
  /** Overview: only Featured skill cards (same as Skills page). */
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
  ) => Promise<AgentCatalogSkillDetail>
  onGetCatalogAudit: (
    source: string,
    skill: string,
    signal?: AbortSignal
  ) => Promise<AgentCatalogSkillAudit>
  onBulkAction: (
    action: AgentSkillBatchAction,
    names: string[]
  ) => Promise<AgentSkillBatchResult>
  onSetEnabled: (name: string, enabled: boolean) => Promise<void>
  onRemove: (name: string) => Promise<void>
  embedded?: boolean
}) {
  const [query, setQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [authorFilter, setAuthorFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all')
  const [pendingEnabled, setPendingEnabled] = useState<Record<string, boolean>>(
    {}
  )
  const [pendingRemove, setPendingRemove] = useState<Record<string, boolean>>({})
  const [removeTarget, setRemoveTarget] = useState<
    | { type: 'single'; name: string }
    | { type: 'filtered'; count: number }
    | null
  >(null)
  const [batchBusy, setBatchBusy] = useState(false)
  const [batchToast, setBatchToast] = useState<{
    message: string
    tone: 'success' | 'warning'
  } | null>(null)
  const [githubSource, setGithubSource] = useState('fastfold-ai/skills@skills/fold')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const uploadInputRef = useRef<HTMLInputElement | null>(null)
  const [installing, setInstalling] = useState(false)
  const [trustedSources, setTrustedSources] = useState<AgentSkillSource[]>([])
  const [trustedSelected, setTrustedSelected] = useState<Record<string, boolean>>({})
  const [trustedLoading, setTrustedLoading] = useState(false)
  const [catalogResults, setCatalogResults] = useState<AgentCatalogSkill[]>([])
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [catalogSearchMode, setCatalogSearchMode] = useState(
    openCatalogSearchInitially && catalogSearchEnabled
  )
  const [catalogInstallingId, setCatalogInstallingId] = useState<string | null>(
    null
  )
  const [catalogDetail, setCatalogDetail] = useState<AgentCatalogSkillDetail | null>(
    null
  )
  const [catalogAudit, setCatalogAudit] = useState<AgentCatalogSkillAudit | null>(
    null
  )
  const [catalogDetailLoading, setCatalogDetailLoading] = useState(false)
  const [catalogDetailError, setCatalogDetailError] = useState<string | null>(null)
  const [copiedCatalogInstall, setCopiedCatalogInstall] = useState(false)
  const [catalogInstallError, setCatalogInstallError] = useState<string | null>(
    null
  )
  const [localCatalogDetail, setLocalCatalogDetail] =
    useState<AgentCatalogSkillDetail | null>(null)
  const [localCatalogAudit, setLocalCatalogAudit] =
    useState<AgentCatalogSkillAudit | null>(null)
  const [localCatalogLoading, setLocalCatalogLoading] = useState(false)
  const [copiedInstall, setCopiedInstall] = useState(false)

  useEffect(() => {
    if (mode !== 'catalog_detail' || !catalogSkillRoute) {
      setCatalogDetail(null)
      setCatalogAudit(null)
      setCatalogDetailError(null)
      setCatalogInstallError(null)
      setCatalogDetailLoading(false)
      return
    }
    const controller = new AbortController()
    setCatalogDetailLoading(true)
    setCatalogDetailError(null)
    setCatalogInstallError(null)
    setCatalogDetail(null)
    setCatalogAudit(null)
    void onGetCatalogDetail(
      catalogSkillRoute.source,
      catalogSkillRoute.skill,
      controller.signal
    )
      .then(setCatalogDetail)
      .catch(error => {
        if (!controller.signal.aborted) {
          setCatalogDetailError(
            error instanceof Error
              ? error.message
              : 'Unable to load catalog skill details.'
          )
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setCatalogDetailLoading(false)
      })
    void onGetCatalogAudit(
      catalogSkillRoute.source,
      catalogSkillRoute.skill,
      controller.signal
    )
      .then(setCatalogAudit)
      .catch(() => {
        if (!controller.signal.aborted) {
          setCatalogAudit({
            id: catalogSkillRoute.id,
            source: catalogSkillRoute.source,
            slug: catalogSkillRoute.skill,
            audits: []
          })
        }
      })
    return () => controller.abort()
  }, [catalogSkillRoute, mode, onGetCatalogAudit, onGetCatalogDetail])

  useEffect(() => {
    if (mode !== 'detail' || !detail || !catalogSearchEnabled) {
      setLocalCatalogDetail(null)
      setLocalCatalogAudit(null)
      setLocalCatalogLoading(false)
      return
    }
    const coords = catalogCoordsFromInstalledSkill(detail)
    if (!coords) {
      setLocalCatalogDetail(null)
      setLocalCatalogAudit(null)
      setLocalCatalogLoading(false)
      return
    }
    const controller = new AbortController()
    setLocalCatalogLoading(true)
    setLocalCatalogDetail(null)
    setLocalCatalogAudit(null)
    const detailPromise = onGetCatalogDetail(
      coords.source,
      coords.skill,
      controller.signal
    )
      .then(result => {
        if (!controller.signal.aborted) setLocalCatalogDetail(result)
      })
      .catch(() => {
        if (!controller.signal.aborted) setLocalCatalogDetail(null)
      })
    const auditPromise = onGetCatalogAudit(
      coords.source,
      coords.skill,
      controller.signal
    )
      .then(result => {
        if (!controller.signal.aborted) setLocalCatalogAudit(result)
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setLocalCatalogAudit({
            id: `${coords.source}/${coords.skill}`,
            source: coords.source,
            slug: coords.skill,
            audits: []
          })
        }
      })
    void Promise.allSettled([detailPromise, auditPromise]).then(() => {
      if (!controller.signal.aborted) setLocalCatalogLoading(false)
    })
    return () => controller.abort()
  }, [
    catalogSearchEnabled,
    detail,
    mode,
    onGetCatalogAudit,
    onGetCatalogDetail
  ])

  useEffect(() => {
    if (!copiedCatalogInstall) return
    const timer = window.setTimeout(() => setCopiedCatalogInstall(false), 2000)
    return () => window.clearTimeout(timer)
  }, [copiedCatalogInstall])

  useEffect(() => {
    if (!openCatalogSearchInitially) return
    if (!catalogSearchEnabled) {
      onBack()
      return
    }
    setCatalogSearchMode(true)
    onBack()
  }, [catalogSearchEnabled, onBack, openCatalogSearchInitially])

  useEffect(() => {
    if (catalogSearchEnabled) return
    setCatalogSearchMode(false)
  }, [catalogSearchEnabled])

  useEffect(() => {
    if (mode !== 'import_file') return
    const timer = window.setTimeout(() => {
      if (uploadInputRef.current) {
        uploadInputRef.current.value = ''
        uploadInputRef.current.click()
      }
    }, 0)
    return () => window.clearTimeout(timer)
  }, [mode])

  useEffect(() => {
    if (mode !== 'trusted_sources') return
    const controller = new AbortController()
    setTrustedLoading(true)
    void onLoadSuggestedSources(controller.signal)
      .then(items => {
        setTrustedSources(items)
        setTrustedSelected(current => {
          const next = { ...current }
          for (const item of items) {
            if (next[item.source] === undefined) next[item.source] = false
          }
          return next
        })
      })
      .finally(() => {
        if (!controller.signal.aborted) setTrustedLoading(false)
      })
    return () => controller.abort()
  }, [mode, onLoadSuggestedSources])

  useEffect(() => {
    if (!catalogSearchMode) {
      setCatalogResults([])
      setCatalogError(null)
      setCatalogLoading(false)
      return
    }
    const text = query.trim()
    if (text.length < 2) {
      setCatalogResults([])
      setCatalogError(null)
      setCatalogLoading(false)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setCatalogLoading(true)
      setCatalogError(null)
      void onSearchCatalog(text, controller.signal)
        .then(items => {
          if (!controller.signal.aborted) setCatalogResults(items)
        })
        .catch(error => {
          if (controller.signal.aborted) return
          setCatalogResults([])
          setCatalogError(
            error instanceof Error ? error.message : 'Unable to search skills.sh.'
          )
        })
        .finally(() => {
          if (!controller.signal.aborted) setCatalogLoading(false)
        })
    }, 220)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [catalogSearchMode, onSearchCatalog, query])

  useEffect(() => {
    if (!batchToast) return
    const timer = window.setTimeout(() => setBatchToast(null), 2800)
    return () => window.clearTimeout(timer)
  }, [batchToast])

  useEffect(() => {
    setCopiedInstall(false)
  }, [detail?.name])

  const listData = useMemo(
    () =>
      computeSkillsListData(skills, {
        query,
        categoryFilter,
        authorFilter,
        statusFilter
      }),
    [skills, query, categoryFilter, authorFilter, statusFilter]
  )

  useEffect(() => {
    if (
      categoryFilter !== 'all' &&
      categoryFilter !== 'featured' &&
      !listData.categories.includes(categoryFilter)
    ) {
      setCategoryFilter('all')
    }
  }, [categoryFilter, listData.categories])

  useEffect(() => {
    if (authorFilter !== 'all' && !listData.authors.includes(authorFilter)) {
      setAuthorFilter('all')
    }
  }, [authorFilter, listData.authors])

  const installedSkillIndex = useMemo(
    () => buildInstalledSkillIndex(skills),
    [skills]
  )

  const checkCatalogSkillInstalled = useCallback(
    (skill: AgentCatalogSkill) =>
      isCatalogSkillInstalled(skill, installedSkillIndex),
    [installedSkillIndex]
  )

  const enableCatalogSearchMode = () => {
    if (!catalogSearchEnabled) {
      onOpenCatalogSetup()
      return
    }
    setCatalogError(null)
    setCatalogSearchMode(true)
  }

  const submitGithubInstall = async () => {
    if (installing) return
    setInstalling(true)
    try {
      const source = githubSource.trim()
      if (!source) return
      await onInstall(source)
      onBack()
    } finally {
      setInstalling(false)
    }
  }

  const submitFileInstall = async () => {
    if (installing || !uploadFile) return
    setInstalling(true)
    try {
      await onUpload(uploadFile)
      onBack()
    } finally {
      setInstalling(false)
    }
  }

  const selectedTrustedSources = trustedSources
    .map(item => item.source)
    .filter(source => Boolean(trustedSelected[source]))

  const submitTrustedInstall = async () => {
    if (installing || selectedTrustedSources.length === 0) return
    setInstalling(true)
    try {
      for (const source of selectedTrustedSources) {
        await onInstall(source)
      }
      onBack()
    } finally {
      setInstalling(false)
    }
  }

  const submitCatalogInstallSource = async (
    source: string,
    installingId = 'catalog-detail',
    preferredSkillName?: string
  ) => {
    if (installing || batchBusy) return
    const installSource = String(source || '').trim()
    if (!installSource) {
      setCatalogInstallError('No install source available for this catalog skill.')
      return
    }
    setCatalogInstallingId(installingId)
    setInstalling(true)
    setCatalogInstallError(null)
    try {
      const installed = (await onInstall(installSource)) || []
      const preferred = String(preferredSkillName || '').trim()
      const preferredKey = preferred.toLowerCase().replace(/_/g, '-')
      const match =
        installed.find(
          name => name.toLowerCase().replace(/_/g, '-') === preferredKey
        ) ||
        installed[0] ||
        preferred
      if (match) onOpen(match)
    } catch (error) {
      setCatalogInstallError(formatSkillInstallError(error))
    } finally {
      setInstalling(false)
      setCatalogInstallingId(null)
    }
  }

  const detailInstallCommand = detail
    ? `sandwalk skills add ${skillInstallSource(detail.name, detail.source)} --skill ${detail.name}`
    : ''

  const detailPresentation = detail
    ? resolveInstalledDetailPresentation(detail)
    : null

  const handleCopyInstall = useCallback(() => {
    if (!detailInstallCommand) return
    void navigator.clipboard.writeText(detailInstallCommand).then(() => {
      setCopiedInstall(true)
      window.setTimeout(() => setCopiedInstall(false), 2000)
    })
  }, [detailInstallCommand])

  const setSkillEnabled = async (name: string, enabled: boolean) => {
    setPendingEnabled(current => ({ ...current, [name]: true }))
    try {
      await onSetEnabled(name, enabled)
    } finally {
      setPendingEnabled(current => ({ ...current, [name]: false }))
    }
  }

  const removeSkill = (name: string) => {
    if (batchBusy || pendingRemove[name]) return
    setRemoveTarget({ type: 'single', name })
  }

  const removeFiltered = () => {
    if (listData.filteredSkillNames.length === 0 || batchBusy) return
    setRemoveTarget({
      type: 'filtered',
      count: listData.filteredSkillNames.length
    })
  }

  const confirmRemoveSkill = async () => {
    const target = removeTarget
    if (!target) return
    setRemoveTarget(null)
    if (target.type === 'single') {
      const name = target.name
      setPendingRemove(current => ({ ...current, [name]: true }))
      try {
        await onRemove(name)
        if (mode === 'detail' && detail?.name === name) {
          onBack()
        }
      } finally {
        setPendingRemove(current => ({ ...current, [name]: false }))
      }
      return
    }
    if (listData.filteredSkillNames.length === 0 || batchBusy) return
    setBatchBusy(true)
    try {
      const result = await onBulkAction('remove', listData.filteredSkillNames)
      setBatchToast({
        message:
          result.failed.length > 0
            ? `Removed ${result.succeeded.length}/${result.requested} skills (${result.failed.length} failed).`
            : `Removed ${result.succeeded.length}/${result.requested} skills.`,
        tone: result.failed.length > 0 ? 'warning' : 'success'
      })
      if (mode === 'detail' && detail && result.succeeded.includes(detail.name)) {
        onBack()
      }
    } finally {
      setBatchBusy(false)
    }
  }

  const setFilteredEnabled = async (enabled: boolean) => {
    if (listData.filteredSkillNames.length === 0 || batchBusy) return
    setBatchBusy(true)
    try {
      const result = await onBulkAction(
        enabled ? 'enable' : 'disable',
        listData.filteredSkillNames
      )
      const actionLabel = enabled ? 'Enabled' : 'Disabled'
      setBatchToast({
        message:
          result.failed.length > 0
            ? `${actionLabel} ${result.succeeded.length}/${result.requested} skills (${result.failed.length} failed).`
            : `${actionLabel} ${result.succeeded.length}/${result.requested} skills.`,
        tone: result.failed.length > 0 ? 'warning' : 'success'
      })
    } finally {
      setBatchBusy(false)
    }
  }

  const showCatalogEmptyState =
    catalogSearchMode &&
    !catalogLoading &&
    !catalogError &&
    query.trim().length >= 2 &&
    catalogResults.length === 0

  const handleRemoveDialogOpenChange = (open: boolean) => {
    if (!open) setRemoveTarget(null)
  }

  if (mode === 'import_github') {
    return (
      <SkillsImportGithubView
        githubSource={githubSource}
        onGithubSourceChange={setGithubSource}
        installing={installing}
        onBack={onBack}
        onSubmit={() => void submitGithubInstall()}
      />
    )
  }

  if (mode === 'import_file') {
    return (
      <SkillsImportFileView
        uploadFile={uploadFile}
        uploadInputRef={uploadInputRef}
        onUploadFileChange={setUploadFile}
        installing={installing}
        onBack={onBack}
        onSubmit={() => void submitFileInstall()}
      />
    )
  }

  if (mode === 'trusted_sources') {
    return (
      <SkillsTrustedSourcesView
        trustedSources={trustedSources}
        trustedSelected={trustedSelected}
        onTrustedSelectedChange={setTrustedSelected}
        trustedLoading={trustedLoading}
        selectedTrustedSources={selectedTrustedSources}
        installing={installing}
        onBack={onBack}
        onSubmit={() => void submitTrustedInstall()}
      />
    )
  }

  if (mode === 'catalog_detail') {
    const catalogSource = String(
      catalogDetail?.source || catalogSkillRoute?.source || ''
    ).trim()
    const catalogSlug = String(
      catalogDetail?.slug || catalogSkillRoute?.skill || ''
    ).trim()
    const catalogFiles = catalogDetail?.files || []
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
        catalogDetail={catalogDetail}
        catalogAudit={catalogAudit}
        catalogDetailLoading={catalogDetailLoading}
        catalogDetailError={catalogDetailError}
        catalogInstallingId={catalogInstallingId}
        installing={installing}
        catalogInstallError={catalogInstallError}
        copiedCatalogInstall={copiedCatalogInstall}
        isInstalled={checkCatalogSkillInstalled}
        onBack={onBack}
        onCopyInstall={() => {
          if (!catalogInstallCommand) return
          void navigator.clipboard.writeText(catalogInstallCommand).then(() => {
            setCopiedCatalogInstall(true)
          })
        }}
        onInstall={() =>
          void submitCatalogInstallSource(
            catalogInstallTarget,
            String(catalogDetail?.id || catalogSkillRoute?.id || '').trim() ||
              'catalog-detail',
            catalogSlug
          )
        }
      />
    )
  }

  if (mode === 'detail' && detail && detailPresentation) {
    return (
      <SkillsInstalledDetailView
        detail={detail}
        catalogSearchEnabled={catalogSearchEnabled}
        localCatalogDetail={localCatalogDetail}
        localCatalogAudit={localCatalogAudit}
        localCatalogLoading={localCatalogLoading}
        detailInstallCommand={detailInstallCommand}
        detailGithubUrl={detailPresentation.detailGithubUrl}
        detailAuthorUrl={detailPresentation.detailAuthorUrl}
        detailIconSource={detailPresentation.detailIconSource}
        detailIconInvert={detailPresentation.detailIconInvert}
        detailVersionLabel={detailPresentation.detailVersionLabel}
        detailUpdatedLabel={detailPresentation.detailUpdatedLabel}
        copiedInstall={copiedInstall}
        pendingEnabled={pendingEnabled}
        pendingRemove={pendingRemove}
        batchBusy={batchBusy}
        removeTarget={removeTarget}
        onBack={onBack}
        onCopyInstall={handleCopyInstall}
        onRemove={removeSkill}
        onRemoveDialogOpenChange={handleRemoveDialogOpenChange}
        onConfirmRemove={() => void confirmRemoveSkill()}
        onToggleEnabled={(name, enabled) => void setSkillEnabled(name, enabled)}
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
        pendingEnabled={pendingEnabled}
        pendingRemove={pendingRemove}
        batchBusy={batchBusy}
        removeTarget={removeTarget}
        onShowAll={onShowAll}
        onOpen={onOpen}
        onToggleEnabled={(name, enabled) => void setSkillEnabled(name, enabled)}
        onRemove={removeSkill}
        onRemoveDialogOpenChange={handleRemoveDialogOpenChange}
        onConfirmRemove={() => void confirmRemoveSkill()}
      />
    )
  }

  return (
    <SkillsMainListView
      skills={skills}
      loading={loading}
      embedded={embedded}
      query={query}
      categoryFilter={categoryFilter}
      authorFilter={authorFilter}
      statusFilter={statusFilter}
      categories={listData.categories}
      authors={listData.authors}
      categoryCounts={listData.categoryCounts}
      authorCounts={listData.authorCounts}
      featuredCount={listData.featuredCount}
      enabledCount={listData.enabledCount}
      disabledCount={listData.disabledCount}
      featuredVisible={listData.featuredVisible}
      nonFeaturedVisible={listData.nonFeaturedVisible}
      visible={listData.visible}
      disableEligibleCount={listData.disableEligibleCount}
      enableEligibleCount={listData.enableEligibleCount}
      removeEligibleCount={listData.removeEligibleCount}
      catalogSearchMode={catalogSearchMode}
      catalogSearchEnabled={catalogSearchEnabled}
      catalogLoading={catalogLoading}
      catalogError={catalogError}
      catalogResults={catalogResults}
      showCatalogEmptyState={showCatalogEmptyState}
      batchBusy={batchBusy}
      batchToast={batchToast}
      pendingEnabled={pendingEnabled}
      pendingRemove={pendingRemove}
      removeTarget={removeTarget}
      isCatalogSkillInstalled={checkCatalogSkillInstalled}
      onQueryChange={setQuery}
      onCategoryFilterChange={setCategoryFilter}
      onAuthorFilterChange={setAuthorFilter}
      onStatusFilterChange={setStatusFilter}
      onCatalogSearchModeChange={enabled => {
        if (!enabled) {
          setCatalogSearchMode(false)
          setCatalogResults([])
          setCatalogError(null)
        }
      }}
      onEnableCatalogSearchMode={enableCatalogSearchMode}
      onOpenImportGithub={onOpenImportGithub}
      onOpenImportFile={onOpenImportFile}
      onOpenTrustedSources={onOpenTrustedSources}
      onOpen={onOpen}
      onOpenCatalogDetail={onOpenCatalogDetail}
      onToggleEnabled={(name, enabled) => void setSkillEnabled(name, enabled)}
      onRemove={removeSkill}
      onSetFilteredEnabled={enabled => void setFilteredEnabled(enabled)}
      onRemoveFiltered={() => void removeFiltered()}
      onRemoveDialogOpenChange={handleRemoveDialogOpenChange}
      onConfirmRemove={() => void confirmRemoveSkill()}
    />
  )
}
