import { useRef } from 'react'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyFn = (...args: any[]) => any

/**
 * Return `props` with every function-valued field replaced by a wrapper
 * whose identity is stable for the life of the component and which always
 * calls the latest function. Non-function fields pass through untouched.
 *
 * Use right before spreading into a `memo` child whose parent recreates
 * its handlers each render (`buildHeaderProps(...)` style builders). A
 * handler that flips to `undefined` is passed as `undefined` so presence
 * checks (`onDelete ? <Item/> : null`) keep working.
 */
export function useStableHandlers<T extends object>(props: T): T {
  const latest = useRef<T>(props)
  latest.current = props
  const wrappers = useRef<Record<string, AnyFn>>({})
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(props)) {
    if (typeof value !== 'function') {
      out[key] = value
      continue
    }
    let wrapper = wrappers.current[key]
    if (!wrapper) {
      wrapper = (...args: unknown[]) => {
        const fn = (latest.current as Record<string, unknown>)[key]
        return typeof fn === 'function' ? (fn as AnyFn)(...args) : undefined
      }
      wrappers.current[key] = wrapper
    }
    out[key] = wrapper
  }
  return out as T
}
