import type { IntegrationSummary } from '@sandwalk/agent-ui-core'

import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import { filterButtonClass } from '../tools-view/tools-view-shared'

export function IntegrationsListSidebar({
  integrations,
  integrationStatus,
  integrationCategory,
  categories,
  categoryCounts,
  configuredCount,
  notConfiguredCount,
  featuredCount,
  onStatusChange,
  onCategoryChange,
  className
}: {
  integrations: IntegrationSummary[]
  integrationStatus: 'all' | 'configured' | 'not_configured'
  integrationCategory: string
  categories: string[]
  categoryCounts: Record<string, number>
  configuredCount: number
  notConfiguredCount: number
  featuredCount: number
  onStatusChange: (value: 'all' | 'configured' | 'not_configured') => void
  onCategoryChange: (value: string) => void
  className?: string
}) {
  return (
    <aside
      className={cn(
        'flex w-full shrink-0 flex-col gap-4 xl:h-full xl:min-h-0 xl:w-[280px] xl:self-stretch xl:overflow-hidden',
        className
      )}
    >
      <section className="border-border/50 bg-muted/20 shrink-0 rounded-2xl border p-2.5">
        <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
          Status
        </div>
        <button
          type="button"
          className={filterButtonClass(integrationStatus === 'all')}
          onClick={() => onStatusChange('all')}
        >
          All ({integrations.length})
        </button>
        <button
          type="button"
          className={filterButtonClass(integrationStatus === 'configured')}
          onClick={() => onStatusChange('configured')}
        >
          Configured ({configuredCount})
        </button>
        <button
          type="button"
          className={filterButtonClass(integrationStatus === 'not_configured')}
          onClick={() => onStatusChange('not_configured')}
        >
          Not configured ({notConfiguredCount})
        </button>
      </section>
      <section className="border-border/50 bg-muted/20 flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border p-2.5">
        <div className="text-muted-foreground/60 mb-1 shrink-0 px-2 py-1 text-xs font-semibold">
          Categories
        </div>
        <ScrollArea className="min-h-0 flex-1 pr-2">
          <button
            type="button"
            className={filterButtonClass(integrationCategory === 'all')}
            onClick={() => onCategoryChange('all')}
          >
            All ({integrations.length})
          </button>
          <button
            type="button"
            className={filterButtonClass(integrationCategory === 'featured')}
            onClick={() => onCategoryChange('featured')}
          >
            Featured ({featuredCount})
          </button>
          {categories.map(category => (
            <button
              key={category}
              type="button"
              className={filterButtonClass(integrationCategory === category)}
              onClick={() => onCategoryChange(category)}
            >
              {category} ({categoryCounts[category] || 0})
            </button>
          ))}
        </ScrollArea>
      </section>
    </aside>
  )
}
