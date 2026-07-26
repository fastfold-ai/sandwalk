import { useEffect } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { isTauri, listenDesktopNavigate } from '@/lib/desktop'

/** In-app routes only — reject absolute FS paths from argv (e.g. the binary). */
export function isSpaDesktopRoute(path: string) {
  if (path === '/') return true
  if (!path.startsWith('/') || path.startsWith('//')) return false
  const head = path.slice(1).split('/')[0] ?? ''
  return (
    head === 'agents' ||
    head === 'dashboard' ||
    head === 'library' ||
    head === 'projects' ||
    head === 'onboarding'
  )
}

/** Menubar launches / second-instance argv → SPA navigate. */
export function useDesktopNavigate(
  navigate: NavigateFunction,
  onRoute?: (path: string) => void
) {
  useEffect(() => {
    if (!isTauri()) return

    const go = (path: string) => {
      if (!isSpaDesktopRoute(path)) return
      navigate(path)
      onRoute?.(path)
    }

    const initial = (
      globalThis as { __SANDWALK_INITIAL_ROUTE__?: unknown }
    ).__SANDWALK_INITIAL_ROUTE__
    if (typeof initial === 'string') {
      go(initial)
      delete (globalThis as { __SANDWALK_INITIAL_ROUTE__?: unknown })
        .__SANDWALK_INITIAL_ROUTE__
    }

    let unlisten: (() => void) | undefined
    void listenDesktopNavigate(path => {
      go(path)
    }).then(fn => {
      unlisten = fn
    })
    return () => {
      unlisten?.()
    }
  }, [navigate, onRoute])
}
