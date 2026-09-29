import { type MutableRefObject,useRef } from 'react'

/**
 * Returns a ref that always holds the latest `value`.
 *
 * Use it to hand frequently-changing data (e.g. the `sessions` array that
 * every session event replaces) to callbacks and effects that only need
 * the *current* value when they run — without making the consumer re-render
 * or re-subscribe every time the identity changes. The ref object itself is
 * stable, so it's safe to pass through memoized props.
 *
 * Do not read `.current` during render: it's updated synchronously here, so
 * it's fresh for the current render, but the caller would still not
 * re-render when the value changes later.
 */
export function useLatestRef<T>(value: T): MutableRefObject<T> {
  const ref = useRef(value)
  ref.current = value
  return ref
}
