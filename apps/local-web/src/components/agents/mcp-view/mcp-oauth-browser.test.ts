import { beforeEach, describe, expect, it, vi } from 'vitest'

import { isTauri, openInSystemBrowser } from '@/lib/desktop'

import {
  disposeMcpOAuthWatch,
  openMcpOAuthBrowser
} from './mcp-oauth-browser'

vi.mock('@/lib/desktop', () => ({
  isTauri: vi.fn(),
  openInSystemBrowser: vi.fn()
}))

describe('openMcpOAuthBrowser', () => {
  beforeEach(() => {
    vi.mocked(isTauri).mockReset()
    vi.mocked(openInSystemBrowser).mockReset()
    disposeMcpOAuthWatch()
  })

  it('opens OAuth in the system browser from Tauri', async () => {
    vi.mocked(isTauri).mockReturnValue(true)
    const popup = vi.spyOn(window, 'open')

    await openMcpOAuthBrowser('https://example.com/oauth')

    expect(openInSystemBrowser).toHaveBeenCalledWith(
      'https://example.com/oauth'
    )
    expect(popup).not.toHaveBeenCalled()
    popup.mockRestore()
  })

  it('keeps polling after early focus so late OAuth completion refreshes', async () => {
    vi.useFakeTimers()
    vi.mocked(isTauri).mockReturnValue(true)
    const onReturn = vi.fn()

    const watch = await openMcpOAuthBrowser(
      'https://example.com/oauth',
      onReturn
    )
    // Immediate tick + first focus.
    expect(onReturn).toHaveBeenCalledTimes(1)
    window.dispatchEvent(new Event('focus'))
    await vi.advanceTimersByTimeAsync(400)
    expect(onReturn).toHaveBeenCalledTimes(2)

    // Previous bug: listener was one-shot. Second focus + interval must still run.
    window.dispatchEvent(new Event('focus'))
    await vi.advanceTimersByTimeAsync(400)
    expect(onReturn).toHaveBeenCalledTimes(3)

    await vi.advanceTimersByTimeAsync(2000)
    expect(onReturn.mock.calls.length).toBeGreaterThanOrEqual(4)

    watch.dispose()
    const calls = onReturn.mock.calls.length
    await vi.advanceTimersByTimeAsync(5000)
    expect(onReturn).toHaveBeenCalledTimes(calls)
    vi.useRealTimers()
  })

  it('stops watching when disposeMcpOAuthWatch is called', async () => {
    vi.useFakeTimers()
    vi.mocked(isTauri).mockReturnValue(true)
    const onReturn = vi.fn()

    await openMcpOAuthBrowser('https://example.com/oauth', onReturn)
    expect(onReturn).toHaveBeenCalledTimes(1)
    disposeMcpOAuthWatch()
    await vi.advanceTimersByTimeAsync(5000)
    expect(onReturn).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
  })

  it('stops watching when onReturn reports done', async () => {
    vi.useFakeTimers()
    vi.mocked(isTauri).mockReturnValue(true)
    const onReturn = vi
      .fn()
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true)

    await openMcpOAuthBrowser('https://example.com/oauth', onReturn)
    expect(onReturn).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(2000)
    expect(onReturn).toHaveBeenCalledTimes(2)

    await vi.advanceTimersByTimeAsync(5000)
    expect(onReturn).toHaveBeenCalledTimes(2)
    vi.useRealTimers()
  })

  it('keeps a named popup in the web app and still watches for return', async () => {
    vi.useFakeTimers()
    vi.mocked(isTauri).mockReturnValue(false)
    const popup = vi.spyOn(window, 'open').mockReturnValue({} as Window)
    const onReturn = vi.fn()

    const watch = await openMcpOAuthBrowser(
      'https://example.com/oauth',
      onReturn
    )

    expect(popup).toHaveBeenCalledWith(
      'https://example.com/oauth',
      'fastfold-mcp-oauth',
      'width=560,height=720'
    )
    expect(openInSystemBrowser).not.toHaveBeenCalled()
    expect(onReturn).toHaveBeenCalledTimes(1)
    watch.dispose()
    popup.mockRestore()
    vi.useRealTimers()
  })

  it('reports blocked web popups', async () => {
    vi.mocked(isTauri).mockReturnValue(false)
    const popup = vi.spyOn(window, 'open').mockReturnValue(null)

    await expect(
      openMcpOAuthBrowser('https://example.com/oauth')
    ).rejects.toThrow('blocked the OAuth popup')
    popup.mockRestore()
  })
})
