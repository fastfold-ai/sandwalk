import type { NavigateFunction } from 'react-router-dom'

/**
 * Prefer in-app history back; fall back when this is the first router entry
 * (deep link / refresh). React Router stores the stack index on history.state.
 */
export function navigateBack(
  navigate: NavigateFunction,
  fallback: string
): void {
  const idx = window.history.state?.idx
  if (typeof idx === 'number' && idx > 0) {
    navigate(-1)
    return
  }
  navigate(fallback)
}
