import type { PaneNode } from '@sandwalk/agent-ui-core'
import { describe, expect, it } from 'vitest'

import {
  buildDefaultTree,
  buildDefaultTreeFromRefs,
  buildGridTree,
  closePane,
  extractChatIds,
  extractItemRefs,
  leafItemId,
  leafItemRef,
  reconcileTree,
  reconcileTreeFromRefs,
  setBranchRatios,
  splitPane,
  splitPaneWithRef
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

describe('buildGridTree', () => {
  const ids = ['a', 'b', 'c', 'd', 'e', 'f']

  it('lays ids out row-major as a vertical branch of horizontal rows', () => {
    const tree = buildGridTree(ids, 2, 3)
    expect(tree.type).toBe('branch')
    if (tree.type !== 'branch') return
    expect(tree.direction).toBe('vertical')
    expect(tree.children).toHaveLength(2)
    const [top, bottom] = tree.children
    expect(top.type === 'branch' && top.direction).toBe('horizontal')
    expect(extractChatIds(top)).toEqual(['a', 'b', 'c'])
    expect(extractChatIds(bottom)).toEqual(['d', 'e', 'f'])
    expect(extractChatIds(tree)).toEqual(ids)
  })

  it('spills extra ids into more rows and keeps a short last row', () => {
    const tree = buildGridTree(['a', 'b', 'c', 'd', 'e'], 2, 2)
    expect(tree.type === 'branch' && tree.children).toHaveLength(3)
    if (tree.type !== 'branch') return
    const last = tree.children[2]
    expect(last.type).toBe('chat') // single leaf, no wrapper branch
    expect(extractChatIds(tree)).toEqual(['a', 'b', 'c', 'd', 'e'])
  })

  it('collapses to a single row when everything fits in one', () => {
    const tree = buildGridTree(['a', 'b'], 1, 4)
    expect(tree.type === 'branch' && tree.direction).toBe('horizontal')
    expect(extractChatIds(tree)).toEqual(['a', 'b'])
  })

  it('falls back to the default tree for degenerate input', () => {
    expect(buildGridTree(['a'], 4, 4)).toEqual(buildDefaultTree(['a']))
    expect(buildGridTree(ids, 0, 4)).toEqual(buildDefaultTree(ids))
  })
})

describe('split and close mixed panes', () => {
  it('inserts a terminal beside a chat and ignores a missing target', () => {
    const tree = buildDefaultTree(['a'])
    const split = splitPane(tree, 'a', 'horizontal', 'term_1', 'before')
    expect(extractItemRefs(split).map(ref => ref.kind)).toEqual([
      'terminal',
      'chat'
    ])
    expect(splitPane(tree, 'missing', 'vertical', 'b')).toEqual(tree)
    expect(leafItemId(tree)).toBe('a')
  })

  it('inserts a sibling in the same direction and wraps a perpendicular split', () => {
    const row = splitPane(buildDefaultTree(['a']), 'a', 'horizontal', 'b')
    const wider = splitPane(row, 'a', 'horizontal', 'c', 'before')
    expect(extractChatIds(wider)).toEqual(['c', 'a', 'b'])
    const wrapped = splitPaneWithRef(row, 'b', 'vertical', {
      kind: 'terminal',
      id: 'term_2'
    })
    expect(wrapped.type).toBe('branch')
    const closed = closePane(wider, 'a')
    expect(extractChatIds(closed!)).toEqual(['c', 'b'])
    expect(closePane(buildDefaultTree(['a']), 'a')).toBeNull()
    expect(closePane(buildDefaultTree(['a']), 'nope')).toEqual(
      buildDefaultTree(['a'])
    )
  })

  it('renormalizes dragged ratios and reconciles terminals', () => {
    const tree = buildDefaultTree(['a', 'b'])
    const resized = setBranchRatios(tree, [], [1, 3])
    expect(resized.type === 'branch' && resized.ratios).toEqual([0.25, 0.75])
    expect(setBranchRatios(tree, [], [1])).toEqual(tree)
    expect(setBranchRatios(buildDefaultTree(['a']), [0], [1, 1])).toEqual(
      buildDefaultTree(['a'])
    )
    const withTerm = reconcileTree(buildDefaultTree(['a']), ['a', 'term_9'])
    expect(extractItemRefs(withTerm).map(ref => ref.id)).toContain('term_9')
    const refs = [
      { kind: 'chat' as const, id: 'a' },
      { kind: 'terminal' as const, id: 'term_1' }
    ]
    expect(extractItemRefs(reconcileTreeFromRefs(buildDefaultTree(['gone']), refs))).toEqual(
      refs
    )
    expect(buildDefaultTreeFromRefs([])).toEqual({ type: 'chat', chatId: '' })
  })

  it('appends onto a vertical root and ignores an empty chat id', () => {
    expect(leafItemRef({ type: 'chat', chatId: '' })).toBeNull()
    const vertical: PaneNode = {
      type: 'branch',
      direction: 'vertical',
      ratios: [1],
      children: [{ type: 'chat', chatId: 'a' }]
    }
    const next = reconcileTreeFromRefs(vertical, [
      { kind: 'chat', id: 'a' },
      { kind: 'terminal', id: 'term_3' }
    ])
    expect(extractItemRefs(next).map(ref => ref.id)).toEqual(['a', 'term_3'])
    const nested = splitPane(
      splitPane(buildDefaultTree(['a', 'b']), 'b', 'vertical', 'c'),
      'c',
      'horizontal',
      'd'
    )
    expect(extractChatIds(nested)).toContain('d')
    expect(setBranchRatios(buildDefaultTree(['a', 'b']), [0], [1]).type).toBe(
      'branch'
    )
  })
})
