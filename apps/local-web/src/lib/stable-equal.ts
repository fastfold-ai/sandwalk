/**
 * Identity-preserving equality helpers for React state.
 *
 * Loaders that refetch and `setState(freshArray)` hand every consumer a new
 * reference even when nothing changed, which defeats `memo` down the tree
 * (rows re-render their markdown on every run completion). Use these inside
 * updaters: `setSkills(prev => sameArrayBy(prev, next, skillKey) ? prev : next)`.
 */

/** True when both objects have the same own keys with `Object.is` values. */
export function shallowEqualObjects(
  a: Record<string, unknown> | null | undefined,
  b: Record<string, unknown> | null | undefined
): boolean {
  if (a === b) return true
  if (!a || !b) return false
  const keysA = Object.keys(a)
  if (keysA.length !== Object.keys(b).length) return false
  for (const key of keysA) {
    if (!Object.is(a[key], b[key])) return false
  }
  return true
}

/**
 * True when both arrays have the same length and `key(item)` matches
 * pairwise. `key` should fold in every field the UI renders.
 */
export function sameArrayBy<T>(
  a: readonly T[] | null | undefined,
  b: readonly T[] | null | undefined,
  key: (item: T) => string
): boolean {
  if (a === b) return true
  if (!a || !b || a.length !== b.length) return false
  for (let i = 0; i < a.length; i += 1) {
    if (key(a[i]) !== key(b[i])) return false
  }
  return true
}

/** Return `prev` when `next` is equal by `key`, else `next`. */
export function keepArrayIfSame<T>(
  prev: readonly T[],
  next: readonly T[],
  key: (item: T) => string
): readonly T[] {
  return sameArrayBy(prev, next, key) ? prev : next
}
