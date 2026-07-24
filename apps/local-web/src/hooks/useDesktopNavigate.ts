import { useEffect } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { isTauri, listenDesktopNavigate } from '@/lib/desktop'

/** Menubar deep-links / second-instance argv → SPA navigate. */
export function useDesktopNavigate(navigate: NavigateFunction) {
  useEffect(() => {
    if (!isTauri()) return
    let unlisten: (() => void) | undefined
    void listenDesktopNavigate(path => {
      navigate(path)
    }).then(fn => {
      unlisten = fn
    })
    return () => {
      unlisten?.()
    }
  }, [navigate])
}
