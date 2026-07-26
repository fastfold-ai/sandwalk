import { useEffect, useState } from 'react'

import {
  isMacDesktopOverlay,
  isTauri,
  listenWindowFullscreen,
  listenWindowGlassActive,
  platformOS,
  syncSidebarGlassTheme,
  windowIsFullscreen
} from '@/lib/desktop'
import {
  getStoredLiquidGlass,
  LIQUID_GLASS_CHANGE_EVENT,
  resolveDark
} from '@/lib/theme'

const OVERLAY_CLASS = 'sandwalk-mac-overlay'
const GLASS_CLASS = 'sandwalk-mac-glass'
const GLASS_ACTIVE_CLASS = 'sandwalk-mac-glass-active'
const FULLSCREEN_CLASS = 'sandwalk-mac-fullscreen'

/**
 * Keeps macOS Tauri overlay chrome in sync. Detection can be wrong on the first
 * paint (globals injected late), so we re-check after mount.
 *
 * Fullscreen drops the traffic-light left pad so nav buttons sit flush left.
 * Native glass stays installed; unfocused / preference-off paints a solid
 * sidebar over it so traffic lights are not torn down with the effect view.
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
      document.documentElement.classList.toggle(GLASS_CLASS, next)
      // Assume focused until the native shell reports otherwise.
      if (next && getStoredLiquidGlass()) {
        document.documentElement.classList.add(GLASS_ACTIVE_CLASS)
      } else {
        document.documentElement.classList.remove(GLASS_ACTIVE_CLASS)
      }
    }
    apply()
    // Native glass tint defaults to light until the SPA reports theme.
    void syncSidebarGlassTheme(resolveDark())
    const id = window.setTimeout(apply, 50)
    return () => {
      window.clearTimeout(id)
    }
  }, [])

  useEffect(() => {
    if (!overlay) {
      document.documentElement.classList.remove(FULLSCREEN_CLASS)
      document.documentElement.classList.remove(GLASS_ACTIVE_CLASS)
      return
    }

    const setFullscreen = (next: boolean) => {
      document.documentElement.classList.toggle(FULLSCREEN_CLASS, next)
    }

    const setGlassActive = (active: boolean) => {
      if (!getStoredLiquidGlass()) {
        document.documentElement.classList.remove(GLASS_ACTIVE_CLASS)
        return
      }
      document.documentElement.classList.toggle(GLASS_ACTIVE_CLASS, active)
    }

    const onLiquidGlassPref = (event: Event) => {
      const enabled = (event as CustomEvent<boolean>).detail
      if (!enabled) {
        document.documentElement.classList.remove(GLASS_ACTIVE_CLASS)
        return
      }
      // Interacting with Settings implies the window is focused.
      document.documentElement.classList.add(GLASS_ACTIVE_CLASS)
    }

    const sync = () => {
      void windowIsFullscreen().then(fs => {
        if (fs !== null) setFullscreen(fs)
      })
    }

    sync()
    let unlistenFullscreen: (() => void) | undefined
    let unlistenGlass: (() => void) | undefined
    void listenWindowFullscreen(setFullscreen).then(fn => {
      unlistenFullscreen = fn
    })
    void listenWindowGlassActive(setGlassActive).then(fn => {
      unlistenGlass = fn
    })
    window.addEventListener(LIQUID_GLASS_CHANGE_EVENT, onLiquidGlassPref)
    window.addEventListener('resize', sync)
    return () => {
      unlistenFullscreen?.()
      unlistenGlass?.()
      window.removeEventListener(LIQUID_GLASS_CHANGE_EVENT, onLiquidGlassPref)
      window.removeEventListener('resize', sync)
      document.documentElement.classList.remove(FULLSCREEN_CLASS)
    }
  }, [overlay])

  return overlay
}
