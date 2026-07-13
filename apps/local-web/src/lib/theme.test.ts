import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  applyPalette,
  applyTheme,
  getStoredPalette,
  getStoredTheme,
  PALETTE_CHANGE_EVENT,
  previewPalette,
  resolveDark,
  syncFavicon,
  THEME_CHANGE_EVENT,
  THEME_PALETTES,
  watchSystemTheme
} from './theme'

function installMemoryLocalStorage() {
  const store = new Map<string, string>()
  const memory: Storage = {
    get length() {
      return store.size
    },
    clear() {
      store.clear()
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null
    },
    key(index: number) {
      return [...store.keys()][index] ?? null
    },
    removeItem(key: string) {
      store.delete(key)
    },
    setItem(key: string, value: string) {
      store.set(key, String(value))
    }
  }
  vi.stubGlobal('localStorage', memory)
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: memory
  })
}

describe('theme', () => {
  beforeEach(() => {
    installMemoryLocalStorage()
    document.documentElement.className = ''
    document.documentElement.removeAttribute('data-palette')
    document
      .querySelectorAll('link[data-sandwalk-favicon]')
      .forEach(el => el.remove())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('exposes palette metadata', () => {
    expect(THEME_PALETTES.map(p => p.id)).toEqual([
      'default',
      'mirage',
      'mahal',
      'darwin'
    ])
  })

  it('reads and falls back for stored theme/palette', () => {
    expect(getStoredTheme()).toBe('system')
    expect(getStoredPalette()).toBe('default')

    localStorage.setItem('fastfold.theme', 'dark')
    localStorage.setItem('sandwalk.theme-palette', 'mirage')
    expect(getStoredTheme()).toBe('dark')
    expect(getStoredPalette()).toBe('mirage')

    localStorage.setItem('fastfold.theme', 'nope')
    localStorage.setItem('sandwalk.theme-palette', 'nope')
    expect(getStoredTheme()).toBe('system')
    expect(getStoredPalette()).toBe('default')
  })

  it('resolveDark honors explicit mode and system preference', () => {
    expect(resolveDark('dark')).toBe(true)
    expect(resolveDark('light')).toBe(false)

    const matchMedia = vi.fn().mockReturnValue({ matches: true })
    vi.stubGlobal('matchMedia', matchMedia)
    expect(resolveDark('system')).toBe(true)
    expect(matchMedia).toHaveBeenCalledWith('(prefers-color-scheme: dark)')
  })

  it('syncFavicon creates or updates the favicon link', () => {
    syncFavicon(true)
    const link = document.querySelector<HTMLLinkElement>(
      'link[data-sandwalk-favicon]'
    )
    expect(link?.href).toContain('/favicon-light.svg')
    syncFavicon(false)
    expect(link?.href).toContain('/favicon.svg')
  })

  it('applyTheme toggles dark class, stores mode, and emits event', () => {
    const handler = vi.fn()
    window.addEventListener(THEME_CHANGE_EVENT, handler as EventListener)
    applyTheme('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('fastfold.theme')).toBe('dark')
    expect(handler).toHaveBeenCalled()
    window.removeEventListener(THEME_CHANGE_EVENT, handler as EventListener)
  })

  it('applyPalette sets attribute for non-default and clears for default', () => {
    const handler = vi.fn()
    window.addEventListener(PALETTE_CHANGE_EVENT, handler as EventListener)
    applyPalette('darwin')
    expect(document.documentElement.getAttribute('data-palette')).toBe('darwin')
    applyPalette('default')
    expect(document.documentElement.hasAttribute('data-palette')).toBe(false)
    expect(handler).toHaveBeenCalled()
    window.removeEventListener(PALETTE_CHANGE_EVENT, handler as EventListener)
  })

  it('previewPalette mutates DOM without persisting', () => {
    previewPalette('mahal')
    expect(document.documentElement.getAttribute('data-palette')).toBe('mahal')
    expect(localStorage.getItem('sandwalk.theme-palette')).toBeNull()
    previewPalette('default')
    expect(document.documentElement.hasAttribute('data-palette')).toBe(false)
  })

  it('watchSystemTheme re-applies when stored mode is system', () => {
    const listeners = new Map<string, EventListener>()
    const media = {
      matches: false,
      addEventListener: vi.fn((event: string, cb: EventListener) => {
        listeners.set(event, cb)
      }),
      removeEventListener: vi.fn((event: string, cb: EventListener) => {
        if (listeners.get(event) === cb) listeners.delete(event)
      })
    }
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue(media))
    localStorage.setItem('fastfold.theme', 'system')

    const stop = watchSystemTheme()
    expect(media.addEventListener).toHaveBeenCalledWith(
      'change',
      expect.any(Function)
    )
    listeners.get('change')?.(new Event('change'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)

    stop()
    expect(media.removeEventListener).toHaveBeenCalled()
  })
})
