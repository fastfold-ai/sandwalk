import type { AgentSkill } from '@sandwalk/agent-ui-core'
import { ArrowRight } from 'lucide-react'

import { CardGridSkeleton } from '@/components/agents/PageSkeletons'
import {
  featuredSkillIcon,
  isFeaturedSkill,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { skillMetaText } from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

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
                    'border-border/50 bg-muted/20 hover:border-border hover:bg-muted/35 flex items-start justify-between gap-3 rounded-2xl border p-3.5 transition-all',
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
