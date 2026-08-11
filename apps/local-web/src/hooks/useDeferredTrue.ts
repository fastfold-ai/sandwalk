import { useEffect, useState } from 'react'

/**
 * Becomes true only after `flag` has stayed true for `delayMs`.
 * Becomes false immediately when `flag` is false.
 * Used so collapsed chrome icons appear after the sidebar finishes closing.
 */
export function useDeferredTrue(flag: boolean, delayMs: number) {
  const [value, setValue] = useState(flag)

  useEffect(() => {
    if (!flag) {
      setValue(false)
      return
    }
    const id = window.setTimeout(() => setValue(true), delayMs)
    return () => window.clearTimeout(id)
  }, [delayMs, flag])

  return value
}

/**
 * Crossfade helper: delayed true on rise, delayed false on fall.
 * Keeps chrome icons from disappearing in the gap between sidebar/main.
 */
export function useCrossfadeFlag(
  flag: boolean,
  showDelayMs: number,
  hideDelayMs: number
) {
  const [value, setValue] = useState(flag)

  useEffect(() => {
    const delay = flag ? showDelayMs : hideDelayMs
    const id = window.setTimeout(() => setValue(flag), delay)
    return () => window.clearTimeout(id)
  }, [flag, hideDelayMs, showDelayMs])

  return value
}
