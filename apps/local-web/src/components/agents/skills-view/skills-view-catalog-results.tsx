import type {
  AgentCatalogLeaderboardView,
  AgentCatalogSkill
} from '@sandwalk/agent-ui-core'
import { Loader, RefreshCw } from 'lucide-react'
import { type TouchEvent, useEffect, useRef, useState, type WheelEvent } from 'react'

import { ListRowsSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { formatCatalogInstallCount } from './skills-view-utils'

const LEADERBOARD_TABS: {
  id: AgentCatalogLeaderboardView
  label: string
}[] = [
  { id: 'all-time', label: 'All Time' },
  { id: 'trending', label: 'Trending (24h)' },
  { id: 'hot', label: 'Hot' }
]

const PULL_THRESHOLD = 64

function findScrollRoot(node: HTMLElement | null) {
  return node?.closest(
    '[data-radix-scroll-area-viewport]'
  ) as HTMLElement | null
}

export function SkillsCatalogResultsSection({
  query,
  catalogLoading,
  catalogLoadingMore,
  catalogRefreshing,
  catalogError,
  catalogResults,
  catalogHasMore,
  allTimeTotal,
  leaderboardView,
  onLeaderboardViewChange,
  onLoadMoreLeaderboard,
  onRefreshLeaderboard,
  showCatalogEmptyState,
  isCatalogSkillInstalled,
  onOpenCatalogDetail
}: {
  query: string
  catalogLoading: boolean
  catalogLoadingMore: boolean
  catalogRefreshing: boolean
  catalogError: string | null
  catalogResults: AgentCatalogSkill[]
  catalogTotal: number
  catalogHasMore: boolean
  allTimeTotal: number
  leaderboardView: AgentCatalogLeaderboardView
  onLeaderboardViewChange: (view: AgentCatalogLeaderboardView) => void
  onLoadMoreLeaderboard: () => void
  onRefreshLeaderboard: () => void
  showCatalogEmptyState: boolean
  isCatalogSkillInstalled: (skill: AgentCatalogSkill) => boolean
  onOpenCatalogDetail: (skill: AgentCatalogSkill) => void
}) {
  const searching = query.trim().length >= 2
  const showLeaderboard =
    !searching && !catalogError && catalogResults.length > 0
  const allTimeLabel =
    allTimeTotal > 0 ? allTimeTotal.toLocaleString('en-US') : null

  const sectionRef = useRef<HTMLDivElement | null>(null)
  const pullStartY = useRef<number | null>(null)
  const wheelPull = useRef(0)
  const [pullDistance, setPullDistance] = useState(0)
  const loadMoreRef = useRef(onLoadMoreLeaderboard)
  loadMoreRef.current = onLoadMoreLeaderboard

  useEffect(() => {
    if (
      searching ||
      !catalogHasMore ||
      catalogLoading ||
      catalogRefreshing ||
      catalogLoadingMore
    ) {
      return
    }
    const root = findScrollRoot(sectionRef.current)
    if (!root) return

    const maybeLoad = () => {
      const remaining = root.scrollHeight - root.scrollTop - root.clientHeight
      if (remaining <= 320) loadMoreRef.current()
    }

    maybeLoad()
    root.addEventListener('scroll', maybeLoad, { passive: true })
    return () => root.removeEventListener('scroll', maybeLoad)
  }, [
    searching,
    catalogHasMore,
    catalogLoading,
    catalogRefreshing,
    catalogLoadingMore,
    catalogResults.length
  ])

  const canPullRefresh =
    !searching &&
    !catalogLoading &&
    !catalogRefreshing &&
    catalogResults.length > 0

  const onTouchStart = (event: TouchEvent<HTMLDivElement>) => {
    if (!canPullRefresh) return
    const root = findScrollRoot(event.currentTarget)
    if ((root?.scrollTop ?? 0) > 0) return
    pullStartY.current = event.touches[0]?.clientY ?? null
  }

  const onTouchMove = (event: TouchEvent<HTMLDivElement>) => {
    if (pullStartY.current == null) return
    const root = findScrollRoot(event.currentTarget)
    if ((root?.scrollTop ?? 0) > 0) {
      pullStartY.current = null
      setPullDistance(0)
      return
    }
    const currentY = event.touches[0]?.clientY ?? pullStartY.current
    const distance = Math.max(0, Math.min(96, currentY - pullStartY.current))
    setPullDistance(distance)
  }

  const onTouchEnd = () => {
    if (pullStartY.current == null) return
    const shouldRefresh = pullDistance >= PULL_THRESHOLD
    pullStartY.current = null
    setPullDistance(0)
    if (shouldRefresh) onRefreshLeaderboard()
  }

  const onWheel = (event: WheelEvent<HTMLDivElement>) => {
    if (!canPullRefresh) {
      wheelPull.current = 0
      return
    }
    const root = findScrollRoot(event.currentTarget)
    if ((root?.scrollTop ?? 0) > 0 || event.deltaY >= 0) {
      wheelPull.current = 0
      return
    }
    // Trackpad overscroll at top → refresh after enough upward intent.
    wheelPull.current += -event.deltaY
    if (wheelPull.current < 140) return
    wheelPull.current = 0
    onRefreshLeaderboard()
  }

  return (
    <div
      ref={sectionRef}
      className="space-y-4 pb-4"
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
      onWheel={onWheel}
    >
      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
              Skills Leaderboard
            </p>
            <p className="text-muted-foreground mt-0.5 text-xs">
              {searching
                ? `${catalogResults.length} result${catalogResults.length === 1 ? '' : 's'} for “${query.trim()}”`
                : 'Browse the public skills.sh catalog'}
            </p>
          </div>
          {!searching ? (
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                disabled={catalogLoading || catalogRefreshing}
                onClick={() => onRefreshLeaderboard()}
                aria-label="Refresh leaderboard"
              >
                <RefreshCw
                  className={cn(
                    'size-3.5',
                    catalogRefreshing ? 'animate-spin' : ''
                  )}
                />
              </Button>
              <div className="flex items-center gap-1 border-b border-border/60">
                {LEADERBOARD_TABS.map(tab => (
                  <button
                    key={tab.id}
                    type="button"
                    className={cn(
                      'px-3 py-1.5 text-xs transition-colors',
                      leaderboardView === tab.id
                        ? 'text-foreground border-b-2 border-foreground -mb-px font-medium'
                        : 'text-muted-foreground hover:text-foreground'
                    )}
                    onClick={() => onLeaderboardViewChange(tab.id)}
                  >
                    {tab.label}
                    {tab.id === 'all-time' &&
                    allTimeLabel &&
                    !catalogLoading &&
                    !catalogRefreshing
                      ? ` (${allTimeLabel})`
                      : ''}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        {(pullDistance > 0 || catalogRefreshing) && !searching ? (
          <div
            className="text-muted-foreground flex items-center justify-center gap-2 text-xs transition-[height,opacity]"
            style={{
              height: catalogRefreshing
                ? 28
                : Math.max(0, pullDistance * 0.6),
              opacity: catalogRefreshing || pullDistance > 12 ? 1 : 0.5
            }}
          >
            <Loader
              className={cn(
                'size-3.5',
                catalogRefreshing || pullDistance >= PULL_THRESHOLD
                  ? 'animate-spin'
                  : ''
              )}
            />
            <span>
              {catalogRefreshing
                ? 'Refreshing…'
                : pullDistance >= PULL_THRESHOLD
                  ? 'Release to refresh'
                  : 'Pull to refresh'}
            </span>
          </div>
        ) : null}

        {catalogLoading && catalogResults.length === 0 ? (
          <ListRowsSkeleton rows={8} withToggle={false} />
        ) : null}
        {catalogError ? (
          <p className="text-destructive text-sm">{catalogError}</p>
        ) : null}
        {showCatalogEmptyState ? (
          <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
            No skills.sh results match “{query.trim()}”.
          </div>
        ) : null}

        {!catalogLoading &&
        !catalogRefreshing &&
        !catalogError &&
        !searching &&
        catalogResults.length === 0 ? (
          <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
            No leaderboard skills available right now.
          </div>
        ) : null}

        {showLeaderboard ||
        (!catalogLoading &&
          !catalogError &&
          searching &&
          catalogResults.length > 0) ? (
          <div className="overflow-hidden rounded-lg border border-border/60">
            <div className="text-muted-foreground grid grid-cols-[2.5rem_minmax(0,1fr)_5.5rem_auto] gap-2 border-b border-border/60 px-3 py-2 text-[10px] font-semibold tracking-wide uppercase">
              <span>#</span>
              <span>Skill</span>
              <span className="text-right">Installs</span>
              <span className="sr-only">Actions</span>
            </div>
            <div className="divide-y divide-border/50">
              {catalogResults.map((skill, index) => {
                const isInstalled = isCatalogSkillInstalled(skill)
                const title = skill.name || skill.slug
                const rank = index + 1
                return (
                  <div
                    key={skill.id || `${skill.source}/${skill.slug}`}
                    className="hover:bg-muted/30 grid grid-cols-[2.5rem_minmax(0,1fr)_5.5rem_auto] items-center gap-2 px-3 py-2.5 transition-colors"
                  >
                    <span className="text-muted-foreground text-xs tabular-nums">
                      {rank}
                    </span>
                    <button
                      type="button"
                      className="min-w-0 text-left"
                      onClick={() => onOpenCatalogDetail(skill)}
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <img
                          src="/suggestions/skills-sh.png"
                          alt=""
                          className="size-5 shrink-0 rounded object-contain dark:invert"
                        />
                        <span className="truncate text-sm font-medium">
                          {title}
                        </span>
                        <span className="text-muted-foreground truncate text-xs">
                          {skill.source}
                        </span>
                      </div>
                    </button>
                    <span className="text-right text-xs tabular-nums">
                      {skill.installs > 0
                        ? formatCatalogInstallCount(skill.installs)
                        : '—'}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => onOpenCatalogDetail(skill)}
                    >
                      {isInstalled ? 'Update' : 'View'}
                    </Button>
                  </div>
                )
              })}
            </div>
            {!searching ? (
              <div className="text-muted-foreground flex min-h-10 flex-col items-center justify-center gap-2 px-3 py-3 text-xs">
                {catalogLoadingMore ? (
                  <span className="flex items-center gap-2">
                    <Loader className="size-3.5 animate-spin" />
                    Loading more…
                  </span>
                ) : catalogHasMore ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => onLoadMoreLeaderboard()}
                  >
                    Load more
                  </Button>
                ) : catalogResults.length > 0 ? (
                  'End of leaderboard'
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  )
}
