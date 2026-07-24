import type { AgentSkill } from '@sandwalk/agent-ui-core'

import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

export function SkillsListSidebar({
  skills,
  statusFilter,
  categoryFilter,
  authorFilter,
  categories,
  authors,
  categoryCounts,
  authorCounts,
  featuredCount,
  enabledCount,
  disabledCount,
  onStatusFilterChange,
  onCategoryFilterChange,
  onAuthorFilterChange,
  className
}: {
  skills: AgentSkill[]
  statusFilter: 'all' | 'enabled' | 'disabled'
  categoryFilter: string
  authorFilter: string
  categories: string[]
  authors: string[]
  categoryCounts: Record<string, number>
  authorCounts: Record<string, number>
  featuredCount: number
  enabledCount: number
  disabledCount: number
  onStatusFilterChange: (value: 'all' | 'enabled' | 'disabled') => void
  onCategoryFilterChange: (value: string) => void
  onAuthorFilterChange: (value: string) => void
  className?: string
}) {
  return (
    <aside
      className={cn(
        'flex w-full shrink-0 flex-col gap-4 xl:sticky xl:top-4 xl:max-h-[calc(100dvh-5.5rem)] xl:w-[320px] xl:self-start xl:overflow-hidden',
        className
      )}
    >
      <section className="bg-background/70 shrink-0 rounded-lg p-2">
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
          onClick={() => onStatusFilterChange('all')}
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
          onClick={() => onStatusFilterChange('enabled')}
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
          onClick={() => onStatusFilterChange('disabled')}
        >
          Disabled ({disabledCount})
        </button>
      </section>
      <section className="bg-background/70 shrink-0 rounded-lg p-2">
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
          onClick={() => onCategoryFilterChange('all')}
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
          onClick={() => onCategoryFilterChange('featured')}
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
            onClick={() => onCategoryFilterChange(category)}
          >
            {category} ({categoryCounts[category] || 0})
          </button>
        ))}
      </section>
      <section className="bg-background/70 min-h-0 flex-1 rounded-lg p-2">
        <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
          Authors
        </div>
        <ScrollArea className="h-[min(22rem,calc(100dvh-22rem))] pr-2">
          <button
            type="button"
            className={cn(
              'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
              authorFilter === 'all'
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
            onClick={() => onAuthorFilterChange('all')}
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
              onClick={() => onAuthorFilterChange(author)}
            >
              {author} ({authorCounts[author] || 0})
            </button>
          ))}
        </ScrollArea>
      </section>
    </aside>
  )
}
