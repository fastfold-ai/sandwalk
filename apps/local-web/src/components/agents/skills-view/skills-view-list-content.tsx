import type { AgentCatalogSkill, AgentSkill } from '@sandwalk/agent-ui-core'
import { Box } from 'lucide-react'

import {
  CardGridSkeleton,
  ListRowsSkeleton
} from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  featuredSkillIcon,
  skillIcon,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { categorizeSkill, skillMetaText } from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

import {
  SkillEnabledToggle,
  SkillRemoveButton
} from './skills-view-shared'
import { formatCatalogInstallCount } from './skills-view-utils'

export function SkillsCatalogResultsSection({
  query,
  catalogLoading,
  catalogError,
  catalogResults,
  showCatalogEmptyState,
  isCatalogSkillInstalled,
  onOpenCatalogDetail
}: {
  query: string
  catalogLoading: boolean
  catalogError: string | null
  catalogResults: AgentCatalogSkill[]
  showCatalogEmptyState: boolean
  isCatalogSkillInstalled: (skill: AgentCatalogSkill) => boolean
  onOpenCatalogDetail: (skill: AgentCatalogSkill) => void
}) {
  return (
    <div className="space-y-4 pb-4">
      <section className="space-y-2">
        <p className="text-muted-foreground text-xs font-medium">
          Skills.sh
          {query.trim().length >= 2
            ? ` · ${catalogResults.length} result${catalogResults.length === 1 ? '' : 's'}`
            : ''}
        </p>
        {catalogLoading ? <ListRowsSkeleton rows={5} withToggle={false} /> : null}
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
                    onClick={() => onOpenCatalogDetail(skill)}
                  >
                    <div className="flex items-center gap-2">
                      <img
                        src="/suggestions/skills-sh.png"
                        alt=""
                        className="size-6 rounded object-contain dark:invert"
                      />
                      <span className="truncate text-sm font-medium">{title}</span>
                      <span className="text-muted-foreground truncate text-xs">
                        {skill.source}
                      </span>
                      {skill.installs > 0 ? (
                        <span className="text-muted-foreground shrink-0 text-xs">
                          {formatCatalogInstallCount(skill.installs)} installs
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
                      onClick={() => onOpenCatalogDetail(skill)}
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
  )
}

export function SkillsInstalledGridSection({
  loading,
  visible,
  featuredVisible,
  nonFeaturedVisible,
  categoryFilter,
  disableEligibleCount,
  enableEligibleCount,
  removeEligibleCount,
  batchBusy,
  pendingEnabled,
  pendingRemove,
  onOpen,
  onToggleEnabled,
  onRemove,
  onSetFilteredEnabled,
  onRemoveFiltered
}: {
  loading: boolean
  visible: AgentSkill[]
  featuredVisible: AgentSkill[]
  nonFeaturedVisible: AgentSkill[]
  categoryFilter: string
  disableEligibleCount: number
  enableEligibleCount: number
  removeEligibleCount: number
  batchBusy: boolean
  pendingEnabled: Record<string, boolean>
  pendingRemove: Record<string, boolean>
  onOpen: (name: string) => void
  onToggleEnabled: (name: string, enabled: boolean) => void
  onRemove: (name: string) => void
  onSetFilteredEnabled: (enabled: boolean) => void
  onRemoveFiltered: () => void
}) {
  if (loading) {
    return (
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
    )
  }

  if (visible.length === 0) {
    return (
      <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
        No skills match the current search/filter.
      </div>
    )
  }

  return (
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
                onClick={() => onSetFilteredEnabled(false)}
              >
                Disable ({disableEligibleCount})
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground h-7 text-xs"
                disabled={enableEligibleCount === 0 || batchBusy}
                onClick={() => onSetFilteredEnabled(true)}
              >
                Enable ({enableEligibleCount})
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground h-7 text-xs"
                disabled={removeEligibleCount === 0 || batchBusy}
                onClick={onRemoveFiltered}
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
                            skillIconInvertInDark(skill) && 'dark:invert'
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
                    <SkillEnabledToggle
                      skill={skill}
                      pending={Boolean(pendingEnabled[skill.name])}
                      onToggle={onToggleEnabled}
                    />
                    <SkillRemoveButton
                      skill={skill}
                      pending={
                        Boolean(pendingRemove[skill.name]) || batchBusy
                      }
                      onRemove={onRemove}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      ) : null}
    </div>
  )
}
