import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  CardGridSkeleton,
  ListRowsSkeleton
} from '@/components/agents/PageSkeletons'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { isFeaturedIntegration } from '@/lib/skills-catalog'

import { IntegrationCard } from './integrations-view-shared'
import { IntegrationsListSidebar } from './integrations-view-list-sidebar'

export function IntegrationsMainListView({
  integrations,
  loading = false,
  embedded = false,
  onSelect
}: {
  integrations: IntegrationSummary[]
  loading?: boolean
  embedded?: boolean
  onSelect: (key: string) => void
}) {
  const [integrationSearch, setIntegrationSearch] = useState('')
  const [integrationCategory, setIntegrationCategory] = useState('all')
  const [integrationStatus, setIntegrationStatus] = useState<
    'all' | 'configured' | 'not_configured'
  >('all')

  const categories = useMemo(
    () =>
      Array.from(new Set(integrations.map(item => item.category))).sort(),
    [integrations]
  )
  const configuredCount = integrations.filter(item => item.configured).length
  const notConfiguredCount = integrations.length - configuredCount
  const featuredCount = integrations.filter(item =>
    isFeaturedIntegration(item)
  ).length
  const categoryCounts = useMemo(
    () =>
      integrations.reduce<Record<string, number>>((counts, item) => {
        counts[item.category] = (counts[item.category] || 0) + 1
        return counts
      }, {}),
    [integrations]
  )

  const { featuredVisible, nonFeaturedVisible, visibleIntegrations } =
    useMemo(() => {
      const visible = integrations.filter(item => {
        const query = integrationSearch.trim().toLowerCase()
        const matchesQuery =
          !query ||
          item.name.toLowerCase().includes(query) ||
          item.description.toLowerCase().includes(query) ||
          item.key.toLowerCase().includes(query)
        const matchesStatus =
          integrationStatus === 'all' ||
          (integrationStatus === 'configured'
            ? item.configured
            : !item.configured)
        const matchesCategory =
          integrationCategory === 'all'
            ? true
            : integrationCategory === 'featured'
              ? isFeaturedIntegration(item)
              : item.category === integrationCategory
        return matchesStatus && matchesQuery && matchesCategory
      })
      const ordered = [...visible].sort((a, b) => {
        const featuredDelta =
          Number(isFeaturedIntegration(b)) - Number(isFeaturedIntegration(a))
        if (featuredDelta !== 0) return featuredDelta
        return a.name.localeCompare(b.name)
      })
      return {
        visibleIntegrations: visible,
        featuredVisible: ordered.filter(item => isFeaturedIntegration(item)),
        nonFeaturedVisible: ordered.filter(item => !isFeaturedIntegration(item))
      }
    }, [
      integrationCategory,
      integrationSearch,
      integrationStatus,
      integrations
    ])

  return (
    <ScrollArea className={embedded ? 'h-[min(28rem,55vh)]' : 'flex-1'}>
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
              <h2 className="text-2xl font-semibold">Integrations</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Connect API keys and services the agent uses for models, search,
                compute, and cloud workflows.
              </p>
            </div>
          ) : null}
          <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 mb-4 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
            <div className="relative min-w-[280px] max-w-3xl flex-1">
              <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
              <Input
                value={integrationSearch}
                onChange={event => setIntegrationSearch(event.target.value)}
                placeholder="Search integrations, descriptions..."
                className="border-border/70 bg-background/70 h-11 pl-10"
              />
            </div>
          </div>
          {loading ? (
            <div className="space-y-4 pb-4">
              <section className="space-y-2">
                <Skeleton className="h-3 w-24" />
                <CardGridSkeleton cards={4} columns={2} />
              </section>
              <section className="space-y-2">
                <Skeleton className="h-3 w-16" />
                <div className="space-y-2">
                  <ListRowsSkeleton rows={5} />
                </div>
              </section>
            </div>
          ) : visibleIntegrations.length === 0 ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              No integrations match the current search/filter.
            </div>
          ) : (
            <div className="space-y-4 pb-4">
              {featuredVisible.length > 0 ? (
                <section className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium">
                    Featured ({featuredVisible.length})
                  </p>
                  <div className="grid gap-3 md:grid-cols-2">
                    {featuredVisible.map(item => (
                      <IntegrationCard
                        key={item.key}
                        item={item}
                        onSelect={onSelect}
                      />
                    ))}
                  </div>
                </section>
              ) : null}
              {integrationCategory !== 'featured' ? (
                <section className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium">
                    All ({nonFeaturedVisible.length})
                  </p>
                  <div className="space-y-2">
                    {nonFeaturedVisible.map(item => (
                      <IntegrationCard
                        key={item.key}
                        item={item}
                        onSelect={onSelect}
                      />
                    ))}
                  </div>
                </section>
              ) : null}
            </div>
          )}
        </div>
        <IntegrationsListSidebar
          integrations={integrations}
          integrationStatus={integrationStatus}
          integrationCategory={integrationCategory}
          categories={categories}
          categoryCounts={categoryCounts}
          configuredCount={configuredCount}
          notConfiguredCount={notConfiguredCount}
          featuredCount={featuredCount}
          onStatusChange={setIntegrationStatus}
          onCategoryChange={setIntegrationCategory}
        />
      </div>
    </ScrollArea>
  )
}
