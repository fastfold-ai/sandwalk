import type {
  AgentCatalogLeaderboardView,
  AgentCatalogSkill
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useRef, useState } from 'react'

const LEADERBOARD_PAGE_SIZE = 100

export type CatalogLeaderboardPage = {
  data: AgentCatalogSkill[]
  total: number
  allTimeTotal: number
  hasMore: boolean
  page: number
}

function skillKey(skill: AgentCatalogSkill) {
  return skill.id || `${skill.source}/${skill.slug}`
}

function mergeSkills(
  current: AgentCatalogSkill[],
  next: AgentCatalogSkill[]
) {
  const seen = new Set(current.map(skillKey))
  const merged = [...current]
  for (const skill of next) {
    const key = skillKey(skill)
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(skill)
  }
  return merged
}

export function useSkillsViewCatalogSearch({
  catalogSearchMode,
  query,
  onSearchCatalog,
  onListCatalogLeaderboard
}: {
  catalogSearchMode: boolean
  query: string
  onSearchCatalog: (
    query: string,
    signal?: AbortSignal
  ) => Promise<AgentCatalogSkill[]>
  onListCatalogLeaderboard: (
    view: AgentCatalogLeaderboardView,
    options?: { page?: number; perPage?: number },
    signal?: AbortSignal
  ) => Promise<CatalogLeaderboardPage>
}) {
  const [catalogResults, setCatalogResults] = useState<AgentCatalogSkill[]>([])
  const [catalogTotal, setCatalogTotal] = useState(0)
  const [allTimeTotal, setAllTimeTotal] = useState(0)
  const [catalogHasMore, setCatalogHasMore] = useState(false)
  const [catalogPage, setCatalogPage] = useState(0)
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogLoadingMore, setCatalogLoadingMore] = useState(false)
  const [catalogRefreshing, setCatalogRefreshing] = useState(false)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [leaderboardView, setLeaderboardView] =
    useState<AgentCatalogLeaderboardView>('all-time')
  const [refreshTick, setRefreshTick] = useState(0)

  const searchRef = useRef(onSearchCatalog)
  searchRef.current = onSearchCatalog
  const leaderboardRef = useRef(onListCatalogLeaderboard)
  leaderboardRef.current = onListCatalogLeaderboard

  const catalogPageRef = useRef(0)
  catalogPageRef.current = catalogPage
  const catalogHasMoreRef = useRef(false)
  catalogHasMoreRef.current = catalogHasMore
  const catalogLoadingRef = useRef(false)
  catalogLoadingRef.current = catalogLoading
  const catalogLoadingMoreRef = useRef(false)
  catalogLoadingMoreRef.current = catalogLoadingMore
  const catalogRefreshingRef = useRef(false)
  catalogRefreshingRef.current = catalogRefreshing
  const loadMoreControllerRef = useRef<AbortController | null>(null)
  const refreshRequestedRef = useRef(false)
  const hasResultsRef = useRef(false)
  hasResultsRef.current = catalogResults.length > 0

  useEffect(() => {
    if (!catalogSearchMode) {
      setCatalogResults([])
      setCatalogTotal(0)
      setAllTimeTotal(0)
      setCatalogHasMore(false)
      setCatalogPage(0)
      setCatalogError(null)
      setCatalogLoading(false)
      setCatalogLoadingMore(false)
      setCatalogRefreshing(false)
      refreshRequestedRef.current = false
      loadMoreControllerRef.current?.abort()
      return
    }

    const text = query.trim()
    const searching = text.length >= 2
    const refreshing =
      !searching && refreshRequestedRef.current && hasResultsRef.current
    refreshRequestedRef.current = false
    const controller = new AbortController()
    loadMoreControllerRef.current?.abort()
    loadMoreControllerRef.current = null

    const timer = window.setTimeout(
      () => {
        setCatalogLoadingMore(false)
        setCatalogError(null)
        setCatalogHasMore(false)
        setCatalogPage(0)
        if (refreshing) {
          setCatalogRefreshing(true)
          setCatalogLoading(false)
        } else {
          setCatalogRefreshing(false)
          setCatalogLoading(true)
          if (!searching) setCatalogResults([])
        }

        const request = searching
          ? searchRef.current(text, controller.signal).then(items => ({
              data: items,
              total: items.length,
              allTimeTotal: 0,
              hasMore: false,
              page: 0
            }))
          : leaderboardRef.current(
              leaderboardView,
              { page: 0, perPage: LEADERBOARD_PAGE_SIZE },
              controller.signal
            )

        void request
          .then(result => {
            if (controller.signal.aborted) return
            setCatalogResults(result.data)
            setCatalogTotal(result.total)
            setCatalogHasMore(
              !searching &&
                (Boolean(result.hasMore) ||
                  result.data.length >= LEADERBOARD_PAGE_SIZE)
            )
            setCatalogPage(result.page)
            if (!searching) setAllTimeTotal(result.allTimeTotal || 0)
          })
          .catch(error => {
            if (controller.signal.aborted) return
            if (!refreshing) {
              setCatalogResults([])
              setCatalogTotal(0)
              setCatalogHasMore(false)
              setCatalogPage(0)
            }
            setCatalogError(
              error instanceof Error
                ? error.message
                : searching
                  ? 'Unable to search skills.sh.'
                  : 'Unable to load skills.sh leaderboard.'
            )
          })
          .finally(() => {
            if (controller.signal.aborted) return
            setCatalogLoading(false)
            setCatalogRefreshing(false)
          })
      },
      searching ? 220 : 0
    )

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [catalogSearchMode, leaderboardView, query, refreshTick])

  const loadMoreLeaderboard = useCallback(() => {
    const searching = query.trim().length >= 2
    if (
      !catalogSearchMode ||
      searching ||
      !catalogHasMoreRef.current ||
      catalogLoadingRef.current ||
      catalogLoadingMoreRef.current ||
      catalogRefreshingRef.current
    ) {
      return
    }

    const nextPage = catalogPageRef.current + 1
    const controller = new AbortController()
    loadMoreControllerRef.current?.abort()
    loadMoreControllerRef.current = controller
    setCatalogLoadingMore(true)
    setCatalogError(null)

    void leaderboardRef
      .current(
        leaderboardView,
        { page: nextPage, perPage: LEADERBOARD_PAGE_SIZE },
        controller.signal
      )
      .then(result => {
        if (controller.signal.aborted) return
        setCatalogResults(current => mergeSkills(current, result.data))
        setCatalogTotal(result.total)
        setCatalogHasMore(
          Boolean(result.hasMore) ||
            result.data.length >= LEADERBOARD_PAGE_SIZE
        )
        setCatalogPage(result.page)
        if (result.allTimeTotal > 0) setAllTimeTotal(result.allTimeTotal)
      })
      .catch(error => {
        if (controller.signal.aborted) return
        setCatalogError(
          error instanceof Error
            ? error.message
            : 'Unable to load more skills.sh results.'
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setCatalogLoadingMore(false)
        if (loadMoreControllerRef.current === controller) {
          loadMoreControllerRef.current = null
        }
      })
  }, [catalogSearchMode, leaderboardView, query])

  const refreshLeaderboard = useCallback(() => {
    const searching = query.trim().length >= 2
    if (
      !catalogSearchMode ||
      searching ||
      catalogLoadingRef.current ||
      catalogRefreshingRef.current
    ) {
      return
    }
    refreshRequestedRef.current = true
    setRefreshTick(tick => tick + 1)
  }, [catalogSearchMode, query])

  return {
    catalogResults,
    catalogTotal,
    allTimeTotal,
    catalogHasMore,
    catalogLoading,
    catalogLoadingMore,
    catalogRefreshing,
    catalogError,
    leaderboardView,
    setLeaderboardView,
    loadMoreLeaderboard,
    refreshLeaderboard,
    setCatalogResults,
    setCatalogError
  }
}
