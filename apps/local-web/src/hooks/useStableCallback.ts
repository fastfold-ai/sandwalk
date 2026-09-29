import { useCallback, useRef } from 'react'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyFn = (...args: any[]) => any

/**
 * Return a function whose identity never changes but which always calls
 * the latest `fn`. Use at `memo` boundaries for handlers that parents
 * recreate on every render (the "useEvent" pattern). Not for values read
 * during render — only for callbacks invoked from events/effects.
 * `undefined` passes through unchanged so optional props stay optional.
 */
export function useStableCallback<T extends AnyFn | undefined>(fn: T): T {
  const ref = useRef<AnyFn | undefined>(fn)
  ref.current = fn
  const stable = useCallback((...args: unknown[]) => ref.current?.(...args), [])
  return (fn === undefined ? undefined : stable) as T
}
