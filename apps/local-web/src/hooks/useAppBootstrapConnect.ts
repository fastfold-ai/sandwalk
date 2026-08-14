import {
  LocalAgentClient,
  readSessionToken
} from '@sandwalk/agent-local-client'
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
import {
  hasDesktopBackendInject,
  isLocalBackendUrl,
  persistBackendUrl
} from '@/lib/backend-url'
import { normalizeBackendUrl } from '@/lib/backend-url'
import { dedupeAsync, invalidateDedupe } from '@/lib/dedupe-async'
import { isTauri, listenDesktopApplyAuth } from '@/lib/desktop'
import {
  clampOnboardingStep,
  isOnboardingPath,
  onboardingPath
} from '@/lib/onboarding'
import { clearRememberedApiKey, persistRememberedApiKey } from '@/lib/remembered-auth'
import { resolveBackendApiKey } from '@/lib/resolve-backend-api-key'

import type { useAppBootstrapLoaders } from './useAppBootstrapLoaders'
import { useLocalServerWait } from './useLocalServerWait'

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
  setAuthLoginError: (value: unknown | null) => void
}

/** Prefer the raw API error so ErrorPage can title it "Invalid API key". */
function credentialLoginError(cause?: unknown): unknown {
  if (cause != null) return cause
  return {
    title: 'Invalid API key',
    detail:
      'That key was rejected by this server. Copy it from Security (or run sandwalk auth show) on the machine you are connecting to.',
    hint: 'Sign in again with the correct API key. A remembered key that no longer matches will keep failing until you replace it.',
    status: 401,
    raw: 'Missing or invalid backend API key.',
    stack: null,
    name: null
  }
}

export function useAppBootstrapConnect({
  client,
  backendUrl,
  navigate,
  location,
  isDashboardModels,
  loaders,
  connectRef,
  setClientApiKey,
  setAuthLoginError
}: UseAppBootstrapConnectArgs) {
  const [health, setHealth] = useState<BackendHealth | null>(null)
  const [needsAuthLogin, setNeedsAuthLogin] = useState(false)
  const needsAuthLoginRef = useRef(false)
  const [authBootstrapped, setAuthBootstrapped] = useState(false)
  const [connecting, setConnecting] = useState(false)
  /**
   * Stay on the welcome / connect gate until the user picks Local or Remote.
   * Desktop cold start (no remote inject) starts paused so we don't auto-hit
   * 127.0.0.1 and flash “Backend unreachable”. Browser/dev still auto-connects.
   */
  const [connectionPaused, setConnectionPaused] = useState(
    () => isTauri() && !hasDesktopBackendInject()
  )
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

    const goToLogin = (options?: {
      clearRemembered?: boolean
      reason?: unknown
    }) => {
      const alreadyNext = nextFromSearch(loc.search)
      const deepLink =
        loc.pathname === '/'
          ? null
          : sanitizeAuthReturnTo(`${loc.pathname}${loc.search}${loc.hash}`)
      if (options?.clearRemembered !== false && client.apiKey) {
        clearRememberedApiKey(backendUrl)
        setClientApiKey(undefined)
      }
      needsAuthLoginRef.current = true
      setHealth(null)
      setNeedsAuthLogin(true)
      if (options?.reason !== undefined) {
        setAuthLoginError(credentialLoginError(options.reason))
      }
      const target = loginPathWithNext(alreadyNext || deepLink)
      if (`${loc.pathname}${loc.search}` !== target) {
        navigate(target, { replace: true })
      }
    }

    try {
      if (needsAuthLoginRef.current) {
        return
      }
      let sessionKey =
        client.apiKey?.trim() ||
        (await resolveBackendApiKey(backendUrl)) ||
        ''
      if (sessionKey && sessionKey !== (client.apiKey || '')) {
        persistRememberedApiKey(backendUrl, sessionKey)
        setClientApiKey(sessionKey)
      }
      const active = sessionKey
        ? new LocalAgentClient({
            baseUrl: backendUrl,
            apiKey: sessionKey,
            sessionToken: readSessionToken(backendUrl)
          })
        : client

      const nextHealth = await dedupeAsync(`health:${scope}`, () =>
        active.health()
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
        const status = await dedupeAsync(
          `auth-status:${scope}`,
          () => active.authStatus(),
          { force: true }
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
          if (!sessionKey) {
            const recovered = await resolveBackendApiKey(backendUrl)
            if (recovered) {
              persistRememberedApiKey(backendUrl, recovered)
              setClientApiKey(recovered)
              return
            }
            goToLogin({ clearRemembered: false })
            return
          }
          try {
            await active.login(sessionKey, { remember: true })
            invalidateDedupe(`auth-status:${scope}`)
          } catch (cause) {
            if (isAuthCredentialError(cause)) {
              goToLogin({ clearRemembered: true, reason: cause })
              return
            }
            try {
              await active.getRuntimeSettings()
            } catch (probe) {
              if (isAuthCredentialError(probe)) {
                goToLogin({ clearRemembered: false, reason: probe })
                return
              }
              throw probe
            }
          }
        }
        if (authenticated === null) {
          try {
            await dedupeAsync(`runtime:${scope}`, () =>
              active.getRuntimeSettings()
            )
          } catch (cause) {
            if (isAuthCredentialError(cause)) {
              if (!sessionKey) {
                const recovered = await resolveBackendApiKey(backendUrl)
                if (recovered) {
                  persistRememberedApiKey(backendUrl, recovered)
                  setClientApiKey(recovered)
                  return
                }
              }
              goToLogin({
                clearRemembered: Boolean(sessionKey),
                reason: cause
              })
              return
            }
            throw cause
          }
        }
      }
      if (needsAuthLoginRef.current) return

      // Wait for React client to carry the key before keyless loaders run.
      if (sessionKey && sessionKey !== (client.apiKey || '')) {
        setClientApiKey(sessionKey)
        needsAuthLoginRef.current = false
        setNeedsAuthLogin(false)
        setHealth(nextHealth)
        return
      }

      needsAuthLoginRef.current = false
      setNeedsAuthLogin(false)
      setAuthLoginError(null)
      setHealth(nextHealth)
      const [, , , , , , , settings, sandbox] = await Promise.all([
        loadSessions({ force: true }),
        loadProjects(),
        loadSkills(),
        loadIntegrations(),
        loadMcpServers(),
        loadMcpCatalog(),
        loadSpecialists(),
        dedupeAsync(`runtime:${scope}`, () => active.getRuntimeSettings()),
        dedupeAsync(`sandbox:${scope}`, () =>
          active.getSandboxSettings().catch(() => null)
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
            // Keep typed/remembered key so Login shows a clear error, not an empty loop.
            goToLogin({ clearRemembered: false, reason: cause })
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
    setAuthLoginError,
    loadSkills,
    loadSpecialists,
    navigate,
    setRuntimeSettings,
    setSandboxSettings
  ])

  connectRef.current = connect

  const localStarting = useLocalServerWait({
    backendUrl,
    connecting,
    error,
    health,
    connectionPaused,
    needsAuthLogin,
    connect
  })

  useEffect(() => {
    if (!isTauri()) return
    let cancelled = false
    let unlisten: (() => void) | undefined
    void listenDesktopApplyAuth(payload => {
      if (cancelled) return
      const url = normalizeBackendUrl(payload.url)
      if (normalizeBackendUrl(backendUrl) !== url) return
      const key = payload.apiKey.trim()
      if (!key) return
      persistRememberedApiKey(url, key)
      needsAuthLoginRef.current = false
      setNeedsAuthLogin(false)
      setClientApiKey(key)
    }).then(fn => {
      if (cancelled) fn()
      else unlisten = fn
    })
    return () => {
      cancelled = true
      unlisten?.()
    }
  }, [backendUrl, setClientApiKey])

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
      void loadSessions().catch(cause => {
        if (!isAuthCredentialError(cause)) return
        needsAuthLoginRef.current = true
        setHealth(null)
        setNeedsAuthLogin(true)
        setAuthLoginError(credentialLoginError(cause))
      })
    }
    const timer = window.setInterval(refresh, SESSION_LIST_REFRESH_MS)
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [connectionPaused, health, loadSessions, needsAuthLogin, setAuthLoginError])

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
    localStarting,
    setError,
    connect
  }
}
