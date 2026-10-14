import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { ChatGPTAuthStatus } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useRef, useState } from 'react'

import { openInSystemBrowser } from '@/lib/desktop'

/** How often to ask the API whether the browser sign-in finished. */
const POLL_MS = 1500
/** Stop polling after this long; the server-side listener also times out. */
const POLL_LIMIT_MS = 10 * 60 * 1000

const EMPTY: ChatGPTAuthStatus = {
  connected: false,
  email: null,
  planUsage: false,
  expiresAt: null
}

export type ChatGPTAuthPhase = 'idle' | 'loading' | 'waiting' | 'disconnecting'

/**
 * Drives Sign in with ChatGPT end to end: start → system browser → poll until
 * the loopback callback lands → connected. Shared by Models and onboarding.
 */
export function useChatGPTAuth(
  client: LocalAgentClient,
  options?: { onConnected?: (status: ChatGPTAuthStatus) => void | Promise<void> }
) {
  const [status, setStatus] = useState<ChatGPTAuthStatus>(EMPTY)
  const [phase, setPhase] = useState<ChatGPTAuthPhase>('loading')
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<number | null>(null)
  const onConnectedRef = useRef(options?.onConnected)
  onConnectedRef.current = options?.onConnected

  const stopPolling = useCallback(() => {
    if (pollRef.current != null) {
      window.clearTimeout(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const refresh = useCallback(async () => {
    try {
      const next = await client.getChatGPTAuthStatus()
      setStatus(next)
      return next
    } catch {
      return null
    }
  }, [client])

  useEffect(() => {
    let cancelled = false
    void refresh().finally(() => {
      if (!cancelled) setPhase(current => (current === 'loading' ? 'idle' : current))
    })
    return () => {
      cancelled = true
      stopPolling()
    }
  }, [refresh, stopPolling])

  const signIn = useCallback(async () => {
    setError(null)
    setPhase('waiting')
    let state: string
    try {
      const started = await client.startChatGPTLogin()
      state = started.state
      await openInSystemBrowser(started.url)
    } catch (err) {
      setPhase('idle')
      setError(err instanceof Error ? err.message : 'Could not start ChatGPT sign-in.')
      return
    }

    const startedAt = Date.now()
    const tick = async () => {
      try {
        const next = await client.getChatGPTAuthStatus({ state })
        if (next.connected) {
          stopPolling()
          setStatus(next)
          setPhase('idle')
          await onConnectedRef.current?.(next)
          return
        }
      } catch (err) {
        // The server reports a failed attempt as a 4xx with the reason.
        stopPolling()
        setPhase('idle')
        setError(err instanceof Error ? err.message : 'ChatGPT sign-in failed.')
        return
      }
      if (Date.now() - startedAt > POLL_LIMIT_MS) {
        stopPolling()
        setPhase('idle')
        setError('Sign-in timed out. Try again.')
        return
      }
      pollRef.current = window.setTimeout(() => void tick(), POLL_MS)
    }
    pollRef.current = window.setTimeout(() => void tick(), POLL_MS)
  }, [client, stopPolling])

  const cancel = useCallback(() => {
    stopPolling()
    setPhase('idle')
  }, [stopPolling])

  const disconnect = useCallback(async () => {
    setError(null)
    setPhase('disconnecting')
    try {
      const next = await client.logoutChatGPT()
      setStatus(next)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not disconnect ChatGPT.')
    } finally {
      setPhase('idle')
    }
  }, [client])

  return { status, phase, error, signIn, cancel, disconnect, refresh }
}
