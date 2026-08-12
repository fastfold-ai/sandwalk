import type { UsageOverview } from '@sandwalk/agent-ui-core'

const TTL_MS = 45_000

let cached: { at: number; baseUrl: string; overview: UsageOverview } | null =
  null
let inflight: Promise<UsageOverview> | null = null
let inflightBaseUrl: string | null = null

export function readUsageOverviewCache(
  baseUrl: string
): UsageOverview | null {
  if (!cached) return null
  if (cached.baseUrl !== baseUrl) return null
  if (Date.now() - cached.at > TTL_MS) return null
  return cached.overview
}

export function writeUsageOverviewCache(
  baseUrl: string,
  overview: UsageOverview
): void {
  cached = { at: Date.now(), baseUrl, overview }
}

export function invalidateUsageOverviewCache(): void {
  cached = null
}

/** Warm Overview before the user opens it (fire-and-forget from bootstrap). */
export function prefetchUsageOverview(
  baseUrl: string,
  fetch: (signal?: AbortSignal) => Promise<UsageOverview>
): void {
  const existing = readUsageOverviewCache(baseUrl)
  if (existing) return
  if (inflight && inflightBaseUrl === baseUrl) return
  const controller = new AbortController()
  inflightBaseUrl = baseUrl
  inflight = fetch(controller.signal)
    .then(overview => {
      writeUsageOverviewCache(baseUrl, overview)
      return overview
    })
    .catch(() => {
      /* keep Overview lazy-load path */
      return null as unknown as UsageOverview
    })
    .finally(() => {
      if (inflightBaseUrl === baseUrl) {
        inflight = null
        inflightBaseUrl = null
      }
    })
}
