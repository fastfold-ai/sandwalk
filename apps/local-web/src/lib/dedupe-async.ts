/** Coalesce concurrent identical async work (e.g. React StrictMode double-mount). */
const inflight = new Map<string, Promise<unknown>>()

export function dedupeAsync<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key)
  if (existing) return existing as Promise<T>
  const promise = fn().finally(() => {
    if (inflight.get(key) === promise) inflight.delete(key)
  })
  inflight.set(key, promise)
  return promise
}
