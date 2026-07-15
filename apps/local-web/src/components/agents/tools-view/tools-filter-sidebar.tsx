import { ScrollArea } from '@/components/ui/scroll-area'

import { filterButtonClass } from './tools-view-shared'

export function ToolsFilterSidebar({
  toolsCount,
  tierFilter,
  statusFilter,
  categoryFilter,
  coreCount,
  extraCount,
  enabledCount,
  disabledCount,
  categories,
  categoryCounts,
  onTierFilterChange,
  onStatusFilterChange,
  onCategoryFilterChange
}: {
  toolsCount: number
  tierFilter: 'all' | 'core' | 'extra'
  statusFilter: 'all' | 'enabled' | 'disabled'
  categoryFilter: string
  coreCount: number
  extraCount: number
  enabledCount: number
  disabledCount: number
  categories: string[]
  categoryCounts: Record<string, number>
  onTierFilterChange: (value: 'all' | 'core' | 'extra') => void
  onStatusFilterChange: (value: 'all' | 'enabled' | 'disabled') => void
  onCategoryFilterChange: (value: string) => void
}) {
  return (
    <aside className="flex w-full shrink-0 flex-col gap-4 xl:sticky xl:top-4 xl:self-start xl:w-[280px]">
      <section className="bg-background/70 rounded-lg p-2">
        <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
          Tier
        </div>
        <button
          type="button"
          className={filterButtonClass(tierFilter === 'all')}
          onClick={() => onTierFilterChange('all')}
        >
          All ({toolsCount})
        </button>
        <button
          type="button"
          className={filterButtonClass(tierFilter === 'core')}
          onClick={() => onTierFilterChange('core')}
        >
          Core ({coreCount})
        </button>
        <button
          type="button"
          className={filterButtonClass(tierFilter === 'extra')}
          onClick={() => onTierFilterChange('extra')}
        >
          Extra ({extraCount})
        </button>
      </section>
      <section className="bg-background/70 rounded-lg p-2">
        <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
          Status
        </div>
        <button
          type="button"
          className={filterButtonClass(statusFilter === 'all')}
          onClick={() => onStatusFilterChange('all')}
        >
          All ({toolsCount})
        </button>
        <button
          type="button"
          className={filterButtonClass(statusFilter === 'enabled')}
          onClick={() => onStatusFilterChange('enabled')}
        >
          Enabled ({enabledCount})
        </button>
        <button
          type="button"
          className={filterButtonClass(statusFilter === 'disabled')}
          onClick={() => onStatusFilterChange('disabled')}
        >
          Disabled ({disabledCount})
        </button>
      </section>
      <section className="bg-background/70 flex min-h-0 flex-col rounded-lg p-2 xl:max-h-[calc(100vh-14rem)]">
        <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
          Categories
        </div>
        <ScrollArea className="min-h-0 flex-1 pr-2">
          <button
            type="button"
            className={filterButtonClass(categoryFilter === 'all')}
            onClick={() => onCategoryFilterChange('all')}
          >
            All ({toolsCount})
          </button>
          {categories.map(category => (
            <button
              key={category}
              type="button"
              className={filterButtonClass(categoryFilter === category)}
              onClick={() => onCategoryFilterChange(category)}
            >
              {category} ({categoryCounts[category] || 0})
            </button>
          ))}
        </ScrollArea>
      </section>
    </aside>
  )
}
