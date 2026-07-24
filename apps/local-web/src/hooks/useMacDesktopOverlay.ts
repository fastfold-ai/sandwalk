import { useEffect, useState } from 'react'

import { isMacDesktopOverlay, isTauri, platformOS } from '@/lib/desktop'

const OVERLAY_CLASS = 'sandwalk-mac-overlay'

/**
 * Keeps macOS Tauri overlay chrome in sync. Detection can be wrong on the first
 * paint (globals injected late), so we re-check after mount.
 */
export function useMacDesktopOverlay() {
  const [overlay, setOverlay] = useState(() => isMacDesktopOverlay())

  useEffect(() => {
    const apply = () => {
      const next =
        isMacDesktopOverlay() ||
        (isTauri() && platformOS() === 'macos') ||
        // WKWebView / Tauri 2 sometimes exposes internals before __TAURI__.
        (typeof (globalThis as { __TAURI_INTERNALS__?: unknown })
          .__TAURI_INTERNALS__ !== 'undefined' &&
          platformOS() === 'macos')
      setOverlay(next)
      document.documentElement.dataset.platform = platformOS()
      document.documentElement.classList.toggle(OVERLAY_CLASS, next)
    }
    apply()
    const id = window.setTimeout(apply, 50)
    return () => {
      window.clearTimeout(id)
    }
  }, [])

  return overlay
}
