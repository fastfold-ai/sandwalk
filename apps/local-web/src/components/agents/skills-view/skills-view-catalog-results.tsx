import type { AgentCatalogSkill } from '@sandwalk/agent-ui-core'

import { ListRowsSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'

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
