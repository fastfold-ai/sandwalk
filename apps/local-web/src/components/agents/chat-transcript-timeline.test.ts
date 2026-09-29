import { describe, expect, it } from 'vitest'

import {
  type ChatTimelineItem,
  reuseTimelineItems
} from './chat-transcript-timeline'

describe('reuseTimelineItems', () => {
  const entryA = { role: 'user', content: 'a' } as never
  const entryB = { role: 'assistant', content: 'b' } as never
  const toolX = { id: 'x', name: 'ls' } as never

  it('returns the previous array when nothing changed', () => {
    const prev: ChatTimelineItem[] = [
      { kind: 'entry', key: 'a', entry: entryA },
      { kind: 'tool_run', key: 't', tools: [toolX] }
    ]
    const next: ChatTimelineItem[] = [
      { kind: 'entry', key: 'a', entry: entryA },
      { kind: 'tool_run', key: 't', tools: [toolX] }
    ]
    expect(reuseTimelineItems(prev, next)).toBe(prev)
  })

  it('reuses unchanged items and keeps only the changed/new ones fresh', () => {
    const prev: ChatTimelineItem[] = [{ kind: 'entry', key: 'a', entry: entryA }]
    const next: ChatTimelineItem[] = [
      { kind: 'entry', key: 'a', entry: entryA },
      { kind: 'entry', key: 'b', entry: entryB }
    ]
    const merged = reuseTimelineItems(prev, next)
    expect(merged).not.toBe(prev)
    expect(merged[0]).toBe(prev[0])
    expect(merged[1]).toBe(next[1])
  })

  it('does not reuse when the entry object or tool list changed', () => {
    const prev: ChatTimelineItem[] = [
      { kind: 'entry', key: 'a', entry: entryA },
      { kind: 'tool_run', key: 't', tools: [toolX] }
    ]
    const next: ChatTimelineItem[] = [
      { kind: 'entry', key: 'a', entry: { ...(entryA as object) } as never },
      { kind: 'tool_run', key: 't', tools: [toolX, { id: 'y', name: 'cat' } as never] }
    ]
    const merged = reuseTimelineItems(prev, next)
    expect(merged[0]).toBe(next[0])
    expect(merged[1]).toBe(next[1])
  })

  it('treats a kind change under the same key as new', () => {
    const prev: ChatTimelineItem[] = [{ kind: 'entry', key: 'k', entry: entryA }]
    const next: ChatTimelineItem[] = [{ kind: 'tool_run', key: 'k', tools: [toolX] }]
    expect(reuseTimelineItems(prev, next)[0]).toBe(next[0])
  })
})
