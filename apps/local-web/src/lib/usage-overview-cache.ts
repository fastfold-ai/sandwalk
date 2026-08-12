import type { UsageOverview } from '@sandwalk/agent-ui-core'

const TTL_MS = 45_000

type CacheKey = string

function scopeKey(baseUrl: string, projectId?: string | null): CacheKey {
  const scoped = (projectId || '').trim()
  return scoped ? `${baseUrl}::project:${scoped}` : `${baseUrl}::global`
}

let cached: { at: number; key: CacheKey; overview: UsageOverview } | null =
  null
let inflight: Promise<UsageOverview> | null = null
let inflightKey: CacheKey | null = null

export function readUsageOverviewCache(
  baseUrl: string,
  projectId?: string | null
): UsageOverview | null {
  if (!cached) return null
  if (cached.key !== scopeKey(baseUrl, projectId)) return null
  if (Date.now() - cached.at > TTL_MS) return null
  return cached.overview
}

export function writeUsageOverviewCache(
  baseUrl: string,
  overview: UsageOverview,
  projectId?: string | null
): void {
  cached = {
    at: Date.now(),
    key: scopeKey(baseUrl, projectId),
    overview
  }
}

export function invalidateUsageOverviewCache(): void {
  cached = null
}

/** Warm Overview before the user opens it (fire-and-forget from bootstrap). */
export function prefetchUsageOverview(
  baseUrl: string,
  fetch: (signal?: AbortSignal) => Promise<UsageOverview>,
  projectId?: string | null
): void {
  const key = scopeKey(baseUrl, projectId)
  const existing = readUsageOverviewCache(baseUrl, projectId)
  if (existing) return
  if (inflight && inflightKey === key) return
  const controller = new AbortController()
  inflightKey = key
  inflight = fetch(controller.signal)
    .then(overview => {
      writeUsageOverviewCache(baseUrl, overview, projectId)
      return overview
    })
    .catch(() => {
      /* keep Overview lazy-load path */
      return null as unknown as UsageOverview
    })
    .finally(() => {
      if (inflightKey === key) {
        inflight = null
        inflightKey = null
      }
    })
}
