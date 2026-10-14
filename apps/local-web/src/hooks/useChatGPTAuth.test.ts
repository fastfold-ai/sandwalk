import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { ChatGPTAuthStatus } from '@sandwalk/agent-ui-core'
import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const openInSystemBrowser = vi.fn(async () => undefined)
vi.mock('@/lib/desktop', () => ({
  openInSystemBrowser: (...args: unknown[]) => openInSystemBrowser(...args)
}))

import { useChatGPTAuth } from './useChatGPTAuth'

const disconnected: ChatGPTAuthStatus = {
  connected: false,
  email: null,
  planUsage: false,
  expiresAt: null
}
const connected: ChatGPTAuthStatus = {
  connected: true,
  email: 'user@example.com',
  planUsage: true,
  expiresAt: 1
}

function fakeClient(overrides: Partial<LocalAgentClient> = {}) {
  return {
    getChatGPTAuthStatus: vi.fn(async () => disconnected),
    startChatGPTLogin: vi.fn(async () => ({
      url: 'https://auth.openai.com/api/accounts/authorize?x=1',
      state: 'st-1'
    })),
    logoutChatGPT: vi.fn(async () => disconnected),
    ...overrides
  } as unknown as LocalAgentClient
}

/** Flush the mount-time status fetch without fake timers interfering. */
async function mount(client: LocalAgentClient, options?: Parameters<typeof useChatGPTAuth>[1]) {
  const rendered = renderHook(() => useChatGPTAuth(client, options))
  await act(async () => {
    await Promise.resolve()
  })
  return rendered
}

describe('useChatGPTAuth', () => {
  afterEach(() => {
    vi.useRealTimers()
    openInSystemBrowser.mockClear()
  })

  it('loads the current status on mount', async () => {
    const client = fakeClient({
      getChatGPTAuthStatus: vi.fn(async () => connected)
    } as Partial<LocalAgentClient>)
    const { result } = await mount(client)
    expect(result.current.phase).toBe('idle')
    expect(result.current.status.connected).toBe(true)
    expect(result.current.status.email).toBe('user@example.com')
  })

  it('signIn opens the browser and polls with the state until connected', async () => {
    const statuses = [disconnected, disconnected, connected]
    const getStatus = vi.fn(async (opts?: { state?: string }) => {
      if (!opts?.state) return disconnected
      return statuses.shift() ?? connected
    })
    const onConnected = vi.fn()
    const client = fakeClient({ getChatGPTAuthStatus: getStatus } as Partial<LocalAgentClient>)
    const { result } = await mount(client, { onConnected })

    vi.useFakeTimers()
    await act(async () => {
      await result.current.signIn()
    })
    expect(result.current.phase).toBe('waiting')
    expect(openInSystemBrowser).toHaveBeenCalledWith(
      'https://auth.openai.com/api/accounts/authorize?x=1'
    )

    // Two "not yet" polls, then connected.
    for (let i = 0; i < 3; i += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500)
      })
    }
    expect(result.current.status.connected).toBe(true)
    expect(result.current.phase).toBe('idle')
    expect(onConnected).toHaveBeenCalledTimes(1)
    expect(getStatus).toHaveBeenCalledWith({ state: 'st-1' })
  })

  it('surfaces a server-reported failure and stops polling', async () => {
    const getStatus = vi.fn(async (opts?: { state?: string }) => {
      if (!opts?.state) return disconnected
      throw new Error('You did not allow Sandwalk to use your ChatGPT plan.')
    })
    const client = fakeClient({ getChatGPTAuthStatus: getStatus } as Partial<LocalAgentClient>)
    const { result } = await mount(client)

    vi.useFakeTimers()
    await act(async () => {
      await result.current.signIn()
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })
    expect(result.current.phase).toBe('idle')
    expect(result.current.error).toMatch(/did not allow/)
    const callsAfterError = getStatus.mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(getStatus.mock.calls.length).toBe(callsAfterError)
  })

  it('disconnect calls logout and reflects the new status', async () => {
    const client = fakeClient({
      getChatGPTAuthStatus: vi.fn(async () => connected)
    } as Partial<LocalAgentClient>)
    const { result } = await mount(client)
    expect(result.current.status.connected).toBe(true)
    await act(async () => {
      await result.current.disconnect()
    })
    expect(client.logoutChatGPT).toHaveBeenCalled()
    expect(result.current.status.connected).toBe(false)
    expect(result.current.phase).toBe('idle')
  })
})
