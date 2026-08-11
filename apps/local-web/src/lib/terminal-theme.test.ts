import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  buildTerminalTheme,
  isDocumentDark,
  readDocumentPalette,
  watchTerminalTheme
} from './terminal-theme'
import { PALETTE_CHANGE_EVENT, THEME_CHANGE_EVENT } from './theme'

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

describe('terminal-theme', () => {
  beforeEach(() => {
    installMemoryLocalStorage()
    document.documentElement.className = ''
    document.documentElement.removeAttribute('data-palette')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('reads dark mode and palette from the document', () => {
    expect(isDocumentDark()).toBe(false)
    expect(readDocumentPalette()).toBe('default')

    document.documentElement.classList.add('dark')
    document.documentElement.setAttribute('data-palette', 'mirage')
    expect(isDocumentDark()).toBe(true)
    expect(readDocumentPalette()).toBe('mirage')

    document.documentElement.setAttribute('data-palette', 'mahal')
    expect(readDocumentPalette()).toBe('mahal')
    document.documentElement.setAttribute('data-palette', 'darwin')
    expect(readDocumentPalette()).toBe('darwin')
    document.documentElement.setAttribute('data-palette', 'fabienk')
    expect(readDocumentPalette()).toBe('fabienk')
    document.documentElement.setAttribute('data-palette', 'dune')
    expect(readDocumentPalette()).toBe('dune')
    document.documentElement.setAttribute('data-palette', 'neonnoir')
    expect(readDocumentPalette()).toBe('neonnoir')
    document.documentElement.setAttribute('data-palette', 'nope')
    expect(readDocumentPalette()).toBe('default')
  })

  it('builds light and dark default ANSI themes with fallbacks', () => {
    const light = buildTerminalTheme(false, 'default')
    expect(light.background).toBe('#FAFAFA')
    expect(light.foreground).toBe('#24292F')
    expect(light.cursor).toBe('#0969DA')
    expect(light.green).toBe('#1A7F37')
    expect(light.cursorAccent).toBe(light.background)

    const dark = buildTerminalTheme(true, 'default')
    expect(dark.background).toBe('#0D1117')
    expect(dark.foreground).toBe('#E6EDF3')
    expect(dark.blue).toBe('#58A6FF')
    expect(dark.selectionBackground).toBe('rgba(88, 166, 255, 0.28)')
  })

  it('uses palette-tinted ANSI for mirage, mahal, darwin, fabienk, dune, and neonnoir', () => {
    const mirage = buildTerminalTheme(true, 'mirage')
    expect(mirage.yellow).toBe('#E2B045')
    expect(mirage.green).toBe('#9BBB5C')

    const mahalLight = buildTerminalTheme(false, 'mahal')
    expect(mahalLight.black).toBe('#3A2418')

    const darwinDark = buildTerminalTheme(true, 'darwin')
    expect(darwinDark.green).toBe('#52B788')

    const fabienkDark = buildTerminalTheme(true, 'fabienk')
    expect(fabienkDark.yellow).toBe('#F8B144')
    expect(fabienkDark.brightYellow).toBe('#FFC857')

    const duneLight = buildTerminalTheme(false, 'dune')
    expect(duneLight.brightBlue).toBe('#8BB6B6')
    expect(duneLight.brightYellow).toBe('#D4A373')

    const noir = buildTerminalTheme(true, 'neonnoir')
    expect(noir.magenta).toBe('#E83A8A')
    expect(noir.brightMagenta).toBe('#FF4DA6')
  })

  it('prefers CSS token values when present on the document', () => {
    const spy = vi
      .spyOn(window, 'getComputedStyle')
      .mockReturnValue({
        getPropertyValue: (token: string) => {
          if (token === '--card') return '0 0% 10%'
          if (token === '--foreground') return '0 0% 98%'
          if (token === '--primary') return '210 100% 56%'
          return ''
        }
      } as CSSStyleDeclaration)

    const theme = buildTerminalTheme(true, 'default')
    expect(theme.background).toBe('hsl(0 0% 10%)')
    expect(theme.foreground).toBe('hsl(0 0% 98%)')
    expect(theme.cursor).toBe('hsl(210 100% 56%)')
    expect(theme.selectionBackground).toBe('hsl(210 100% 56% / 0.28)')
    spy.mockRestore()
  })

  it('watches window theme events and cleans up on stop', () => {
    const onChange = vi.fn()
    const stop = watchTerminalTheme(onChange)

    window.dispatchEvent(new Event(THEME_CHANGE_EVENT))
    window.dispatchEvent(new Event(PALETTE_CHANGE_EVENT))
    expect(onChange).toHaveBeenCalledTimes(2)

    stop()
    onChange.mockClear()
    window.dispatchEvent(new Event(THEME_CHANGE_EVENT))
    window.dispatchEvent(new Event(PALETTE_CHANGE_EVENT))
    expect(onChange).not.toHaveBeenCalled()
  })
})
