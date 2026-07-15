import type { IntegrationSummary } from '@sandwalk/agent-ui-core'

import { cn } from '@/lib/utils'

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
  onCategoryChange
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
}) {
  return (
    <aside className="flex w-full shrink-0 flex-col gap-4 xl:sticky xl:top-4 xl:self-start xl:w-[320px]">
      <section className="bg-background/70 rounded-lg p-2">
        <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
          Status
        </div>
        <button
          type="button"
          className={cn(
            'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
            integrationStatus === 'all'
              ? 'bg-muted text-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          )}
          onClick={() => onStatusChange('all')}
        >
          All ({integrations.length})
        </button>
        <button
          type="button"
          className={cn(
            'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
            integrationStatus === 'configured'
              ? 'bg-muted text-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          )}
          onClick={() => onStatusChange('configured')}
        >
          Configured ({configuredCount})
        </button>
        <button
          type="button"
          className={cn(
            'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
            integrationStatus === 'not_configured'
              ? 'bg-muted text-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          )}
          onClick={() => onStatusChange('not_configured')}
        >
          Not configured ({notConfiguredCount})
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
            integrationCategory === 'all'
              ? 'bg-muted text-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          )}
          onClick={() => onCategoryChange('all')}
        >
          All ({integrations.length})
        </button>
        <button
          type="button"
          className={cn(
            'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
            integrationCategory === 'featured'
              ? 'bg-muted text-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
          )}
          onClick={() => onCategoryChange('featured')}
        >
          Featured ({featuredCount})
        </button>
        {categories.map(category => (
          <button
            key={category}
            type="button"
            className={cn(
              'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
              integrationCategory === category
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
            onClick={() => onCategoryChange(category)}
          >
            {category} ({categoryCounts[category] || 0})
          </button>
        ))}
      </section>
    </aside>
  )
}
