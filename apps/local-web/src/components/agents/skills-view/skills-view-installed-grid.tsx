import type { AgentSkill } from '@sandwalk/agent-ui-core'
import { Box, Download, Loader } from 'lucide-react'

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
import type { FeaturedPendingSkill } from './skills-view-utils'

export function SkillsInstalledGridSection({
  loading,
  visible,
  featuredVisible,
  featuredPendingInstall = [],
  nonFeaturedVisible,
  categoryFilter,
  disableEligibleCount,
  enableEligibleCount,
  removeEligibleCount,
  batchBusy,
  pendingEnabled,
  pendingRemove,
  pendingFeaturedInstall = {},
  onOpen,
  onToggleEnabled,
  onRemove,
  onSetFilteredEnabled,
  onRemoveFiltered,
  onInstallFeatured
}: {
  loading: boolean
  visible: AgentSkill[]
  featuredVisible: AgentSkill[]
  featuredPendingInstall?: FeaturedPendingSkill[]
  nonFeaturedVisible: AgentSkill[]
  categoryFilter: string
  disableEligibleCount: number
  enableEligibleCount: number
  removeEligibleCount: number
  batchBusy: boolean
  pendingEnabled: Record<string, boolean>
  pendingRemove: Record<string, boolean>
  pendingFeaturedInstall?: Record<string, boolean>
  onOpen: (name: string) => void
  onToggleEnabled: (name: string, enabled: boolean) => void
  onRemove: (name: string) => void
  onSetFilteredEnabled: (enabled: boolean) => void
  onRemoveFiltered: () => void
  onInstallFeatured?: (item: FeaturedPendingSkill) => void
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

  const featuredTotal = featuredVisible.length + featuredPendingInstall.length

  if (visible.length === 0 && featuredPendingInstall.length === 0) {
    return (
      <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
        No skills match the current search/filter.
      </div>
    )
  }

  return (
    <div className="space-y-4 pb-4">
      {featuredTotal > 0 ? (
        <section className="space-y-2">
          <p className="text-muted-foreground text-xs font-medium">
            Featured ({featuredTotal})
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
            {featuredPendingInstall.map(item => {
              const iconSource = featuredSkillIcon({
                name: item.name,
                iconSrc: null
              })
              const installing = Boolean(pendingFeaturedInstall[item.name])
              return (
                <div
                  key={`pending:${item.name}`}
                  className="bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg border border-dashed border-border/70 p-3 transition-colors"
                >
                  <div className="min-w-0 flex-1 text-left">
                    <div className="flex items-center gap-2">
                      <img
                        src={iconSource}
                        alt=""
                        className={cn(
                          'size-7 rounded object-contain',
                          skillIconInvertInDark({
                            name: item.name,
                            iconSrc: null
                          }) && 'dark:invert'
                        )}
                      />
                      <span className="truncate text-sm font-medium">
                        {item.name}
                      </span>
                    </div>
                    <p className="text-muted-foreground mt-0.5 text-xs">
                      Not installed · {item.source}
                    </p>
                    <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                      {item.description}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 pt-0.5">
                    <Button
                      type="button"
                      size="sm"
                      className="h-7 gap-1.5 px-2 text-xs"
                      disabled={installing || batchBusy || !onInstallFeatured}
                      onClick={() => onInstallFeatured?.(item)}
                    >
                      {installing ? (
                        <Loader className="size-3.5 animate-spin" />
                      ) : (
                        <Download className="size-3.5" />
                      )}
                      Install
                    </Button>
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
