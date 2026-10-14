import { beforeEach, describe, expect, it } from 'vitest'

import {
  applyCapyOpenSplit,
  CAPY_OPEN_EVENT,
  CAPY_REVEAL_MINIMIZED_EVENT,
  CAPY_SHORTCUT_CHANGE_EVENT,
  CAPY_UI_STORAGE_KEY,
  CAPY_WINDOW_DEFAULT,
  capyShortcutSymbols,
  clampCapyWindow,
  DEFAULT_CAPY_SHORTCUT,
  formatCapyUnreadBadge,
  isCapyHandsFreeKey,
  matchesCapyShortcut,
  parseGridLayout,
  readCapyShortcut,
  readCapyWindow,
  requestOpenCapy,
  requestRevealCapyMinimized,
  setCapyShortcutRecording,
  shortcutFromEvent,
  shouldRevealCapyMinimized,
  writeCapyShortcut,
  writeCapyWindow
} from './capy-ui'

describe('applyCapyOpenSplit', () => {
  it('creates a group and navigates when given two or more chats', () => {
    const paths: string[] = []
    const groupId = applyCapyOpenSplit(
      ['a', 'b', 'a'],
      ids => (ids.length >= 2 ? 'grp_test' : null),
      path => paths.push(path)
    )
    expect(groupId).toBe('grp_test')
    expect(paths).toEqual(['/agents/grp_test'])
  })

  it('does nothing for a single chat', () => {
    const paths: string[] = []
    expect(
      applyCapyOpenSplit(['only'], () => 'grp_x', path => paths.push(path))
    ).toBeNull()
    expect(paths).toEqual([])
  })
})

describe('clampCapyWindow', () => {
  const view = { width: 1000, height: 700 }

  it('keeps the expanded modal fully on screen from a corner', () => {
    const next = clampCapyWindow(
      {
        ...CAPY_WINDOW_DEFAULT,
        open: true,
        minimized: false,
        x: 980,
        y: 680,
        width: 520,
        height: 580
      },
      view
    )
    expect(next.x + next.width).toBeLessThanOrEqual(view.width - 8)
    expect(next.y + next.height).toBeLessThanOrEqual(view.height - 8)
    expect(next.x).toBeGreaterThanOrEqual(8)
    expect(next.y).toBeGreaterThanOrEqual(8)
  })

  it('keeps the minimized icon on screen in a corner', () => {
    const next = clampCapyWindow(
      {
        ...CAPY_WINDOW_DEFAULT,
        open: false,
        minimized: true,
        x: 1200,
        y: 900
      },
      view
    )
    expect(next.x + 56).toBeLessThanOrEqual(view.width - 8)
    expect(next.y + 56).toBeLessThanOrEqual(view.height - 8)
  })
})

describe('formatCapyUnreadBadge', () => {
  it('formats a macOS-style count', () => {
    expect(formatCapyUnreadBadge(0)).toBeNull()
    expect(formatCapyUnreadBadge(1)).toBe('1')
    expect(formatCapyUnreadBadge(12)).toBe('12')
    expect(formatCapyUnreadBadge(100)).toBe('99+')
  })
})

describe('shouldRevealCapyMinimized', () => {
  it('reveals only when Capy is fully hidden', () => {
    expect(shouldRevealCapyMinimized({ open: false, minimized: false })).toBe(true)
    expect(shouldRevealCapyMinimized({ open: true, minimized: false })).toBe(false)
    expect(shouldRevealCapyMinimized({ open: false, minimized: true })).toBe(false)
  })
})

function installStorage() {
  const store = new Map<string, string>()
  const storage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value)
    },
    removeItem: (key: string) => {
      store.delete(key)
    },
    clear: () => store.clear(),
    key: (index: number) => [...store.keys()][index] ?? null,
    get length() {
      return store.size
    }
  }
  Object.defineProperty(globalThis, 'localStorage', {
    value: storage,
    configurable: true
  })
}

describe('Capy window persistence', () => {
  beforeEach(() => installStorage())

  it('returns the default when nothing is stored or the payload is junk', () => {
    expect(readCapyWindow()).toEqual(CAPY_WINDOW_DEFAULT)
    localStorage.setItem(CAPY_UI_STORAGE_KEY, '{')
    expect(readCapyWindow()).toEqual(CAPY_WINDOW_DEFAULT)
  })

  it('round-trips a saved window and clamps it onto the viewport', () => {
    writeCapyWindow({
      ...CAPY_WINDOW_DEFAULT,
      open: true,
      x: 4000,
      y: 10,
      width: 400,
      height: 500
    })
    const next = readCapyWindow()
    expect(next.open).toBe(true)
    expect(next.width).toBe(400)
    expect(next.x).toBeLessThan(window.innerWidth)
  })

  it('asks the overlay to open or reveal', () => {
    const opened: string[] = []
    const onOpen = () => opened.push('open')
    const onReveal = () => opened.push('reveal')
    window.addEventListener(CAPY_OPEN_EVENT, onOpen)
    window.addEventListener(CAPY_REVEAL_MINIMIZED_EVENT, onReveal)
    requestOpenCapy()
    requestRevealCapyMinimized()
    window.removeEventListener(CAPY_OPEN_EVENT, onOpen)
    window.removeEventListener(CAPY_REVEAL_MINIMIZED_EVENT, onReveal)
    expect(opened).toEqual(['open', 'reveal'])
  })
})

describe('Capy shortcut storage', () => {
  beforeEach(() => {
    installStorage()
    setCapyShortcutRecording(false)
  })

  it('keeps the default until a two-part shortcut is saved', () => {
    expect(readCapyShortcut()).toEqual(DEFAULT_CAPY_SHORTCUT)
    localStorage.setItem('sandwalk:capy-shortcut', '{')
    expect(readCapyShortcut()).toEqual(DEFAULT_CAPY_SHORTCUT)
    localStorage.setItem('sandwalk:capy-shortcut', JSON.stringify({ ctrl: true }))
    expect(readCapyShortcut()).toEqual(DEFAULT_CAPY_SHORTCUT)
  })

  it('writes a custom chord and renders its symbols', () => {
    const shortcut = {
      ctrl: true,
      alt: false,
      shift: true,
      meta: true,
      key: 'enter'
    }
    const seen: unknown[] = []
    const onChange = (event: Event) =>
      seen.push((event as CustomEvent).detail)
    window.addEventListener(CAPY_SHORTCUT_CHANGE_EVENT, onChange)
    writeCapyShortcut(shortcut)
    window.removeEventListener(CAPY_SHORTCUT_CHANGE_EVENT, onChange)
    expect(readCapyShortcut()).toEqual(shortcut)
    expect(seen).toEqual([shortcut])
    expect(capyShortcutSymbols(shortcut)).toEqual(['⌃', '⇧', '⌘', 'enter'])
    expect(
      capyShortcutSymbols({
        ctrl: false,
        alt: true,
        shift: false,
        meta: false,
        key: 'k'
      })
    ).toEqual(['⌥', 'K'])
  })

  it('builds a shortcut only after two keys, and ignores Escape', () => {
    expect(shortcutFromEvent({ key: 'Escape', ctrlKey: true })).toBeNull()
    expect(shortcutFromEvent({ key: 'Control', repeat: true })).toBeNull()
    expect(shortcutFromEvent({ key: 'Control' })).toBeNull()
    expect(shortcutFromEvent({ key: 'k' })).toBeNull()
    expect(shortcutFromEvent({ key: 'Alt', ctrlKey: true })).toEqual({
      ctrl: true,
      alt: true,
      shift: false,
      meta: false,
      key: null
    })
    expect(shortcutFromEvent({ key: 'k', ctrlKey: true, metaKey: true })).toEqual({
      ctrl: true,
      alt: false,
      shift: false,
      meta: true,
      key: 'k'
    })
  })

  it('matches modifier-only chords and ignores repeats', () => {
    const chord = { ctrl: true, alt: true, shift: false, meta: false, key: null }
    expect(matchesCapyShortcut({ key: 'Alt', ctrlKey: true, repeat: true }, chord)).toBe(
      false
    )
    expect(matchesCapyShortcut({ key: 'Alt', ctrlKey: true }, chord)).toBe(true)
    expect(matchesCapyShortcut({ key: 'K', ctrlKey: true, shiftKey: true }, {
      ctrl: true,
      alt: false,
      shift: true,
      meta: false,
      key: 'k'
    })).toBe(true)
  })

  it('does not toggle hands-free while a shortcut is being recorded', () => {
    setCapyShortcutRecording(true)
    expect(isCapyHandsFreeKey({ key: 'Alt', ctrlKey: true })).toBe(false)
    setCapyShortcutRecording(false)
    expect(isCapyHandsFreeKey({ key: 'Alt', ctrlKey: true })).toBe(true)
  })
})

describe('Capy shortcut', () => {
  it('matches a custom modifier plus key', () => {
    expect(
      matchesCapyShortcut(
        { key: 'k', ctrlKey: true, shiftKey: true },
        { ctrl: true, alt: false, shift: true, meta: false, key: 'k' }
      )
    ).toBe(true)
    expect(
      matchesCapyShortcut(
        { key: 'k', ctrlKey: true },
        { ctrl: true, alt: false, shift: true, meta: false, key: 'k' }
      )
    ).toBe(false)
  })
})

describe('Capy hands-free key', () => {
  it('fires on Control-Option, not a bare Control tap', () => {
    expect(isCapyHandsFreeKey({ key: 'Alt', ctrlKey: true })).toBe(true)
    expect(isCapyHandsFreeKey({ key: 'Control', altKey: true })).toBe(true)
    expect(isCapyHandsFreeKey({ key: 'Control' })).toBe(false)
    expect(isCapyHandsFreeKey({ key: 'c', ctrlKey: true, altKey: true })).toBe(false)
    expect(isCapyHandsFreeKey({ key: 'Alt', ctrlKey: true, metaKey: true })).toBe(false)
  })
})

describe('parseGridLayout', () => {
  it('accepts positive integer rows/cols', () => {
    expect(parseGridLayout({ rows: 4, cols: 4 })).toEqual({ rows: 4, cols: 4 })
    expect(parseGridLayout({ rows: '2', cols: '3' })).toEqual({ rows: 2, cols: 3 })
  })

  it('rejects anything else', () => {
    expect(parseGridLayout(null)).toBeNull()
    expect(parseGridLayout('4x4')).toBeNull()
    expect(parseGridLayout({ rows: 0, cols: 4 })).toBeNull()
    expect(parseGridLayout({ rows: 1.5, cols: 2 })).toBeNull()
    expect(parseGridLayout({ rows: 99, cols: 2 })).toBeNull()
  })
})
