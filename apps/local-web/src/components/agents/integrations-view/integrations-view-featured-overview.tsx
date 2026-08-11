import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { ArrowRight } from 'lucide-react'

import { CardGridSkeleton } from '@/components/agents/PageSkeletons'
import { isFeaturedIntegration } from '@/lib/skills-catalog'

import { IntegrationCard } from './integrations-view-shared'

export function IntegrationsFeaturedOverview({
  integrations,
  loading,
  onShowAll,
  onSelect
}: {
  integrations: IntegrationSummary[]
  loading?: boolean
  onShowAll?: () => void
  onSelect: (key: string) => void
}) {
  const featuredAll = integrations.filter(item => isFeaturedIntegration(item))
  const featured = featuredAll.slice(0, 2)

  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold tracking-tight">Integrations</h3>
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
          No featured integrations yet.
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {featured.map(item => (
            <IntegrationCard key={item.key} item={item} onSelect={onSelect} />
          ))}
        </div>
      )}
    </section>
  )
}
