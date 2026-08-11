import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  BackendHealth,
  RuntimeSettings,
  SandboxSettings
} from '@sandwalk/agent-ui-core'
import type { MutableRefObject } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Location, NavigateFunction } from 'react-router-dom'

import {
  isAuthCredentialError,
  isBackendUnavailableError
} from '@/lib/app-error'
import {
  loginPathWithNext,
  nextFromSearch,
  sanitizeAuthReturnTo
} from '@/lib/auth-routing'
import { isLocalBackendUrl, persistBackendUrl } from '@/lib/backend-url'
import { dedupeAsync } from '@/lib/dedupe-async'
import {
  clampOnboardingStep,
  isOnboardingPath,
  onboardingPath
} from '@/lib/onboarding'
import { clearRememberedApiKey } from '@/lib/remembered-auth'

import type { useAppBootstrapLoaders } from './useAppBootstrapLoaders'

type LoaderBundle = ReturnType<typeof useAppBootstrapLoaders>

/** Revision poll cadence. Full /sessions only runs when the watermark moves.
 * Keep this snappy so background runs (no per-session SSE) still update
 * sidebar status / awaiting_approval without flooding the API. */
const SESSION_LIST_REFRESH_MS = 2_000

type UseAppBootstrapConnectArgs = {
  client: LocalAgentClient
  backendUrl: string
  navigate: NavigateFunction
  location: Location
  isDashboardModels: boolean
  loaders: LoaderBundle
  connectRef: MutableRefObject<(() => Promise<void>) | null>
  setClientApiKey: (value: string | undefined) => void
}

export function useAppBootstrapConnect({
  client,
  backendUrl,
  navigate,
  location,
  isDashboardModels,
  loaders,
  connectRef,
  setClientApiKey
}: UseAppBootstrapConnectArgs) {
  const [health, setHealth] = useState<BackendHealth | null>(null)
  const [needsAuthLogin, setNeedsAuthLogin] = useState(false)
  const needsAuthLoginRef = useRef(false)
  const [authBootstrapped, setAuthBootstrapped] = useState(false)
  const [connecting, setConnecting] = useState(false)
  /** User chose Disconnect — stay on the connect gate until Connect/Retry. */
  const [connectionPaused, setConnectionPaused] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorStack, setErrorStack] = useState<string | null>(null)
  const onboardingAutoOpenedRef = useRef(false)
  const locationRef = useRef(location)
  locationRef.current = location

  const {
    loadSessions,
    loadProjects,
    loadSkills,
    loadIntegrations,
    loadMcpServers,
    loadMcpCatalog,
    loadSpecialists,
    loadModelOptions,
    setRuntimeSettings,
    setSandboxSettings
  } = loaders

  const connect = useCallback(async () => {
    setConnectionPaused(false)
    setConnecting(true)
    setError(null)
    setErrorStack(null)
    const loc = locationRef.current
    const scope = backendUrl

    const goToLogin = () => {
      const alreadyNext = nextFromSearch(loc.search)
      const deepLink =
        loc.pathname === '/'
          ? null
          : sanitizeAuthReturnTo(`${loc.pathname}${loc.search}${loc.hash}`)
      // Drop a stale remembered key so we don't immediately re-fail auth.
      if (client.apiKey) {
        clearRememberedApiKey(backendUrl)
        setClientApiKey(undefined)
      }
      needsAuthLoginRef.current = true
      setHealth(null)
      setNeedsAuthLogin(true)
      const target = loginPathWithNext(alreadyNext || deepLink)
      if (`${loc.pathname}${loc.search}` !== target) {
        navigate(target, { replace: true })
      }
    }

    try {
      if (needsAuthLoginRef.current) {
        return
      }
      const nextHealth = await dedupeAsync(`health:${scope}`, () =>
        client.health()
      )
      if (needsAuthLoginRef.current) return
      persistBackendUrl(backendUrl)
      try {
        const { isTauri, rememberDesktopWindowRecent } = await import(
          '@/lib/desktop'
        )
        if (isTauri()) {
          await rememberDesktopWindowRecent(backendUrl)
        }
      } catch {
        // Browser / bridge unavailable.
      }

      let authEnabled = false
      let authenticated: boolean | null = null
      try {
        const status = await dedupeAsync(`auth-status:${scope}`, () =>
          client.authStatus()
        )
        authEnabled = Boolean(status.authEnabled)
        authenticated =
          typeof status.authenticated === 'boolean'
            ? status.authenticated
            : null
      } catch {
        authEnabled = false
        authenticated = null
      }
      if (needsAuthLoginRef.current) return

      if (authEnabled) {
        if (authenticated === false) {
          goToLogin()
          return
        }
        if (authenticated === null) {
          try {
            await dedupeAsync(`runtime:${scope}`, () =>
              client.getRuntimeSettings()
            )
          } catch (cause) {
            if (isAuthCredentialError(cause)) {
              goToLogin()
              return
            }
            throw cause
          }
        }
      }
      if (needsAuthLoginRef.current) return

      needsAuthLoginRef.current = false
      setNeedsAuthLogin(false)
      setHealth(nextHealth)
      const [, , , , , , , settings, sandbox] = await Promise.all([
        loadSessions({ force: true }),
        loadProjects(),
        loadSkills(),
        loadIntegrations(),
        loadMcpServers(),
        loadMcpCatalog(),
        loadSpecialists(),
        dedupeAsync(`runtime:${scope}`, () => client.getRuntimeSettings()),
        dedupeAsync(`sandbox:${scope}`, () =>
          client.getSandboxSettings().catch(() => null)
        ),
        loadModelOptions()
      ])
      if (needsAuthLoginRef.current) return
      setRuntimeSettings(settings as RuntimeSettings)
      setSandboxSettings(sandbox as SandboxSettings | null)
      try {
        const onboarding = await dedupeAsync(`onboarding:${scope}`, () =>
          client.getOnboardingSettings()
        )
        const step = clampOnboardingStep(onboarding.step)
        if (!onboarding.completed && !onboardingAutoOpenedRef.current) {
          onboardingAutoOpenedRef.current = true
          if (!isOnboardingPath(loc.pathname)) {
            navigate(onboardingPath(step), { replace: true })
            return
          }
        }
      } catch {
        // Older backends may not expose onboarding settings yet.
      }
      const returnTo = nextFromSearch(loc.search)
      if (returnTo) {
        navigate(returnTo, { replace: true })
      }
    } catch (cause) {
      if (needsAuthLoginRef.current) return
      const message =
        cause instanceof Error ? cause.message : 'Unable to connect'
      const isLocalBackend = isLocalBackendUrl(backendUrl)
      if (isAuthCredentialError(cause)) {
        try {
          const status = await client.authStatus()
          if (status.authEnabled) {
            goToLogin()
            return
          }
        } catch {
          // Fall through to backend-error UI below.
        }
      }
      if (isLocalBackend && isBackendUnavailableError(cause)) {
        needsAuthLoginRef.current = false
        setNeedsAuthLogin(false)
        setHealth(null)
        setError(message)
        setErrorStack(cause instanceof Error ? cause.stack || null : null)
        return
      }
      setHealth(null)
      setError(message)
      setErrorStack(cause instanceof Error ? cause.stack || null : null)
    } finally {
      setConnecting(false)
      setAuthBootstrapped(true)
    }
  }, [
    backendUrl,
    client,
    loadIntegrations,
    loadMcpCatalog,
    loadMcpServers,
    loadModelOptions,
    loadProjects,
    loadSessions,
    setClientApiKey,
    loadSkills,
    loadSpecialists,
    navigate,
    setRuntimeSettings,
    setSandboxSettings
  ])

  connectRef.current = connect

  useEffect(() => {
    if (needsAuthLogin || connectionPaused) return
    void connect()
  }, [connect, connectionPaused, needsAuthLogin])

  // Work can arrive from outside this client: a `sandwalk` CLI session, or a
  // Slack mention spawning one. Neither goes through the UI, and session
  // events only reach the stream of a session that is already open, so the
  // list would otherwise sit stale until the next reconnect. Poll a tiny
  // revision watermark while visible; full /sessions only when it moves.
  // Focus / visibility regain still checks immediately.
  useEffect(() => {
    if (needsAuthLogin || connectionPaused || !health) return
    const refresh = () => {
      if (document.visibilityState !== 'visible') return
      void loadSessions()
    }
    const timer = window.setInterval(refresh, SESSION_LIST_REFRESH_MS)
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [connectionPaused, health, loadSessions, needsAuthLogin])

  useEffect(() => {
    if (needsAuthLogin || connectionPaused || health || connecting) return
    if (!error) return
    if (!isLocalBackendUrl(backendUrl)) return
    if (!isBackendUnavailableError(error)) return
    const timer = window.setInterval(() => {
      void connect()
    }, 5000)
    return () => window.clearInterval(timer)
  }, [
    backendUrl,
    connect,
    connecting,
    connectionPaused,
    error,
    health,
    needsAuthLogin
  ])

  useEffect(() => {
    if (isDashboardModels || !health) return
    void loadModelOptions()
  }, [health, isDashboardModels, loadModelOptions])

  return {
    health,
    setHealth,
    needsAuthLogin,
    setNeedsAuthLogin,
    needsAuthLoginRef,
    authBootstrapped,
    setAuthBootstrapped,
    connecting,
    connectionPaused,
    setConnectionPaused,
    error,
    errorStack,
    setError,
    connect
  }
}
