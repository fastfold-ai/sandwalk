import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { ListFilter, Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  CardGridSkeleton,
  ListRowsSkeleton
} from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { isFeaturedIntegration } from '@/lib/skills-catalog'

import { IntegrationsListSidebar } from './integrations-view-list-sidebar'
import { IntegrationCard } from './integrations-view-shared'

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
  const [filtersOpen, setFiltersOpen] = useState(false)

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
  const activeFilterCount =
    (integrationStatus !== 'all' ? 1 : 0) +
    (integrationCategory !== 'all' ? 1 : 0)

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

  const sidebarProps = {
    integrations,
    integrationStatus,
    integrationCategory,
    categories,
    categoryCounts,
    configuredCount,
    notConfiguredCount,
    featuredCount,
    onStatusChange: setIntegrationStatus,
    onCategoryChange: setIntegrationCategory
  }

  return (
    <div
      className={
        embedded
          ? 'flex h-[min(28rem,55vh)] min-h-0 flex-1 flex-col overflow-hidden'
          : 'flex h-full min-h-0 flex-1 flex-col overflow-hidden'
      }
    >
      <div
        className={
          embedded
            ? 'mx-auto flex h-full min-h-0 w-full max-w-5xl flex-1 flex-col gap-4 overflow-hidden p-1 xl:flex-row xl:items-stretch xl:gap-6'
            : 'mx-auto flex h-full min-h-0 w-full max-w-7xl flex-1 flex-col gap-4 overflow-hidden px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8 xl:flex-row xl:items-stretch xl:gap-6'
        }
      >
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {!embedded ? (
            <div className="mb-3 shrink-0">
              <h2 className="text-2xl font-semibold">Integrations</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Connect services the agent uses for search, communication,
                compute, and cloud workflows.
              </p>
            </div>
          ) : null}

          <div className="mb-3 flex shrink-0 flex-wrap items-center gap-2">
            <div className="relative min-w-[200px] flex-1">
              <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
              <Input
                value={integrationSearch}
                onChange={event => setIntegrationSearch(event.target.value)}
                placeholder="Search integrations, descriptions..."
                className="border-border/60 bg-muted/20 h-10 rounded-xl pl-10"
              />
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-10 xl:hidden"
              onClick={() => setFiltersOpen(true)}
            >
              <ListFilter className="mr-1.5 size-3.5" />
              Filters
              {activeFilterCount > 0 ? (
                <span className="bg-foreground text-background ml-1.5 inline-flex min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-medium tabular-nums">
                  {activeFilterCount}
                </span>
              ) : null}
            </Button>
          </div>

          {loading ? (
            <div className="min-h-0 flex-1 space-y-4 overflow-auto pb-4">
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
            <ScrollArea className="min-h-0 flex-1">
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
            </ScrollArea>
          )}
        </div>

        <div className="hidden xl:flex xl:h-full xl:min-h-0">
          <IntegrationsListSidebar {...sidebarProps} />
        </div>
      </div>

      <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
        <SheetContent
          side="right"
          className="w-[min(100vw,22rem)] gap-0 overflow-hidden p-0 sm:max-w-[22rem]"
        >
          <SheetHeader className="border-border/60 border-b px-4 py-3">
            <SheetTitle>Filters</SheetTitle>
            <SheetDescription>
              Narrow integrations by status or category.
            </SheetDescription>
          </SheetHeader>
          <ScrollArea className="h-[calc(100dvh-5.5rem)] px-3 py-3">
            <IntegrationsListSidebar
              {...sidebarProps}
              className="xl:static xl:h-auto xl:w-full xl:overflow-visible"
            />
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </div>
  )
}
