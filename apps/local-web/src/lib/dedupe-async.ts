/** Coalesce concurrent identical async work + optional short TTL result cache. */

type CacheEntry = { at: number; value: unknown }

const inflight = new Map<string, Promise<unknown>>()
const results = new Map<string, CacheEntry>()

export type DedupeOptions = {
  /** Serve a successful result younger than this many ms without re-fetching. */
  ttlMs?: number
  /** Bypass TTL and drop any cached value for this key. */
  force?: boolean
}

export function invalidateDedupe(prefix?: string): void {
  if (!prefix) {
    results.clear()
    return
  }
  for (const key of [...results.keys()]) {
    if (key === prefix || key.startsWith(prefix)) results.delete(key)
  }
}

export function dedupeAsync<T>(
  key: string,
  fn: () => Promise<T>,
  options?: DedupeOptions
): Promise<T> {
  const ttlMs = options?.ttlMs ?? 0
  if (options?.force) {
    results.delete(key)
    inflight.delete(key)
  }
  if (ttlMs > 0 && !options?.force) {
    const hit = results.get(key)
    if (hit && Date.now() - hit.at < ttlMs) {
      return Promise.resolve(hit.value as T)
    }
  }
  const existing = inflight.get(key)
  if (existing) return existing as Promise<T>
  const promise = fn()
    .then(value => {
      if (ttlMs > 0) results.set(key, { at: Date.now(), value })
      return value
    })
    .finally(() => {
      if (inflight.get(key) === promise) inflight.delete(key)
    })
  inflight.set(key, promise)
  return promise
}
