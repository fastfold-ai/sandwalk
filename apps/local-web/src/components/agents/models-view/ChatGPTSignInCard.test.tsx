import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/desktop', () => ({
  openInSystemBrowser: vi.fn(async () => undefined)
}))

import { ChatGPTSignInCard } from './ChatGPTSignInCard'

function client(connected: boolean) {
  return {
    getChatGPTAuthStatus: vi.fn(async () => ({
      connected,
      email: connected ? 'user@example.com' : null,
      planUsage: connected,
      expiresAt: connected ? 1 : null
    })),
    startChatGPTLogin: vi.fn(),
    logoutChatGPT: vi.fn()
  } as unknown as LocalAgentClient
}

describe('ChatGPTSignInCard', () => {
  afterEach(() => cleanup())

  it('shows a quiet Checking… state before the first status resolves', () => {
    render(<ChatGPTSignInCard client={client(true)} />)
    // Synchronously, before the fetch settles, there must be no sign-in CTA.
    expect(screen.queryByRole('button', { name: /continue with chatgpt/i })).toBeNull()
    expect(screen.getByText(/checking/i)).toBeTruthy()
  })

  it('offers Continue with ChatGPT when disconnected', async () => {
    render(<ChatGPTSignInCard client={client(false)} />)
    const button = (await screen.findByRole('button', {
      name: /continue with chatgpt/i
    })) as HTMLButtonElement
    expect(button.disabled).toBe(false)
    expect(screen.queryByText(/5-hour usage window/i)).toBeNull()
    expect(screen.queryByText(/^connected$/i)).toBeNull()
  })

  it('shows the account and a Disconnect button when connected', async () => {
    render(<ChatGPTSignInCard client={client(true)} />)
    await waitFor(() => expect(screen.getByText('Connected')).toBeTruthy())
    expect(screen.getByText('user@example.com')).toBeTruthy()
    const disconnect = screen.getByRole('button', {
      name: /disconnect/i
    }) as HTMLButtonElement
    expect(disconnect.disabled).toBe(false)
    expect(screen.queryByRole('button', { name: /continue with chatgpt/i })).toBeNull()
  })
})
