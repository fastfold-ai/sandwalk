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
  ArrowLeft,
  ArrowRight,
  Box,
  CalendarDays,
  Check,
  ChevronDown,
  Copy,
  GitBranch,
  Loader2,
  MoreHorizontal,
  Plus,
  Search,
  Tag,
  Trash2,
  Upload,
  UserRound
} from 'lucide-react'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react'

import { MarkdownContent } from '@/components/agents/MarkdownContent'
import {
  CardGridSkeleton,
  DetailPageSkeleton,
  ListRowsSkeleton
} from '@/components/agents/PageSkeletons'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import {
  featuredSkillIcon,
  isFeaturedSkill,
  skillIcon,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import {
  compareSkillsBySearchRank,
  skillMatchesSearch
} from '@/lib/skill-search'
import {
  auditStatusBadgeClass,
  catalogCoordsFromInstalledSkill,
  catalogSkillInstallCommand,
  catalogSkillInstallSource,
  catalogSkillInstallTarget,
  categorizeSkill,
  displaySkillVersion,
  formatSkillInstallError,
  formatSkillUpdatedLabel,
  frontmatterValue,
  normalizeSkillMatchKey,
  skillAuthorLabel,
  skillAuthorUrl,
  skillGithubUrl,
  skillInstallSource,
  skillMetaText,
  skillsShSkillUrl,
  type SkillsViewMode,
  splitSkillSourceSpec,
  stripFrontmatter,
  suggestionSourceIcon,
  suggestionSourceLabel
} from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

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
  onRemove
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
  const openCatalogDetailFromResult = (skill: AgentCatalogSkill) => {
    onOpenCatalogDetail(skill)
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
  const categories = Array.from(
    new Set(skills.map(skill => categorizeSkill(skill)))
  ).sort()
  const authors = Array.from(
    new Set(skills.map(skill => skillAuthorLabel(skill)))
  ).sort((a, b) => {
    if (a === 'Unknown') return 1
    if (b === 'Unknown') return -1
    return a.localeCompare(b)
  })
  useEffect(() => {
    if (
      categoryFilter !== 'all' &&
      categoryFilter !== 'featured' &&
      !categories.includes(categoryFilter)
    ) {
      setCategoryFilter('all')
    }
  }, [categories, categoryFilter])
  useEffect(() => {
    if (authorFilter !== 'all' && !authors.includes(authorFilter)) {
      setAuthorFilter('all')
    }
  }, [authors, authorFilter])
  const categoryCounts = skills.reduce<Record<string, number>>((result, skill) => {
    const category = categorizeSkill(skill)
    result[category] = (result[category] || 0) + 1
    return result
  }, {})
  const authorCounts = skills.reduce<Record<string, number>>((result, skill) => {
    const author = skillAuthorLabel(skill)
    result[author] = (result[author] || 0) + 1
    return result
  }, {})
  const featuredCount = skills.filter(skill => isFeaturedSkill(skill)).length
  const enabledCount = skills.filter(skill => skill.enabled).length
  const disabledCount = skills.length - enabledCount
  const visible = skills.filter(skill => {
    const queryText = query.trim().toLowerCase()
    const category = categorizeSkill(skill)
    const matchesQuery = skillMatchesSearch(skill, queryText)
    const matchesCategory =
      categoryFilter === 'all' ||
      (categoryFilter === 'featured' && isFeaturedSkill(skill)) ||
      category === categoryFilter
    const author = skillAuthorLabel(skill)
    const matchesAuthor = authorFilter === 'all' || author === authorFilter
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'enabled' && skill.enabled) ||
      (statusFilter === 'disabled' && !skill.enabled)
    return matchesQuery && matchesCategory && matchesAuthor && matchesStatus
  })
  const orderedVisible = [...visible].sort((a, b) => {
    const queryText = query.trim().toLowerCase()
    if (queryText) {
      const rankDiff = compareSkillsBySearchRank(a, b, queryText)
      if (rankDiff !== 0) return rankDiff
    }
    if (categoryFilter !== 'featured') {
      const featuredDiff =
        Number(isFeaturedSkill(b)) - Number(isFeaturedSkill(a))
      if (featuredDiff !== 0) return featuredDiff
    }
    return a.name.localeCompare(b.name)
  })
  const featuredVisible = orderedVisible.filter(skill => isFeaturedSkill(skill))
  const nonFeaturedVisible = orderedVisible.filter(skill => !isFeaturedSkill(skill))
  const filteredSkillNames = orderedVisible.map(skill => skill.name)
  const disableEligibleCount = orderedVisible.filter(skill => skill.enabled).length
  const enableEligibleCount = orderedVisible.filter(skill => !skill.enabled).length
  const removeEligibleCount = filteredSkillNames.length
  const [copiedInstall, setCopiedInstall] = useState(false)
  const detailInstallCommand = detail
    ? `sandwalk skills add ${skillInstallSource(detail.name, detail.source)} --skill ${detail.name}`
    : ''
  const detailGithubUrl = detail
    ? skillGithubUrl(detail.name, detail.source)
    : null
  const detailAuthorUrl = detail
    ? skillAuthorUrl(detail.source)
    : null
  const detailIconSource = detail
    ? isFeaturedSkill(detail)
      ? featuredSkillIcon(detail)
      : skillIcon(detail)
    : null
  const detailIconInvert = detail ? skillIconInvertInDark(detail) : false
  const detailVersionLabel = displaySkillVersion(detail?.version)
  const detailUpdatedLabel = formatSkillUpdatedLabel(detail?.updatedAt)
  useEffect(() => {
    setCopiedInstall(false)
  }, [detail?.name])
  const handleCopyInstall = useCallback(() => {
    if (!detailInstallCommand) return
    void navigator.clipboard.writeText(detailInstallCommand).then(() => {
      setCopiedInstall(true)
      window.setTimeout(() => setCopiedInstall(false), 2000)
    })
  }, [detailInstallCommand])

  const renderSkillsShMetrics = (
    source: string,
    installs: number,
    audits: AgentCatalogSkillAudit['audits']
  ) => {
    const installLabel = new Intl.NumberFormat('en-US', {
      notation: 'compact',
      maximumFractionDigits: 1
    }).format(installs)
    return (
      <aside className="space-y-4 lg:sticky lg:top-4">
        <div className="rounded-lg p-3">
          <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
            Installs
          </p>
          <p className="mt-1 text-3xl font-semibold">{installLabel}</p>
        </div>
        <div className="rounded-lg p-3">
          <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
            Repository
          </p>
          <p className="mt-1 break-all text-sm">{source || 'Unknown'}</p>
        </div>
        <div className="rounded-lg p-3">
          <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
            Security Audits
          </p>
          <div className="mt-2 space-y-2">
            {audits.length === 0 ? (
              <p className="text-muted-foreground text-xs">No audits available.</p>
            ) : (
              audits.map(audit => (
                <div
                  key={`${audit.provider}-${audit.slug}`}
                  className="flex items-center justify-between gap-2"
                >
                  <span className="truncate text-xs">{audit.provider}</span>
                  <span
                    className={cn(
                      'rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase',
                      auditStatusBadgeClass(audit.status)
                    )}
                  >
                    {audit.status || 'unknown'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </aside>
    )
  }

  const renderSkillsShMetricsLoading = () => (
    <aside className="space-y-4 lg:sticky lg:top-4">
      <div className="rounded-lg border border-border/60 p-4">
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 shrink-0 animate-spin" />
          <span>Fetching skills.sh details…</span>
        </div>
        <div className="mt-4 space-y-3">
          <div className="bg-muted/60 h-3 w-16 animate-pulse rounded" />
          <div className="bg-muted/50 h-8 w-12 animate-pulse rounded" />
          <div className="bg-muted/60 mt-4 h-3 w-20 animate-pulse rounded" />
          <div className="bg-muted/50 h-4 w-full animate-pulse rounded" />
          <div className="bg-muted/60 mt-4 h-3 w-24 animate-pulse rounded" />
          <div className="space-y-2">
            <div className="bg-muted/50 h-4 w-full animate-pulse rounded" />
            <div className="bg-muted/50 h-4 w-full animate-pulse rounded" />
            <div className="bg-muted/50 h-4 w-5/6 animate-pulse rounded" />
          </div>
        </div>
      </div>
    </aside>
  )

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
    if (filteredSkillNames.length === 0 || batchBusy) return
    setRemoveTarget({ type: 'filtered', count: filteredSkillNames.length })
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
    if (filteredSkillNames.length === 0 || batchBusy) return
    setBatchBusy(true)
    try {
      const result = await onBulkAction('remove', filteredSkillNames)
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
    if (filteredSkillNames.length === 0 || batchBusy) return
    setBatchBusy(true)
    try {
      const result = await onBulkAction(
        enabled ? 'enable' : 'disable',
        filteredSkillNames
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
  useEffect(() => {
    if (!batchToast) return
    const timer = window.setTimeout(() => setBatchToast(null), 2800)
    return () => window.clearTimeout(timer)
  }, [batchToast])
  const showCatalogEmptyState =
    catalogSearchMode &&
    !catalogLoading &&
    !catalogError &&
    query.trim().length >= 2 &&
    catalogResults.length === 0
  const catalogInstallLabelFor = (installs: number) =>
    new Intl.NumberFormat('en-US', {
      notation: 'compact',
      maximumFractionDigits: 1
    }).format(installs)
  const installedSkillIndex = useMemo(() => {
    const index = new Map<string, Set<string>>()
    for (const skill of skills) {
      const nameKey = normalizeSkillMatchKey(skill.name)
      if (!nameKey) continue
      const sourceSpec = splitSkillSourceSpec(skill.source)
      const ownerRepo = sourceSpec?.ownerRepo.toLowerCase() || ''
      const repos = index.get(nameKey) || new Set<string>()
      repos.add(ownerRepo)
      index.set(nameKey, repos)
    }
    return index
  }, [skills])
  const isCatalogSkillInstalled = useCallback(
    (skill: AgentCatalogSkill) => {
      const candidateKeys = [
        normalizeSkillMatchKey(skill.slug),
        normalizeSkillMatchKey(skill.name)
      ].filter(Boolean)
      if (candidateKeys.length === 0) return false
      const catalogSpec = splitSkillSourceSpec(catalogSkillInstallSource(skill))
      const catalogOwnerRepo = catalogSpec?.ownerRepo.toLowerCase() || ''
      return candidateKeys.some(key => {
        const installedRepos = installedSkillIndex.get(key)
        if (!installedRepos || installedRepos.size === 0) return false
        if (!catalogOwnerRepo) return true
        return (
          installedRepos.has(catalogOwnerRepo) ||
          installedRepos.has('')
        )
      })
    },
    [installedSkillIndex]
  )

  const renderEnabledToggle = (skill: AgentSkill) => {
    const pending = Boolean(pendingEnabled[skill.name])
    return (
      <button
        type="button"
        role="switch"
        aria-checked={skill.enabled}
        aria-label={`${skill.enabled ? 'Disable' : 'Enable'} ${skill.name}`}
        disabled={pending}
        className={cn(
          'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
          skill.enabled
            ? 'bg-black/75 dark:bg-zinc-300/50'
            : 'bg-zinc-200 dark:bg-zinc-700',
          pending && 'cursor-not-allowed opacity-60'
        )}
        onClick={event => {
          event.preventDefault()
          event.stopPropagation()
          void setSkillEnabled(skill.name, !skill.enabled)
        }}
      >
        <span
          className={cn(
            'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
            skill.enabled ? 'translate-x-4' : 'translate-x-0.5'
          )}
        />
      </button>
    )
  }
  const renderRemoveButton = (skill: AgentSkill) => {
    const pending = Boolean(pendingRemove[skill.name]) || batchBusy
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-muted-foreground/70 hover:text-muted-foreground h-6 w-6 p-0"
            disabled={pending}
            onClick={event => {
              event.preventDefault()
              event.stopPropagation()
            }}
          >
            <MoreHorizontal className="size-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            className="text-red-600 focus:text-red-700"
            onClick={event => {
              event.preventDefault()
              event.stopPropagation()
              void removeSkill(skill.name)
            }}
          >
            <Trash2 className="size-3.5" />
            Remove
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }
  const renderSkillsBreadcrumb = () => (
    <div className="flex items-center gap-2 text-sm">
      <button
        type="button"
        onClick={onBack}
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </button>
      <span className="text-muted-foreground/40">/</span>
      <button
        type="button"
        onClick={onBack}
        className="text-muted-foreground hover:text-foreground transition-colors"
      >
        Skills
      </button>
    </div>
  )

  const renderRemoveDialog = () => (
    <AlertDialog
      open={Boolean(removeTarget)}
      onOpenChange={open => {
        if (!open) setRemoveTarget(null)
      }}
    >
      <AlertDialogContent className="max-w-sm">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {removeTarget?.type === 'filtered'
              ? 'Remove skills?'
              : 'Remove skill?'}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {removeTarget?.type === 'filtered'
              ? `Remove ${removeTarget.count} skills in the current filter? This cannot be undone.`
              : `Remove “${removeTarget?.name || 'this skill'}”? This uninstalls it from this machine and cannot be undone.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={() => void confirmRemoveSkill()}
          >
            Remove
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )

  if (mode === 'import_github') {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10">
          {renderSkillsBreadcrumb()}
          <section className="bg-card mt-4 space-y-4 rounded-xl border p-6">
            <div>
              <h2 className="text-lg font-semibold">Import from GitHub</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Use owner/repo, owner/repo@path, or a GitHub URL. This matches how
                `sandwalk skills add` parses sources.
              </p>
            </div>
            <Input
              value={githubSource}
              onChange={event => setGithubSource(event.target.value)}
              placeholder="fastfold-ai/skills@skills/fold"
              autoFocus
              onKeyDown={event => {
                if (event.key === 'Enter' && githubSource.trim() && !installing) {
                  event.preventDefault()
                  void submitGithubInstall()
                }
              }}
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={onBack}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!githubSource.trim() || installing}
                onClick={() => void submitGithubInstall()}
              >
                {installing ? 'Importing…' : 'Import'}
              </Button>
            </div>
          </section>
        </div>
      </ScrollArea>
    )
  }

  if (mode === 'import_file') {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10">
          {renderSkillsBreadcrumb()}
          <section className="bg-card mt-4 space-y-4 rounded-xl border p-6">
            <div>
              <h2 className="text-lg font-semibold">Import from file</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Choose a local .zip, .skill, or SKILL.md file.
              </p>
            </div>
            <Input
              ref={uploadInputRef}
              type="file"
              accept=".zip,.skill,.md"
              onChange={event => {
                const file = event.target.files?.[0] ?? null
                setUploadFile(file)
              }}
            />
            <p className="text-muted-foreground text-xs">
              {uploadFile
                ? `Selected: ${uploadFile.name}`
                : 'Pick a file to upload using your file browser.'}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={onBack}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!uploadFile || installing}
                onClick={() => void submitFileInstall()}
              >
                {installing ? 'Uploading…' : 'Upload'}
              </Button>
            </div>
          </section>
        </div>
      </ScrollArea>
    )
  }

  if (mode === 'trusted_sources') {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-4xl px-6 py-8 md:px-10">
          {renderSkillsBreadcrumb()}
          <section className="bg-card mt-4 space-y-4 rounded-xl border p-6">
            <div>
              <h2 className="text-lg font-semibold">Suggestions</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Suggested community skill collections from FastFold setup.
                Select one or more sources to install.
              </p>
            </div>
            {trustedLoading ? (
              <CardGridSkeleton cards={6} columns={3} />
            ) : trustedSources.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                No suggestions are currently available.
              </p>
            ) : (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {trustedSources.map(item => (
                  <button
                    key={item.source}
                    type="button"
                    className={cn(
                      'bg-background/60 hover:bg-muted/40 flex items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                      trustedSelected[item.source] &&
                        'ring-primary bg-muted/40 ring-1'
                    )}
                    onClick={() =>
                      setTrustedSelected(current => ({
                        ...current,
                        [item.source]: !current[item.source]
                      }))
                    }
                  >
                    {suggestionSourceIcon(item) ? (
                      <img
                        src={suggestionSourceIcon(item) || ''}
                        alt=""
                        className="mt-0.5 size-8 rounded object-contain"
                      />
                    ) : (
                      <span className="bg-muted/30 text-muted-foreground mt-0.5 grid size-8 shrink-0 place-items-center rounded">
                        <GitBranch className="size-4" />
                      </span>
                    )}
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {suggestionSourceLabel(item)}
                      </p>
                      <p className="text-muted-foreground mt-0.5 text-xs">
                        {item.description}
                      </p>
                      <span className="text-muted-foreground mt-1 block truncate text-xs">
                        {item.source}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={onBack}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={selectedTrustedSources.length === 0 || installing}
                onClick={() => void submitTrustedInstall()}
              >
                {installing
                  ? `Installing ${selectedTrustedSources.length}…`
                  : `Install selected (${selectedTrustedSources.length})`}
              </Button>
            </div>
          </section>
        </div>
      </ScrollArea>
    )
  }

  if (mode === 'catalog_detail') {
    const catalogSource = String(
      catalogDetail?.source || catalogSkillRoute?.source || ''
    ).trim()
    const catalogSlug = String(catalogDetail?.slug || catalogSkillRoute?.skill || '').trim()
    const catalogId = String(catalogDetail?.id || catalogSkillRoute?.id || '').trim()
    const catalogFiles = catalogDetail?.files || []
    const catalogSkillMd = (
      catalogFiles.find(file => file.path.toLowerCase() === 'skill.md') ||
      catalogFiles.find(file => file.path.toLowerCase().endsWith('/skill.md'))
    )?.contents
    const catalogSummary =
      (catalogSkillMd
        ? frontmatterValue(catalogSkillMd, 'description')
        : null) ||
      (catalogSkillMd
        ? stripFrontmatter(catalogSkillMd)
            .split('\n')
            .map(line => line.trim())
            .find(line => line && !line.startsWith('#') && !line.startsWith('-'))
        : null) ||
      'No summary available.'
    const catalogInstallCommand =
      catalogSource && catalogSlug
        ? catalogSkillInstallCommand(catalogSource, catalogSlug, catalogFiles)
        : ''
    const catalogInstallTarget =
      catalogSource && catalogSlug
        ? catalogSkillInstallTarget(catalogSource, catalogSlug, catalogFiles)
        : ''
    const catalogInstalls = Number(catalogDetail?.installs || 0)
    const catalogAudits = catalogAudit?.audits || []
    const catalogSkillsShUrl =
      catalogSource
        ? skillsShSkillUrl(
            catalogSource,
            // Prefer the requested skill id (keeps underscores). API `slug`
            // may hyphenate names (md-openmm-calvados vs md_openmm_calvados).
            String(
              catalogSkillRoute?.skill || catalogDetail?.slug || catalogSlug || ''
            )
          )
        : null
    const handleCatalogInstall = async () => {
      if (!catalogInstallTarget) return
      await submitCatalogInstallSource(
        catalogInstallTarget,
        catalogId || 'catalog-detail',
        catalogSlug
      )
    }
    const handleCatalogCopyInstall = () => {
      if (!catalogInstallCommand) return
      void navigator.clipboard.writeText(catalogInstallCommand).then(() => {
        setCopiedCatalogInstall(true)
      })
    }

    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 md:p-6">
          <div className="flex items-center justify-between gap-3">
            {renderSkillsBreadcrumb()}
            {catalogSkillsShUrl ? (
              <a
                href={catalogSkillsShUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border/70 px-3 py-1.5 text-xs hover:bg-muted"
              >
                <img
                  src="/suggestions/skills-sh.png"
                  alt=""
                  className="size-3.5 rounded object-contain dark:invert"
                />
                View in Skills.sh
              </a>
            ) : null}
          </div>
          {catalogDetailLoading ? (
            <div className="space-y-4">
              <div className="text-muted-foreground flex items-center gap-2 text-sm">
                <Loader2 className="size-4 animate-spin" />
                Fetching skills.sh details…
              </div>
              <DetailPageSkeleton bare />
            </div>
          ) : catalogDetailError ? (
            <p className="text-destructive text-sm">{catalogDetailError}</p>
          ) : (
            <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_250px]">
              <section className="space-y-4">
                <div>
                  <p className="text-muted-foreground text-xs">
                    skills / {catalogSource || 'unknown'} / {catalogSlug || 'unknown'}
                  </p>
                  <h1 className="mt-2 text-3xl font-semibold">
                    {catalogSlug || 'Catalog skill'}
                  </h1>
                </div>

                <div className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    Installation
                  </p>
                  <div className="bg-muted/50 overflow-hidden rounded-lg border">
                    <div className="bg-muted/80 flex items-center justify-between border-b px-3 py-1.5">
                      <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                        bash
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 gap-1.5 px-2 text-xs"
                        onClick={handleCatalogCopyInstall}
                      >
                        {copiedCatalogInstall ? (
                          <>
                            <Check className="h-3.5 w-3.5" />
                            Copied!
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" />
                            Copy
                          </>
                        )}
                      </Button>
                    </div>
                    <pre className="text-muted-foreground overflow-x-auto p-3 font-mono text-sm">
                      <code>{catalogInstallCommand || 'No install command available.'}</code>
                    </pre>
                  </div>
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      disabled={!catalogInstallTarget || installing}
                      onClick={() => void handleCatalogInstall()}
                    >
                      {installing && catalogInstallingId === (catalogId || 'catalog-detail')
                        ? 'Installing…'
                        : isCatalogSkillInstalled({
                            id: catalogId,
                            slug: catalogSlug,
                            name: catalogSlug,
                            source: catalogSource,
                            installs: catalogInstalls,
                            sourceType: 'github',
                            installUrl: null,
                            url: null
                          })
                        ? 'Update'
                        : 'Install'}
                    </Button>
                  </div>
                  {catalogInstallError ? (
                    <div
                      role="alert"
                      className="border-destructive/30 bg-destructive/5 text-destructive rounded-lg border px-3 py-2 text-sm leading-relaxed"
                    >
                      {catalogInstallError}
                    </div>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    Summary
                  </p>
                  <div className="bg-card rounded-lg border p-3 text-sm leading-relaxed">
                    {catalogSummary}
                  </div>
                </div>

                {catalogSkillMd ? (
                  <section className="space-y-2">
                    <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                      SKILL.md
                    </p>
                    <MarkdownContent
                      content={stripFrontmatter(catalogSkillMd)}
                      className="max-w-none text-sm [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_code]:break-words [&_table]:block [&_table]:max-w-full [&_table]:overflow-x-auto"
                    />
                  </section>
                ) : null}
              </section>

              {renderSkillsShMetrics(
                catalogSource,
                catalogInstalls,
                catalogAudits
              )}
            </div>
          )}
        </div>
      </ScrollArea>
    )
  }

  if (mode === 'detail' && detail) {
    const localCatalogSource = String(
      localCatalogDetail?.source ||
        catalogCoordsFromInstalledSkill(detail)?.source ||
        ''
    ).trim()
    const localCatalogInstalls = Number(localCatalogDetail?.installs || 0)
    const localCatalogAudits = localCatalogAudit?.audits || []
    const localCatalogCoords = catalogCoordsFromInstalledSkill(detail)
    const showLocalCatalogColumn =
      catalogSearchEnabled &&
      Boolean(localCatalogCoords) &&
      (localCatalogLoading || localCatalogDetail != null)
    const localSkillsShUrl =
      !localCatalogLoading && localCatalogSource
        ? skillsShSkillUrl(localCatalogSource, detail.name)
        : null

    return (
      <>
        <ScrollArea className="flex-1">
          <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 md:p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <button
                  type="button"
                  onClick={onBack}
                  className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </button>
                <span className="text-muted-foreground/40">/</span>
                <button
                  type="button"
                  onClick={onBack}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  Skills
                </button>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs text-red-600 hover:text-red-700"
                  disabled={Boolean(detail && pendingRemove[detail.name]) || batchBusy}
                  onClick={() => removeSkill(detail.name)}
                >
                  <Trash2 className="mr-1 size-3.5" />
                  Remove
                </Button>
              {localCatalogLoading ? (
                <span className="text-muted-foreground inline-flex items-center gap-1.5 rounded-md border border-border/60 px-3 py-1.5 text-xs">
                  <Loader2 className="size-3.5 animate-spin" />
                  Fetching skills.sh…
                </span>
              ) : localSkillsShUrl ? (
                <a
                  href={localSkillsShUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-md border border-border/70 px-3 py-1.5 text-xs hover:bg-muted"
                >
                  <img
                    src="/suggestions/skills-sh.png"
                    alt=""
                    className="size-3.5 rounded object-contain dark:invert"
                  />
                  View in Skills.sh
                </a>
              ) : null}
              {detailGithubUrl ? (
                <a
                  href={detailGithubUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-md border border-border/70 px-3 py-1.5 text-xs hover:bg-muted"
                >
                  <GitBranch className="h-3.5 w-3.5" />
                  View in GitHub
                </a>
              ) : (
                <span className="text-muted-foreground inline-flex items-center gap-1.5 rounded-md border border-border/60 px-3 py-1.5 text-xs">
                  <GitBranch className="h-3.5 w-3.5" />
                  Source not on GitHub
                </span>
              )}
            </div>
          </div>

          <div
            className={cn(
              'grid items-start gap-4',
              showLocalCatalogColumn
                ? 'lg:grid-cols-[240px_minmax(0,1fr)_220px]'
                : 'lg:grid-cols-[240px_minmax(0,1fr)]'
            )}
          >
            <aside className="space-y-3 lg:sticky lg:top-4 lg:border-r lg:border-border/60 lg:pr-4">
              <div className="space-y-2">
                {detailIconSource ? (
                  <img
                    src={detailIconSource}
                    alt=""
                    className={cn(
                      'size-9 rounded object-contain',
                      detailIconInvert && 'dark:invert'
                    )}
                  />
                ) : (
                  <span className="bg-muted/30 text-muted-foreground grid size-9 shrink-0 place-items-center rounded">
                    <Box className="size-5" />
                  </span>
                )}
                <div className="min-w-0 space-y-0.5">
                  <div className="flex items-start justify-between gap-2">
                    <h1 className="break-all text-lg font-semibold">
                      /{detail.name}
                    </h1>
                    <div className="shrink-0 pt-0.5">
                      {renderEnabledToggle(detail)}
                    </div>
                  </div>
                  <p className="text-muted-foreground mb-6 pb-3 text-sm">
                    {detail.description || 'Runtime skill'}
                  </p>
                  <div className="mt-6 space-y-1 border-t border-border/60 pt-5 text-xs">
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <Tag className="h-3.5 w-3.5 shrink-0" />
                      <span className="text-foreground/90 font-medium">
                        Version:
                      </span>
                      <span className="truncate">{detailVersionLabel}</span>
                    </div>
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <CalendarDays className="h-3.5 w-3.5 shrink-0" />
                      <span className="text-foreground/90 font-medium">
                        Last updated:
                      </span>
                      <span className="truncate" title={detailUpdatedLabel}>
                        {detailUpdatedLabel}
                      </span>
                    </div>
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <UserRound className="h-3.5 w-3.5 shrink-0" />
                      <span className="text-foreground/90 font-medium">
                        Author:
                      </span>
                      {detailAuthorUrl ? (
                        <a
                          href={detailAuthorUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="truncate underline-offset-2 hover:underline"
                        >
                          {detail.author || 'fastfold-ai'}
                        </a>
                      ) : (
                        <span className="truncate">{detail.author || 'unknown'}</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </aside>

            <section className="min-w-0 overflow-x-hidden p-1">
              <div className="mb-4 space-y-1.5">
                <p className="text-muted-foreground text-sm font-medium">
                  Install this skill
                </p>
                <div className="bg-muted/50 overflow-hidden rounded-lg border">
                  <div className="bg-muted/80 flex items-center justify-between border-b px-3 py-1.5">
                    <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                      bash
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 gap-1.5 px-2 text-xs"
                      onClick={handleCopyInstall}
                    >
                      {copiedInstall ? (
                        <>
                          <Check className="h-3.5 w-3.5" />
                          Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="h-3.5 w-3.5" />
                          Copy
                        </>
                      )}
                    </Button>
                  </div>
                  <pre className="text-muted-foreground overflow-x-auto p-3 font-mono text-sm">
                    <code>{detailInstallCommand}</code>
                  </pre>
                </div>
              </div>

              <MarkdownContent
                content={stripFrontmatter(detail.content)}
                className="max-w-none text-sm [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_code]:break-words [&_table]:block [&_table]:max-w-full [&_table]:overflow-x-auto"
              />
            </section>

            {localCatalogLoading
              ? renderSkillsShMetricsLoading()
              : localCatalogDetail != null
                ? renderSkillsShMetrics(
                    localCatalogSource,
                    localCatalogInstalls,
                    localCatalogAudits
                  )
                : null}
          </div>
        </div>
      </ScrollArea>
      {renderRemoveDialog()}
      </>
    )
  }
  if (mode === 'detail') {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10">
          {renderSkillsBreadcrumb()}
          <DetailPageSkeleton bare />
        </div>
      </ScrollArea>
    )
  }

  if (featuredOnly) {
    const featuredAll = skills.filter(skill => isFeaturedSkill(skill))
    const featured = featuredAll.slice(0, 2)
    return (
      <>
        <section className="space-y-3">
          <div className="flex items-end justify-between gap-2">
            <div>
              <h3 className="text-base font-semibold tracking-tight">Skills</h3>
              <p className="text-muted-foreground text-xs font-medium">
                Featured ({featuredAll.length})
              </p>
            </div>
            {onShowAll ? (
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs font-medium transition-colors"
                onClick={onShowAll}
              >
                Show all
                <ArrowRight className="size-3.5" />
              </button>
            ) : null}
          </div>
          {loading && featuredAll.length === 0 ? (
            <CardGridSkeleton cards={2} columns={2} />
          ) : featured.length === 0 ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              No featured skills yet.
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {featured.map(skill => {
                const iconSource = featuredSkillIcon(skill)
                const metaText = skillMetaText(skill)
                return (
                  <div
                    key={skill.name}
                    className={cn(
                      'bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors',
                      !skill.enabled && 'opacity-60'
                    )}
                  >
                    <button
                      type="button"
                      className="min-w-0 flex-1 text-left"
                      onClick={() => onOpen(skill.name)}
                    >
                      <div className="flex items-center gap-2">
                        <img
                          src={iconSource}
                          alt=""
                          className={cn(
                            'size-7 rounded object-contain',
                            skillIconInvertInDark(skill) && 'dark:invert'
                          )}
                        />
                        <span className="truncate text-sm font-medium">
                          {skill.name}
                        </span>
                      </div>
                      {metaText ? (
                        <p className="text-muted-foreground mt-0.5 text-xs">
                          {metaText}
                        </p>
                      ) : null}
                      <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                        {skill.description}
                      </p>
                    </button>
                    <div className="flex flex-col items-end gap-1 pt-0.5">
                      {renderEnabledToggle(skill)}
                      {renderRemoveButton(skill)}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>
        {renderRemoveDialog()}
      </>
    )
  }

  return (
    <>
      <ScrollArea className="flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6 xl:flex-row">
          <div className="min-w-0 flex-1">
            <div className="mb-4">
              <h2 className="text-2xl font-semibold">Skills</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Packaged instructions and scripts the agent can load on demand.
                Install from the catalog or GitHub, and toggle which are active.
              </p>
            </div>
            <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 mb-4 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
              <div className="relative min-w-[280px] flex-1 max-w-3xl">
                <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
                <Input
                  value={query}
                  onChange={event => setQuery(event.target.value)}
                  placeholder={
                    catalogSearchMode
                      ? 'Search skills.sh...'
                      : 'Search skills, descriptions...'
                  }
                  className="border-border/70 bg-background/70 h-11 pl-10 pr-[9.5rem]"
                />
                <button
                  type="button"
                  className={cn(
                    'absolute right-1.5 top-1/2 flex h-8 -translate-y-1/2 items-center gap-1.5 rounded-md px-2 text-xs transition-colors',
                    catalogSearchMode
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                    !catalogSearchEnabled && 'opacity-70'
                  )}
                  onClick={() => {
                    if (catalogSearchMode) {
                      setCatalogSearchMode(false)
                      setCatalogResults([])
                      setCatalogError(null)
                      return
                    }
                    enableCatalogSearchMode()
                  }}
                  title={
                    catalogSearchEnabled
                      ? 'Toggle Skills.sh search'
                      : 'Skills.sh needs setup'
                  }
                >
                  <img
                    src="/suggestions/skills-sh.png"
                    alt=""
                    className="size-3.5 rounded object-contain dark:invert"
                  />
                  <span>Skills.sh</span>
                  <span
                    className={cn(
                      'ml-0.5 inline-flex h-4 w-7 items-center rounded-full px-0.5 transition-colors',
                      catalogSearchMode ? 'bg-foreground/80' : 'bg-muted-foreground/30'
                    )}
                    aria-hidden
                  >
                    <span
                      className={cn(
                        'bg-background size-3 rounded-full transition-transform',
                        catalogSearchMode ? 'translate-x-3' : 'translate-x-0'
                      )}
                    />
                  </span>
                </button>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-10">
                    <Plus className="mr-1 size-3.5" />
                    Add skill
                    <ChevronDown className="ml-1 size-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={onOpenImportGithub}>
                    <GitBranch className="size-4" />
                    Import from GitHub
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={onOpenImportFile}>
                    <Upload className="size-4" />
                    Upload from file
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className={cn(
                      !catalogSearchEnabled &&
                        'text-muted-foreground/80 data-[highlighted]:text-muted-foreground/80'
                    )}
                    onClick={enableCatalogSearchMode}
                  >
                    <img
                      src="/suggestions/skills-sh.png"
                      alt=""
                      className={cn(
                        'size-4 rounded object-contain dark:invert',
                        !catalogSearchEnabled && 'opacity-60'
                      )}
                    />
                    <span>Search in Skills.sh</span>
                    {!catalogSearchEnabled ? (
                      <span className="text-muted-foreground/80 text-[11px]">
                        (Needs setup)
                      </span>
                    ) : null}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={onOpenTrustedSources}>
                    <Check className="size-4" />
                    Suggestions
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            {catalogSearchMode ? (
              <div className="space-y-4 pb-4">
                <section className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium">
                    Skills.sh
                    {query.trim().length >= 2
                      ? ` · ${catalogResults.length} result${catalogResults.length === 1 ? '' : 's'}`
                      : ''}
                  </p>
                  {catalogLoading ? (
                    <ListRowsSkeleton rows={5} withToggle={false} />
                  ) : null}
                  {catalogError ? (
                    <p className="text-destructive text-sm">{catalogError}</p>
                  ) : null}
                  {!catalogLoading && !catalogError && query.trim().length < 2 ? (
                    <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
                      Type at least 2 characters to search skills.sh.
                    </div>
                  ) : null}
                  {showCatalogEmptyState ? (
                    <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
                      No skills.sh results match “{query.trim()}”.
                    </div>
                  ) : null}
                  {!catalogLoading && !catalogError && catalogResults.length > 0 ? (
                    <div className="space-y-2">
                      {catalogResults.map(skill => {
                        const isInstalled = isCatalogSkillInstalled(skill)
                        const title = skill.name || skill.slug
                        return (
                          <div
                            key={skill.id}
                            className="bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors"
                          >
                            <button
                              type="button"
                              className="min-w-0 flex-1 text-left"
                              onClick={() => openCatalogDetailFromResult(skill)}
                            >
                              <div className="flex items-center gap-2">
                                <img
                                  src="/suggestions/skills-sh.png"
                                  alt=""
                                  className="size-6 rounded object-contain dark:invert"
                                />
                                <span className="truncate text-sm font-medium">
                                  {title}
                                </span>
                                <span className="text-muted-foreground truncate text-xs">
                                  {skill.source}
                                </span>
                                {skill.installs > 0 ? (
                                  <span className="text-muted-foreground shrink-0 text-xs">
                                    {catalogInstallLabelFor(skill.installs)} installs
                                  </span>
                                ) : null}
                              </div>
                              <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                                {skill.source}
                                {skill.sourceType ? ` · ${skill.sourceType}` : ''}
                              </p>
                            </button>
                            <div className="flex items-center gap-1 pt-0.5">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 text-xs"
                                onClick={() => openCatalogDetailFromResult(skill)}
                              >
                                {isInstalled ? 'Update' : 'View'}
                              </Button>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  ) : null}
                </section>
              </div>
            ) : loading ? (
              <div className="space-y-4 pb-4">
                <section className="space-y-2">
                  <Skeleton className="h-3 w-24" />
                  <CardGridSkeleton cards={6} columns={3} />
                </section>
                <section className="space-y-2">
                  <Skeleton className="h-3 w-16" />
                  <ListRowsSkeleton rows={5} />
                </section>
              </div>
            ) : visible.length === 0 ? (
              <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
                No skills match the current search/filter.
              </div>
            ) : (
              <div className="space-y-4 pb-4">
                {featuredVisible.length > 0 ? (
                  <section className="space-y-2">
                    <p className="text-muted-foreground text-xs font-medium">
                      Featured ({featuredVisible.length})
                    </p>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {featuredVisible.map(skill => {
                        const iconSource = featuredSkillIcon(skill)
                        const metaText = skillMetaText(skill)
                        return (
                          <div
                            key={skill.name}
                            className={cn(
                              'bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors',
                              !skill.enabled && 'opacity-60'
                            )}
                          >
                            <button
                              type="button"
                              className="min-w-0 flex-1 text-left"
                              onClick={() => onOpen(skill.name)}
                            >
                              <div className="flex items-center gap-2">
                                <img
                                  src={iconSource}
                                  alt=""
                                  className={cn(
                                    'size-7 rounded object-contain',
                                    skillIconInvertInDark(skill) && 'dark:invert'
                                  )}
                                />
                                <span className="truncate text-sm font-medium">
                                  {skill.name}
                                </span>
                              </div>
                              {metaText ? (
                                <p className="text-muted-foreground mt-0.5 text-xs">
                                  {metaText}
                                </p>
                              ) : null}
                              <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                                {skill.description}
                              </p>
                            </button>
                            <div className="flex flex-col items-end gap-1 pt-0.5">
                              {renderEnabledToggle(skill)}
                              {renderRemoveButton(skill)}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </section>
                ) : null}
                {categoryFilter !== 'featured' ? (
                  <section className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-muted-foreground text-xs font-medium">
                        All ({nonFeaturedVisible.length})
                      </p>
                      <div className="flex flex-wrap items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground h-7 text-xs"
                          disabled={disableEligibleCount === 0 || batchBusy}
                          onClick={() => void setFilteredEnabled(false)}
                        >
                          Disable ({disableEligibleCount})
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground h-7 text-xs"
                          disabled={enableEligibleCount === 0 || batchBusy}
                          onClick={() => void setFilteredEnabled(true)}
                        >
                          Enable ({enableEligibleCount})
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground h-7 text-xs"
                          disabled={removeEligibleCount === 0 || batchBusy}
                          onClick={() => void removeFiltered()}
                        >
                          Remove ({removeEligibleCount})
                        </Button>
                      </div>
                    </div>
                    <div className="space-y-2">
                      {nonFeaturedVisible.map(skill => {
                        const iconSource = skillIcon(skill)
                        const metaText = skillMetaText(skill)
                        return (
                          <div
                            key={skill.name}
                            className={cn(
                              'bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors',
                              !skill.enabled && 'opacity-60'
                            )}
                          >
                            <button
                              type="button"
                              className="min-w-0 flex-1 text-left"
                              onClick={() => onOpen(skill.name)}
                            >
                              <div className="flex items-center gap-2">
                                {iconSource ? (
                                  <img
                                    src={iconSource}
                                    alt=""
                                    className={cn(
                                      'size-6 rounded object-contain',
                                      skillIconInvertInDark(skill) &&
                                        'dark:invert'
                                    )}
                                  />
                                ) : (
                                  <span className="bg-muted/30 text-muted-foreground grid size-6 shrink-0 place-items-center rounded">
                                    <Box className="size-4" />
                                  </span>
                                )}
                                <span className="truncate text-sm font-medium">
                                  {skill.name}
                                </span>
                                <span className="text-muted-foreground text-xs">
                                  {categorizeSkill(skill)}
                                </span>
                                {metaText ? (
                                  <span className="text-muted-foreground text-xs">
                                    {metaText}
                                  </span>
                                ) : null}
                              </div>
                              <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                                {skill.description}
                              </p>
                            </button>
                            <div className="flex flex-col items-end gap-1 pt-0.5">
                              {renderEnabledToggle(skill)}
                              {renderRemoveButton(skill)}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </section>
                ) : null}
              </div>
            )}
          </div>
          {!catalogSearchMode ? (
          <aside className="flex w-full shrink-0 flex-col gap-4 xl:sticky xl:top-4 xl:self-start xl:w-[320px]">
            <section className="bg-background/70 rounded-lg p-2">
              <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
                Status
              </div>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  statusFilter === 'all'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setStatusFilter('all')}
              >
                All ({skills.length})
              </button>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  statusFilter === 'enabled'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setStatusFilter('enabled')}
              >
                Enabled ({enabledCount})
              </button>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  statusFilter === 'disabled'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setStatusFilter('disabled')}
              >
                Disabled ({disabledCount})
              </button>
            </section>
            <section className="bg-background/70 rounded-lg p-2">
              <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
                Categories
              </div>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  categoryFilter === 'all'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setCategoryFilter('all')}
              >
                All ({skills.length})
              </button>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  categoryFilter === 'featured'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setCategoryFilter('featured')}
              >
                Featured ({featuredCount})
              </button>
              {categories.map(category => (
                <button
                  key={category}
                  type="button"
                  className={cn(
                    'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                    categoryFilter === category
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                  onClick={() => setCategoryFilter(category)}
                >
                  {category} ({categoryCounts[category] || 0})
                </button>
              ))}
            </section>
            <section className="bg-background/70 rounded-lg p-2">
              <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
                Authors
              </div>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  authorFilter === 'all'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setAuthorFilter('all')}
              >
                All ({skills.length})
              </button>
              {authors.map(author => (
                <button
                  key={author}
                  type="button"
                  className={cn(
                    'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                    authorFilter === author
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                  onClick={() => setAuthorFilter(author)}
                >
                  {author} ({authorCounts[author] || 0})
                </button>
              ))}
            </section>
          </aside>
          ) : null}
        </div>
      </ScrollArea>
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
      {renderRemoveDialog()}
    </>
  )
}
