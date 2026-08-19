import type { PaneNode } from '@sandwalk/agent-ui-core'
import { describe, expect, it } from 'vitest'

import {
  buildDefaultTree,
  closePane,
  extractChatIds,
  reconcileTree,
  setBranchRatios,
  splitPane
} from './useChatTiling'

describe('buildDefaultTree', () => {
  it('returns a bare chat leaf for a single chatId', () => {
    const t = buildDefaultTree(['a'])
    expect(t).toEqual({ type: 'chat', chatId: 'a' })
  })

  it('returns a horizontal branch with equal ratios for N chats', () => {
    const t = buildDefaultTree(['a', 'b', 'c'])
    expect(t.type).toBe('branch')
    if (t.type !== 'branch') return
    expect(t.direction).toBe('horizontal')
    expect(t.ratios).toEqual([1 / 3, 1 / 3, 1 / 3])
    expect(t.children.map(c => (c.type === 'chat' ? c.chatId : '?'))).toEqual([
      'a',
      'b',
      'c'
    ])
  })
})

describe('extractChatIds', () => {
  it('walks the tree in order', () => {
    const t: PaneNode = {
      type: 'branch',
      direction: 'horizontal',
      ratios: [0.5, 0.5],
      children: [
        { type: 'chat', chatId: 'a' },
        {
          type: 'branch',
          direction: 'vertical',
          ratios: [0.5, 0.5],
          children: [
            { type: 'chat', chatId: 'b' },
            { type: 'chat', chatId: 'c' }
          ]
        }
      ]
    }
    expect(extractChatIds(t)).toEqual(['a', 'b', 'c'])
  })
})

describe('splitPane', () => {
  it('splits a bare chat leaf into a branch', () => {
    const t = buildDefaultTree(['a'])
    const next = splitPane(t, 'a', 'horizontal', 'b', 'after')
    expect(next.type).toBe('branch')
    if (next.type !== 'branch') return
    expect(next.direction).toBe('horizontal')
    expect(next.children.map(c => (c.type === 'chat' ? c.chatId : '?'))).toEqual([
      'a',
      'b'
    ])
  })

  it('inserts as a sibling when the parent direction matches', () => {
    const t = buildDefaultTree(['a', 'b']) // horizontal
    const next = splitPane(t, 'a', 'horizontal', 'c', 'after')
    expect(next.type).toBe('branch')
    if (next.type !== 'branch') return
    expect(next.children).toHaveLength(3)
    expect(extractChatIds(next)).toEqual(['a', 'c', 'b'])
    expect(next.ratios).toEqual([1 / 3, 1 / 3, 1 / 3])
  })

  it('wraps in a new branch when directions are perpendicular', () => {
    const t = buildDefaultTree(['a', 'b']) // horizontal
    const next = splitPane(t, 'b', 'vertical', 'c', 'after')
    if (next.type !== 'branch') throw new Error('expected branch')
    // b was wrapped into a vertical branch { b, c }
    const wrapped = next.children[1]
    expect(wrapped.type).toBe('branch')
    if (wrapped.type !== 'branch') return
    expect(wrapped.direction).toBe('vertical')
    expect(extractChatIds(wrapped)).toEqual(['b', 'c'])
  })

  it('respects side=before', () => {
    const t = buildDefaultTree(['a', 'b'])
    const next = splitPane(t, 'a', 'horizontal', 'c', 'before')
    expect(extractChatIds(next)).toEqual(['c', 'a', 'b'])
  })
})

describe('closePane', () => {
  it('returns null when closing the last chat', () => {
    const t = buildDefaultTree(['a'])
    expect(closePane(t, 'a')).toBeNull()
  })

  it('collapses a 2-child branch to a bare leaf when one closes', () => {
    const t = buildDefaultTree(['a', 'b'])
    const next = closePane(t, 'a')
    expect(next).toEqual({ type: 'chat', chatId: 'b' })
  })

  it('re-normalizes ratios among surviving siblings', () => {
    const t = buildDefaultTree(['a', 'b', 'c']) // ratios [1/3, 1/3, 1/3]
    const next = closePane(t, 'b')
    if (!next || next.type !== 'branch') throw new Error('expected branch')
    expect(next.children).toHaveLength(2)
    expect(next.ratios[0] + next.ratios[1]).toBeCloseTo(1)
  })

  it('bubbles a single-child nested branch up', () => {
    // Structure: horiz [ a, vert [ b, c ] ]. Closing c should collapse
    // the vertical branch to just `b`, giving horiz [ a, b ].
    const t: PaneNode = {
      type: 'branch',
      direction: 'horizontal',
      ratios: [0.5, 0.5],
      children: [
        { type: 'chat', chatId: 'a' },
        {
          type: 'branch',
          direction: 'vertical',
          ratios: [0.5, 0.5],
          children: [
            { type: 'chat', chatId: 'b' },
            { type: 'chat', chatId: 'c' }
          ]
        }
      ]
    }
    const next = closePane(t, 'c')
    expect(extractChatIds(next!)).toEqual(['a', 'b'])
  })
})

describe('setBranchRatios', () => {
  it('renormalizes ratios at the given path', () => {
    const t = buildDefaultTree(['a', 'b'])
    const next = setBranchRatios(t, [], [0.7, 0.3])
    if (next.type !== 'branch') throw new Error('expected branch')
    expect(next.ratios[0]).toBeCloseTo(0.7)
    expect(next.ratios[1]).toBeCloseTo(0.3)
  })

  it('ignores calls whose ratio count does not match children', () => {
    const t = buildDefaultTree(['a', 'b'])
    const next = setBranchRatios(t, [], [0.7])
    expect(next).toBe(t) // unchanged
  })
})

describe('reconcileTree', () => {
  it('drops leaves whose chatId is not in the chatIds list', () => {
    const t = buildDefaultTree(['a', 'b'])
    const next = reconcileTree(t, ['a'])
    expect(next).toEqual({ type: 'chat', chatId: 'a' })
  })

  it('appends missing chats at the root', () => {
    const t = buildDefaultTree(['a'])
    const next = reconcileTree(t, ['a', 'b'])
    expect(extractChatIds(next)).toEqual(['a', 'b'])
  })

  it('preserves nested structure when it stays valid', () => {
    const t: PaneNode = {
      type: 'branch',
      direction: 'horizontal',
      ratios: [0.5, 0.5],
      children: [
        { type: 'chat', chatId: 'a' },
        {
          type: 'branch',
          direction: 'vertical',
          ratios: [0.5, 0.5],
          children: [
            { type: 'chat', chatId: 'b' },
            { type: 'chat', chatId: 'c' }
          ]
        }
      ]
    }
    const next = reconcileTree(t, ['a', 'b', 'c'])
    expect(next).toStrictEqual(t)
    expect(extractChatIds(next)).toEqual(['a', 'b', 'c'])
  })
})
