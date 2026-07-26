import type {
  ToolBatchAction,
  ToolBatchResult,
  ToolCatalog,
  ToolSummary
} from '@sandwalk/agent-ui-core'
import { ListFilter, Loader2, RefreshCw, Search } from 'lucide-react'
import { useState } from 'react'

import { ListRowsSkeleton } from '@/components/agents/PageSkeletons'
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

import { ToolsFilterSidebar } from './tools-view/tools-filter-sidebar'
import { ToolsViewToolRow } from './tools-view/tools-view-tool-row'
import { useToolsViewData } from './tools-view/use-tools-view-data'

export function ToolsView({
  onListTools,
  onUpdateToolEnabled,
  onBatchUpdateTools,
  onListDatasets,
  onOpenData
}: {
  onListTools: (signal?: AbortSignal) => Promise<ToolCatalog>
  onUpdateToolEnabled: (
    toolId: string,
    enabled: boolean,
    signal?: AbortSignal
  ) => Promise<ToolSummary>
  onBatchUpdateTools: (
    action: ToolBatchAction,
    ids: string[],
    signal?: AbortSignal
  ) => Promise<ToolBatchResult>
  onListDatasets: (signal?: AbortSignal) => Promise<import('@sandwalk/agent-ui-core').DatasetSummary[]>
  onOpenData: () => void
}) {
  const data = useToolsViewData({
    onListTools,
    onUpdateToolEnabled,
    onBatchUpdateTools,
    onListDatasets
  })
  const [filtersOpen, setFiltersOpen] = useState(false)
  const activeFilterCount =
    (data.tierFilter !== 'all' ? 1 : 0) +
    (data.statusFilter !== 'all' ? 1 : 0) +
    (data.categoryFilter !== 'all' ? 1 : 0)
  const sidebarProps = {
    toolsCount: data.tools.length,
    tierFilter: data.tierFilter,
    statusFilter: data.statusFilter,
    categoryFilter: data.categoryFilter,
    coreCount: data.coreCount,
    extraCount: data.extraCount,
    enabledCount: data.enabledCount,
    disabledCount: data.disabledCount,
    categories: data.categories,
    categoryCounts: data.categoryCounts,
    onTierFilterChange: data.setTierFilter,
    onStatusFilterChange: data.setStatusFilter,
    onCategoryFilterChange: data.setCategoryFilter
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <div className="mx-auto flex h-full min-h-0 w-full max-w-7xl flex-1 flex-col gap-4 overflow-hidden px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6 xl:flex-row xl:items-stretch xl:gap-6">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="mb-3 shrink-0">
            <h2 className="text-2xl font-semibold">Tools</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Research tools available to the agent. Toggle a tool off to hide it
              from the agent's discovery and calls. Core tools stay always on;
              Extra tools are opt-in.
            </p>
          </div>

          <div className="mb-3 flex shrink-0 flex-wrap items-center gap-2">
            <div className="relative min-w-[200px] flex-1">
              <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
              <Input
                value={data.query}
                onChange={event => data.setQuery(event.target.value)}
                placeholder="Search tools by name, description, or dataset"
                className="border-border/70 bg-background/70 h-11 pl-10"
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
            <Button
              variant="ghost"
              size="icon"
              className="size-9 shrink-0"
              disabled={data.refreshing || data.loading}
              onClick={() => void data.refresh()}
              aria-label="Refresh tools"
            >
              {data.refreshing || data.loading ? (
                <Loader2 className="animate-spin" />
              ) : (
                <RefreshCw />
              )}
            </Button>
          </div>

          {data.error ? (
            <div className="border-destructive/40 text-destructive mb-3 shrink-0 rounded-md border px-3 py-2 text-sm">
              {data.error}
            </div>
          ) : null}

          <div className="mb-3 flex shrink-0 items-center justify-between gap-2">
            <p className="text-muted-foreground text-xs">
              {data.enabledCount} of {data.tools.length} tools enabled
              {data.catalog && data.filtered.length !== data.tools.length
                ? ` · showing ${data.filtered.length}`
                : ''}
            </p>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground h-7 text-xs"
                disabled={data.batchBusy || data.enableEligible.length === 0}
                onClick={() => void data.batchUpdate('enable')}
              >
                {data.batchBusy ? <Loader2 className="animate-spin" /> : null}
                Enable ({data.enableEligible.length})
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-muted-foreground h-7 text-xs"
                disabled={data.batchBusy || data.disableEligible.length === 0}
                onClick={() => void data.batchUpdate('disable')}
              >
                {data.batchBusy ? <Loader2 className="animate-spin" /> : null}
                Disable ({data.disableEligible.length})
              </Button>
            </div>
          </div>

          <ScrollArea className="min-h-0 flex-1">
            <div className="bg-muted/20 border-border/60 divide-y overflow-hidden rounded-xl border shadow-sm">
              {data.loading && data.tools.length === 0 ? (
                <ListRowsSkeleton rows={8} />
              ) : data.filtered.length === 0 ? (
                <div className="text-muted-foreground px-4 py-8 text-sm">
                  No tools match this search.
                </div>
              ) : (
                data.filtered.map(tool => (
                  <ToolsViewToolRow
                    key={tool.id}
                    tool={tool}
                    pending={Boolean(data.pending[tool.id])}
                    onOpenData={onOpenData}
                    onToggle={() => void data.toggle(tool)}
                    resolveRequirement={data.resolveRequirement}
                  />
                ))
              )}
            </div>
          </ScrollArea>
        </div>

        <div className="hidden xl:flex xl:h-full xl:min-h-0">
          <ToolsFilterSidebar {...sidebarProps} />
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
              Narrow tools by tier, status, or category.
            </SheetDescription>
          </SheetHeader>
          <ScrollArea className="h-[calc(100dvh-5.5rem)] px-3 py-3">
            <ToolsFilterSidebar
              {...sidebarProps}
              className="xl:static xl:h-auto xl:w-full xl:overflow-visible"
            />
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </div>
  )
}
