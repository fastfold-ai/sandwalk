import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useEffect, useState } from 'react'

export type ProjectAssetStats = {
  fileCount: number
  fileBytes: number
  siteCount: number
  loading: boolean
}

const EMPTY: ProjectAssetStats = {
  fileCount: 0,
  fileBytes: 0,
  siteCount: 0,
  loading: true
}

/**
 * Library (+ optional project folder/sites) totals for metric cards.
 * When `projectId` is null, sums the global Library (overview File size).
 */
export function useProjectAssetStats(
  client: LocalAgentClient | null | undefined,
  projectId: string | null | undefined,
  enabled: boolean
): ProjectAssetStats {
  const [stats, setStats] = useState<ProjectAssetStats>(EMPTY)

  useEffect(() => {
    if (!enabled || !client) {
      setStats({ ...EMPTY, loading: false })
      return
    }
    let cancelled = false
    setStats(current => ({ ...current, loading: true }))

    const load = async () => {
      let libraryCount = 0
      let libraryBytes = 0
      let folderCount = 0
      let folderBytes = 0
      let siteCount = 0

      try {
        const library = await client.listLibrary({
          projectId: projectId || undefined,
          page: 0,
          perPage: 1
        })
        libraryCount = library.pagination.total
        libraryBytes = library.totalBytes ?? 0
      } catch {
        /* keep zeros */
      }

      if (projectId) {
        try {
          const folder = await client.listProjectFolderFiles(projectId)
          folderCount = folder.data.length
          folderBytes = folder.data.reduce(
            (sum, item) => sum + (item.size || 0),
            0
          )
        } catch {
          /* no linked folder or unavailable */
        }

        try {
          const sites = await client.listSites()
          siteCount = sites.filter(site => site.sourceProjectId === projectId)
            .length
        } catch {
          /* keep zero */
        }
      }

      if (!cancelled) {
        setStats({
          fileCount: libraryCount + folderCount,
          // Overview: library only. Project: library + linked folder.
          fileBytes: libraryBytes + folderBytes,
          siteCount,
          loading: false
        })
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [client, enabled, projectId])

  return stats
}

export function formatFileBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  const digits = value >= 100 || unit === 0 ? 0 : value >= 10 ? 1 : 2
  return `${value.toFixed(digits)} ${units[unit]}`
}
