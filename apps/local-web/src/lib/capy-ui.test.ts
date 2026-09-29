import { describe, expect, it } from 'vitest'

import {
  applyCapyOpenSplit,
  CAPY_WINDOW_DEFAULT,
  clampCapyWindow,
  createDoubleTap,
  formatCapyUnreadBadge,
  isCapyHandsFreeKey,
  parseGridLayout,
  shouldRevealCapyMinimized
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

describe('Capy hands-free key', () => {
  it('fires on a Control double-tap inside the window', () => {
    const tap = createDoubleTap(400)
    expect(tap(1000)).toBe(false)
    expect(tap(1200)).toBe(true)
    expect(tap(1300)).toBe(false)
    expect(isCapyHandsFreeKey({ key: 'Control' })).toBe(true)
    expect(isCapyHandsFreeKey({ key: 'c', metaKey: true })).toBe(false)
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
