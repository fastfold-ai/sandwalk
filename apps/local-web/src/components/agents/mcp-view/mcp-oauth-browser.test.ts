import { beforeEach, describe, expect, it, vi } from 'vitest'

import { isTauri, openInSystemBrowser } from '@/lib/desktop'

import { openMcpOAuthBrowser } from './mcp-oauth-browser'

vi.mock('@/lib/desktop', () => ({
  isTauri: vi.fn(),
  openInSystemBrowser: vi.fn()
}))

describe('openMcpOAuthBrowser', () => {
  beforeEach(() => {
    vi.mocked(isTauri).mockReset()
    vi.mocked(openInSystemBrowser).mockReset()
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

  it('refreshes Tauri state when the user returns from OAuth', async () => {
    vi.useFakeTimers()
    vi.mocked(isTauri).mockReturnValue(true)
    const onReturn = vi.fn()

    await openMcpOAuthBrowser('https://example.com/oauth', onReturn)
    window.dispatchEvent(new Event('focus'))
    await vi.advanceTimersByTimeAsync(500)

    expect(onReturn).toHaveBeenCalledOnce()
    vi.useRealTimers()
  })

  it('keeps a named popup in the web app', async () => {
    vi.mocked(isTauri).mockReturnValue(false)
    const popup = vi.spyOn(window, 'open').mockReturnValue({} as Window)

    await openMcpOAuthBrowser('https://example.com/oauth')

    expect(popup).toHaveBeenCalledWith(
      'https://example.com/oauth',
      'fastfold-mcp-oauth',
      'width=560,height=720'
    )
    expect(openInSystemBrowser).not.toHaveBeenCalled()
    popup.mockRestore()
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
