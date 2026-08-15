import type { NavigateFunction } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { navigateToSession } from './navigate-session'

describe('navigateToSession', () => {
  it('opens the tab, prefetches messages, and navigates for a chat id', async () => {
    const openSessionTab = vi.fn()
    const prefetch = vi.fn(() => Promise.resolve())
    const navigate = vi.fn() as unknown as NavigateFunction
    await navigateToSession({
      id: 'chat-1',
      openSessionTab,
      prefetchSessionMessages: prefetch,
      navigate
    })
    expect(openSessionTab).toHaveBeenCalledWith('chat-1')
    expect(prefetch).toHaveBeenCalledWith('chat-1')
    expect(navigate).toHaveBeenCalledWith('/agents/chat-1')
  })

  it('skips prefetch for group ids (they have no /messages endpoint)', async () => {
    const openSessionTab = vi.fn()
    const prefetch = vi.fn()
    const navigate = vi.fn() as unknown as NavigateFunction
    await navigateToSession({
      id: 'grp_abc',
      openSessionTab,
      prefetchSessionMessages: prefetch,
      navigate
    })
    expect(openSessionTab).toHaveBeenCalledWith('grp_abc')
    expect(prefetch).not.toHaveBeenCalled()
    expect(navigate).toHaveBeenCalledWith('/agents/grp_abc')
  })

  it('proceeds when prefetch resolves after the 150ms budget', async () => {
    const openSessionTab = vi.fn()
    const prefetch = vi.fn(
      () => new Promise<void>(resolve => setTimeout(resolve, 250))
    )
    const navigate = vi.fn() as unknown as NavigateFunction
    const start = Date.now()
    await navigateToSession({
      id: 'chat-2',
      openSessionTab,
      prefetchSessionMessages: prefetch,
      navigate
    })
    const elapsed = Date.now() - start
    expect(navigate).toHaveBeenCalledWith('/agents/chat-2')
    // Budget is 150ms; the race should resolve well before the slow prefetch.
    expect(elapsed).toBeLessThan(230)
  })
})
