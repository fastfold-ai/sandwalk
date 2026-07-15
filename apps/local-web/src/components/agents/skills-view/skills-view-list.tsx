import type { AgentCatalogSkill, AgentSkill } from '@sandwalk/agent-ui-core'
import {
  ArrowRight,
  Check,
  ChevronDown,
  GitBranch,
  Plus,
  Search,
  Upload
} from 'lucide-react'

import { CardGridSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  featuredSkillIcon,
  isFeaturedSkill,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { skillMetaText } from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

import {
  SkillsCatalogResultsSection,
  SkillsInstalledGridSection
} from './skills-view-list-content'
import { SkillsListSidebar } from './skills-view-list-sidebar'
import {
  SkillEnabledToggle,
  SkillRemoveButton,
  SkillsRemoveDialog
} from './skills-view-shared'

export function SkillsFeaturedOverview({
  skills,
  loading,
  pendingEnabled,
  pendingRemove,
  batchBusy,
  removeTarget,
  onShowAll,
  onOpen,
  onToggleEnabled,
  onRemove,
  onRemoveDialogOpenChange,
  onConfirmRemove
}: {
  skills: AgentSkill[]
  loading: boolean
  pendingEnabled: Record<string, boolean>
  pendingRemove: Record<string, boolean>
  batchBusy: boolean
  removeTarget:
    | { type: 'single'; name: string }
    | { type: 'filtered'; count: number }
    | null
  onShowAll?: () => void
  onOpen: (name: string) => void
  onToggleEnabled: (name: string, enabled: boolean) => void
  onRemove: (name: string) => void
  onRemoveDialogOpenChange: (open: boolean) => void
  onConfirmRemove: () => void
}) {
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
                    <SkillEnabledToggle
                      skill={skill}
                      pending={Boolean(pendingEnabled[skill.name])}
                      onToggle={onToggleEnabled}
                    />
                    <SkillRemoveButton
                      skill={skill}
                      pending={Boolean(pendingRemove[skill.name]) || batchBusy}
                      onRemove={onRemove}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>
      <SkillsRemoveDialog
        removeTarget={removeTarget}
        onOpenChange={onRemoveDialogOpenChange}
        onConfirm={onConfirmRemove}
      />
    </>
  )
}

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
  catalogError,
  catalogResults,
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
  catalogError: string | null
  catalogResults: AgentCatalogSkill[]
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
            <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 mb-4 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
              <div className="relative min-w-[280px] flex-1 max-w-3xl">
                <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
                <Input
                  value={query}
                  onChange={event => onQueryChange(event.target.value)}
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
                      onCatalogSearchModeChange(false)
                      return
                    }
                    onEnableCatalogSearchMode()
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
                    onClick={onEnableCatalogSearchMode}
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
              <SkillsCatalogResultsSection
                query={query}
                catalogLoading={catalogLoading}
                catalogError={catalogError}
                catalogResults={catalogResults}
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
            <SkillsListSidebar
              skills={skills}
              statusFilter={statusFilter}
              categoryFilter={categoryFilter}
              authorFilter={authorFilter}
              categories={categories}
              authors={authors}
              categoryCounts={categoryCounts}
              authorCounts={authorCounts}
              featuredCount={featuredCount}
              enabledCount={enabledCount}
              disabledCount={disabledCount}
              onStatusFilterChange={onStatusFilterChange}
              onCategoryFilterChange={onCategoryFilterChange}
              onAuthorFilterChange={onAuthorFilterChange}
            />
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
      <SkillsRemoveDialog
        removeTarget={removeTarget}
        onOpenChange={onRemoveDialogOpenChange}
        onConfirm={onConfirmRemove}
      />
    </>
  )
}
