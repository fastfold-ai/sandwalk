import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { BackendHealth, RuntimeSettings } from '@sandwalk/agent-ui-core'
import type { MutableRefObject } from 'react'
import { useCallback, useEffect, useState } from 'react'
import type { Location, NavigateFunction } from 'react-router-dom'
import { toast } from 'sonner'

import {
  isAuthCredentialError,
  isBackendUnavailableError,
  normalizeAppError
} from '@/lib/app-error'
import { cloudAccountDisplayName } from '@/lib/skills-catalog'

type UseAppBootstrapAuthArgs = {
  client: LocalAgentClient
  navigate: NavigateFunction
  location: Location
  health: BackendHealth | null
  setHealth: (value: BackendHealth | null) => void
  setBackendApiKey: (value: string) => void
  setClientApiKey: (value: string | undefined) => void
  setRuntimeSettings: (value: RuntimeSettings | null) => void
  needsAuthLoginRef: MutableRefObject<boolean>
  setNeedsAuthLogin: (value: boolean) => void
  setAuthBootstrapped: (value: boolean) => void
  connectRef: MutableRefObject<(() => Promise<void>) | null>
}

export function useAppBootstrapAuth({
  client,
  navigate,
  location,
  health,
  setHealth,
  setBackendApiKey,
  setClientApiKey,
  setRuntimeSettings,
  needsAuthLoginRef,
  setNeedsAuthLogin,
  setAuthBootstrapped,
  connectRef
}: UseAppBootstrapAuthArgs) {
  const [cloudUserName, setCloudUserName] = useState<string | null>(null)
  const [authLoggingIn, setAuthLoggingIn] = useState(false)
  const [authLoginError, setAuthLoginError] = useState<unknown>(null)

  const loadAccount = useCallback(
    (options?: { checkUpdates?: boolean; signal?: AbortSignal }) =>
      client.getAccount(options),
    [client]
  )

  const refreshCloudUserName = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const account = await loadAccount({ signal })
        if (signal?.aborted) return
        setCloudUserName(cloudAccountDisplayName(account))
      } catch {
        if (!signal?.aborted) setCloudUserName(null)
      }
    },
    [loadAccount]
  )

  const loadAccountForUi = useCallback(
    async (options?: { checkUpdates?: boolean; signal?: AbortSignal }) => {
      const account = await loadAccount(options)
      if (!options?.signal?.aborted) {
        setCloudUserName(cloudAccountDisplayName(account))
      }
      return account
    },
    [loadAccount]
  )

  const logoutAccount = useCallback(
    async (signal?: AbortSignal) => {
      const account = await client.logoutAccount(signal)
      if (!signal?.aborted) {
        setCloudUserName(cloudAccountDisplayName(account))
      }
      return account
    },
    [client]
  )

  useEffect(() => {
    if (!health) {
      setCloudUserName(null)
      return
    }
    const controller = new AbortController()
    void refreshCloudUserName(controller.signal)
    return () => controller.abort()
  }, [health, refreshCloudUserName])

  const sidebarUserName =
    cloudUserName?.trim() || health?.userName?.trim() || null

  const submitAuthLogin = useCallback(
    async (apiKey: string, remember: boolean) => {
      setAuthLoggingIn(true)
      setAuthLoginError(null)
      try {
        await client.login(apiKey, { remember })
        setClientApiKey(apiKey.trim())
        setBackendApiKey('')
        needsAuthLoginRef.current = false
        const connect = connectRef.current
        if (connect) await connect()
      } catch (cause) {
        needsAuthLoginRef.current = true
        setNeedsAuthLogin(true)
        if (isBackendUnavailableError(cause) || !isAuthCredentialError(cause)) {
          setAuthLoginError(cause)
          const info = normalizeAppError(cause)
          toast.error(info.title)
        } else {
          const raw = cause instanceof Error ? cause.message : 'Invalid API key'
          let message = 'Invalid API key'
          try {
            const jsonMatch = raw.match(/\{.*\}/s)
            if (jsonMatch) {
              const parsed = JSON.parse(jsonMatch[0]) as { detail?: string }
              if (parsed.detail) message = parsed.detail
            } else if (/invalid api key/i.test(raw)) {
              message = 'Invalid API key'
            } else if (raw && !raw.startsWith('FastFold Agent API')) {
              message = raw
            }
          } catch {
            // keep friendly default
          }
          toast.error(message)
        }
      } finally {
        setAuthLoggingIn(false)
      }
    },
    [
      client,
      connectRef,
      needsAuthLoginRef,
      setBackendApiKey,
      setClientApiKey,
      setNeedsAuthLogin
    ]
  )

  const logoutSession = useCallback(async () => {
    needsAuthLoginRef.current = true
    setNeedsAuthLogin(true)
    setAuthLoginError(null)
    setHealth(null)
    setAuthBootstrapped(true)
    setBackendApiKey('')
    setClientApiKey(undefined)
    setRuntimeSettings(null)
    if (location.pathname !== '/' || location.search) {
      navigate('/', { replace: true })
    }
    try {
      await client.logout()
    } catch {
      // Cookie clear may have failed; UI is already on login.
    }
  }, [
    client,
    location.pathname,
    location.search,
    navigate,
    needsAuthLoginRef,
    setAuthBootstrapped,
    setBackendApiKey,
    setClientApiKey,
    setHealth,
    setNeedsAuthLogin,
    setRuntimeSettings
  ])

  return {
    cloudUserName,
    authLoggingIn,
    authLoginError,
    setAuthLoginError,
    sidebarUserName,
    loadAccount,
    loadAccountForUi,
    logoutAccount,
    refreshCloudUserName,
    submitAuthLogin,
    logoutSession
  }
}
