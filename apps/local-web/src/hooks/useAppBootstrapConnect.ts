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
import {
  clampOnboardingStep,
  isOnboardingPath,
  onboardingPath
} from '@/lib/onboarding'

import type { useAppBootstrapLoaders } from './useAppBootstrapLoaders'

type LoaderBundle = ReturnType<typeof useAppBootstrapLoaders>

type UseAppBootstrapConnectArgs = {
  client: LocalAgentClient
  backendUrl: string
  navigate: NavigateFunction
  location: Location
  isDashboardModels: boolean
  loaders: LoaderBundle
  connectRef: MutableRefObject<(() => Promise<void>) | null>
}

export function useAppBootstrapConnect({
  client,
  backendUrl,
  navigate,
  location,
  isDashboardModels,
  loaders,
  connectRef
}: UseAppBootstrapConnectArgs) {
  const [health, setHealth] = useState<BackendHealth | null>(null)
  const [needsAuthLogin, setNeedsAuthLogin] = useState(false)
  const needsAuthLoginRef = useRef(false)
  const [authBootstrapped, setAuthBootstrapped] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorStack, setErrorStack] = useState<string | null>(null)
  const onboardingAutoOpenedRef = useRef(false)

  // Depend on stable loader callbacks — never the whole `loaders` object
  // (it is a new reference every render and would retrigger connect forever).
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
    setConnecting(true)
    setError(null)
    setErrorStack(null)
    const goToLogin = () => {
      const alreadyNext = nextFromSearch(location.search)
      const deepLink =
        location.pathname === '/'
          ? null
          : sanitizeAuthReturnTo(
              `${location.pathname}${location.search}${location.hash}`
            )
      needsAuthLoginRef.current = true
      setHealth(null)
      setNeedsAuthLogin(true)
      const target = loginPathWithNext(alreadyNext || deepLink)
      if (`${location.pathname}${location.search}` !== target) {
        navigate(target, { replace: true })
      }
    }

    try {
      if (needsAuthLoginRef.current) {
        return
      }
      const nextHealth = await client.health()
      if (needsAuthLoginRef.current) return
      localStorage.setItem('fastfold.backend.url', backendUrl)

      let authEnabled = false
      let authenticated: boolean | null = null
      try {
        const status = await client.authStatus()
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
            await client.getRuntimeSettings()
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
        loadSessions(),
        loadProjects(),
        loadSkills(),
        loadIntegrations(),
        loadMcpServers(),
        loadMcpCatalog(),
        loadSpecialists(),
        client.getRuntimeSettings(),
        client.getSandboxSettings().catch(() => null),
        loadModelOptions()
      ])
      if (needsAuthLoginRef.current) return
      setRuntimeSettings(settings as RuntimeSettings)
      setSandboxSettings(sandbox as SandboxSettings | null)
      try {
        const onboarding = await client.getOnboardingSettings()
        const step = clampOnboardingStep(onboarding.step)
        if (!onboarding.completed && !onboardingAutoOpenedRef.current) {
          onboardingAutoOpenedRef.current = true
          if (!isOnboardingPath(location.pathname)) {
            navigate(onboardingPath(step), { replace: true })
            return
          }
        }
      } catch {
        // Older backends may not expose onboarding settings yet.
      }
      const returnTo = nextFromSearch(location.search)
      if (returnTo) {
        navigate(returnTo, { replace: true })
      }
    } catch (cause) {
      if (needsAuthLoginRef.current) return
      const message =
        cause instanceof Error ? cause.message : 'Unable to connect'
      const isLocalBackend = /127\.0\.0\.1|localhost/i.test(backendUrl)
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
    loadSkills,
    loadSpecialists,
    location.hash,
    location.pathname,
    location.search,
    navigate,
    setRuntimeSettings,
    setSandboxSettings
  ])

  connectRef.current = connect

  useEffect(() => {
    if (needsAuthLogin) return
    void connect()
  }, [connect, needsAuthLogin])

  useEffect(() => {
    if (needsAuthLogin || health || connecting) return
    if (!error) return
    if (!/127\.0\.0\.1|localhost/i.test(backendUrl)) return
    if (!isBackendUnavailableError(error)) return
    const timer = window.setInterval(() => {
      void connect()
    }, 5000)
    return () => window.clearInterval(timer)
  }, [backendUrl, connect, connecting, error, health, needsAuthLogin])

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
    error,
    errorStack,
    setError,
    connect
  }
}
