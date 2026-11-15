import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import {
  CHAT_CHUNK,
  CHAT_TAIL,
  markChatScrolledUp,
  nextChunkSize,
  useChatHistoryWindow
} from './useChatHistoryWindow'

const items = Array.from({ length: 100 }, (_, index) => `row-${index}`)
const scrollRef = { current: null }

function mount(sessionId: string, enabled = true) {
  return renderHook(
    (props: { sessionId: string; enabled: boolean }) =>
      useChatHistoryWindow({ items, scrollRef, ...props }),
    { initialProps: { sessionId, enabled } }
  )
}

describe('useChatHistoryWindow', () => {
  it('shows the newest rows first, then fills in the history', async () => {
    const { result } = mount('first-open')
    expect(result.current.shown).toEqual(items.slice(-CHAT_TAIL))
    await waitFor(() => expect(result.current.shown).toHaveLength(items.length))
    expect(result.current.shown).toEqual(items)
  })

  it('mounts a short chat whole', () => {
    const { result } = mount('short', false)
    expect(result.current.shown).toBe(items)
  })

  it('mounts whole when the chat was left scrolled up', () => {
    markChatScrolledUp('scrolled-up', true)
    expect(mount('scrolled-up').result.current.shown).toBe(items)
    markChatScrolledUp('scrolled-up', false)
    expect(mount('scrolled-up').result.current.shown).toHaveLength(CHAT_TAIL)
  })

  it('starts over from the newest rows when the chat changes', async () => {
    const { result, rerender } = mount('chat-a')
    await waitFor(() => expect(result.current.shown).toHaveLength(items.length))
    rerender({ sessionId: 'chat-b', enabled: true })
    expect(result.current.shown).toHaveLength(CHAT_TAIL)
  })

  it('mounts everything to jump to a turn that is not on screen yet', () => {
    const { result } = mount('jump')
    act(() => result.current.jumpToTurn('not-mounted'))
    expect(result.current.shown).toBe(items)
  })

  it('grows a chunk that rendered fast and shrinks one that was slow', () => {
    expect(nextChunkSize(CHAT_CHUNK, 2)).toBe(CHAT_CHUNK * 2)
    expect(nextChunkSize(CHAT_CHUNK, 20)).toBe(CHAT_CHUNK)
    expect(nextChunkSize(CHAT_CHUNK, 60)).toBe(CHAT_CHUNK / 2)
    expect(nextChunkSize(160, 1)).toBe(160)
    expect(nextChunkSize(10, 500)).toBe(10)
  })
})
