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
import {
  DEFAULT_BACKEND_URL,
  normalizeBackendUrl,
  persistBackendUrl,
  pinDesktopBackendBind
} from '@/lib/backend-url'
import {
  clearRememberedApiKey,
  persistRememberedApiKey
} from '@/lib/remembered-auth'
import { resolveBackendApiKey } from '@/lib/resolve-backend-api-key'
import { cloudAccountDisplayName } from '@/lib/skills-catalog'

type UseAppBootstrapAuthArgs = {
  client: LocalAgentClient
  navigate: NavigateFunction
  location: Location
  health: BackendHealth | null
  setHealth: (value: BackendHealth | null) => void
  setBackendUrl: (value: string) => void
  setBackendApiKey: (value: string) => void
  setClientApiKey: (value: string | undefined) => void
  setRuntimeSettings: (value: RuntimeSettings | null) => void
  setError: (value: string | null) => void
  needsAuthLoginRef: MutableRefObject<boolean>
  setNeedsAuthLogin: (value: boolean) => void
  setAuthBootstrapped: (value: boolean) => void
  setConnectionPaused: (value: boolean) => void
}

export function useAppBootstrapAuth({
  client,
  navigate,
  location,
  health,
  setHealth,
  setBackendUrl,
  setBackendApiKey,
  setClientApiKey,
  setRuntimeSettings,
  setError,
  needsAuthLoginRef,
  setNeedsAuthLogin,
  setAuthBootstrapped,
  setConnectionPaused
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

  // Prefer a real name/username over a bare email in the sidebar footer.
  const sidebarUserName = (() => {
    const cloud = cloudUserName?.trim() || null
    const local = health?.userName?.trim() || null
    if (cloud && !cloud.includes('@')) return cloud
    if (local) return local
    return cloud
  })()

  const submitAuthLogin = useCallback(
    async (apiKey: string, remember: boolean) => {
      setAuthLoggingIn(true)
      setAuthLoginError(null)
      const key = apiKey.trim()
      try {
        await client.login(key, { remember })
        // Put the key on the next LocalAgentClient before leaving the login gate.
        // Cookie session from /auth/login often does not apply in the Tauri shell
        // (tauri:// origin → http://127.0.0.1), so Authorization must be set first.
        // Do not call connect() with the current (keyless) client — the connect
        // effect re-runs after clientApiKey + needsAuthLogin update.
        if (remember) {
          persistRememberedApiKey(client.baseUrl, key)
        } else {
          clearRememberedApiKey(client.baseUrl)
        }
        setClientApiKey(key)
        setBackendApiKey('')
        needsAuthLoginRef.current = false
        setNeedsAuthLogin(false)
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
      needsAuthLoginRef,
      setBackendApiKey,
      setClientApiKey,
      setNeedsAuthLogin
    ]
  )

  const clearBackendSession = useCallback(
    (options?: { clearRemembered?: boolean }) => {
      needsAuthLoginRef.current = false
      setNeedsAuthLogin(false)
      setAuthLoginError(null)
      setHealth(null)
      setError(null)
      setAuthBootstrapped(true)
      setBackendApiKey('')
      setClientApiKey(undefined)
      // Never wipe remembered keys on Change server / Connect locally — only on
      // explicit logout or disconnect. Cookie sessions do not stick in Tauri.
      if (options?.clearRemembered) {
        clearRememberedApiKey(client.baseUrl)
      }
      setRuntimeSettings(null)
      setCloudUserName(null)
    },
    [
      client.baseUrl,
      needsAuthLoginRef,
      setAuthBootstrapped,
      setBackendApiKey,
      setClientApiKey,
      setError,
      setHealth,
      setNeedsAuthLogin,
      setRuntimeSettings
    ]
  )

  /** Drop the current backend session and show the connect gate again. */
  const disconnectBackend = useCallback(async () => {
    setConnectionPaused(true)
    clearBackendSession({ clearRemembered: true })
    if (location.pathname !== '/' || location.search) {
      navigate('/', { replace: true })
    }
    try {
      await client.logout()
    } catch {
      // Best-effort; UI already returned to the connect gate.
    }
  }, [
    clearBackendSession,
    client,
    location.pathname,
    location.search,
    navigate,
    setConnectionPaused
  ])

  /**
   * Switch agent API URL (and optional key), clear session state, and reconnect.
   * Pass an empty string to reset to the local default.
   */
  const changeBackend = useCallback(
    async (nextUrl: string, nextApiKey?: string) => {
      const normalized = normalizeBackendUrl(nextUrl || DEFAULT_BACKEND_URL)
      const key =
        (await resolveBackendApiKey(normalized, nextApiKey)) || undefined
      pinDesktopBackendBind(normalized, key || null)
      persistBackendUrl(normalized)
      setConnectionPaused(false)
      clearBackendSession()
      setBackendUrl(normalized)
      // Prefer Authorization header (clientApiKey); cookies do not stick in Tauri.
      setClientApiKey(key)
      setBackendApiKey('')
      if (key) persistRememberedApiKey(normalized, key)
      if (location.pathname !== '/' || location.search) {
        navigate('/', { replace: true })
      }
      try {
        await client.logout()
      } catch {
        // Best-effort against the previous host.
      }
      try {
        const { bindDesktopWindowBackend, isTauri } = await import(
          '@/lib/desktop'
        )
        if (isTauri()) {
          await bindDesktopWindowBackend(normalized)
        }
      } catch {
        // Browser / bridge unavailable.
      }
      // connect() re-runs via useEffect when client/backendUrl identity updates.
    },
    [
      clearBackendSession,
      client,
      location.pathname,
      location.search,
      navigate,
      setBackendApiKey,
      setBackendUrl,
      setClientApiKey,
      setConnectionPaused
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
    clearRememberedApiKey(client.baseUrl)
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
    logoutSession,
    disconnectBackend,
    changeBackend
  }
}
