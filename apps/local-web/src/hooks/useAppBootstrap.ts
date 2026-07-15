import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  AgentSkill,
  BackendHealth,
  IntegrationSummary,
  McpCatalogEntry,
  McpServer,
  RuntimeSettings,
  SandboxSettings,
  Specialist
} from '@sandwalk/agent-ui-core'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction
} from 'react'
import type { Location, NavigateFunction } from 'react-router-dom'
import { toast } from 'sonner'

import {
  clampOnboardingStep,
  isOnboardingPath,
  onboardingPath
} from '@/lib/onboarding'
import {
  isAuthCredentialError,
  isBackendUnavailableError,
  normalizeAppError
} from '@/lib/app-error'
import {
  loginPathWithNext,
  nextFromSearch,
  sanitizeAuthReturnTo
} from '@/lib/auth-routing'
import {
  type ComposerModelOption,
  toComposerModelOptions
} from '@/lib/composer-models'
import { cloudAccountDisplayName } from '@/lib/skills-catalog'
import type { SessionChatState } from '@/lib/sessions'

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8787'

type UseAppBootstrapArgs = {
  navigate: NavigateFunction
  location: Location
  setChatBySessionId: Dispatch<
    SetStateAction<Record<string, SessionChatState>>
  >
  isDashboardModels: boolean
}

export function useAppBootstrap({
  navigate,
  location,
  setChatBySessionId,
  isDashboardModels
}: UseAppBootstrapArgs) {
  const [backendUrl, setBackendUrl] = useState(
    () => localStorage.getItem('fastfold.backend.url') || DEFAULT_BACKEND_URL
  )
  const [backendApiKey, setBackendApiKey] = useState('')
  const [clientApiKey, setClientApiKey] = useState<string | undefined>()
  const client = useMemo(
    () =>
      new LocalAgentClient({
        baseUrl: backendUrl,
        apiKey: clientApiKey || backendApiKey || undefined
      }),
    [backendApiKey, backendUrl, clientApiKey]
  )
  const [health, setHealth] = useState<BackendHealth | null>(null)
  const [cloudUserName, setCloudUserName] = useState<string | null>(null)
  const [needsAuthLogin, setNeedsAuthLogin] = useState(false)
  const needsAuthLoginRef = useRef(false)
  const [authBootstrapped, setAuthBootstrapped] = useState(false)
  const [authLoggingIn, setAuthLoggingIn] = useState(false)
  const [authLoginError, setAuthLoginError] = useState<unknown>(null)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorStack, setErrorStack] = useState<string | null>(null)
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [projects, setProjects] = useState<AgentProject[]>([])
  const [sessionPreviews, setSessionPreviews] = useState<
    Record<string, string>
  >({})
  const [skills, setSkills] = useState<AgentSkill[]>([])
  const [integrations, setIntegrations] = useState<IntegrationSummary[]>([])
  const [mcpServers, setMcpServers] = useState<McpServer[]>([])
  const [mcpCatalog, setMcpCatalog] = useState<McpCatalogEntry[]>([])
  const [mcpCatalogLoading, setMcpCatalogLoading] = useState(false)
  const [specialists, setSpecialists] = useState<Specialist[]>([])
  const [specialistsLoading, setSpecialistsLoading] = useState(false)
  const [runtimeSettings, setRuntimeSettings] =
    useState<RuntimeSettings | null>(null)
  const [sandboxSettings, setSandboxSettings] =
    useState<SandboxSettings | null>(null)
  const [modelOptions, setModelOptions] = useState<ComposerModelOption[]>([])
  const onboardingAutoOpenedRef = useRef(false)
  const loadSessionsRef = useRef<(() => Promise<void>) | null>(null)

  const loadSessions = useCallback(async () => {
    const nextSessions = await client.listSessions()
    setSessions(nextSessions)
    setChatBySessionId(current => {
      let changed = false
      const next = { ...current }
      for (const item of nextSessions) {
        const prev = next[item.id]
        if (!prev) continue
        const shouldRun = item.status === 'running'
        if (prev.runActive === shouldRun) continue
        next[item.id] = { ...prev, runActive: shouldRun }
        changed = true
      }
      return changed ? next : current
    })
    void Promise.all(
      nextSessions.slice(0, 12).map(async item => {
        try {
          const history = await client.listMessages(item.id)
          return [
            item.id,
            history.at(-1)?.content || 'No messages yet.'
          ] as const
        } catch {
          return [item.id, 'No messages yet.'] as const
        }
      })
    ).then(entries => setSessionPreviews(Object.fromEntries(entries)))
  }, [client, setChatBySessionId])

  loadSessionsRef.current = loadSessions

  const loadProjects = useCallback(async () => {
    setProjects(await client.listProjects())
  }, [client])

  const loadSkills = useCallback(async () => {
    const items = await client.listSkills()
    const seen = new Set<string>()
    const unique = items.filter(skill => {
      const key = skill.name.trim().toLowerCase()
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
    setSkills(unique)
  }, [client])

  const loadIntegrations = useCallback(async () => {
    setIntegrations(await client.listIntegrations())
  }, [client])

  const loadMcpServers = useCallback(async () => {
    setMcpServers(await client.listMcpServers())
  }, [client])

  const loadMcpCatalog = useCallback(async () => {
    setMcpCatalogLoading(true)
    try {
      setMcpCatalog(await client.listMcpCatalog())
    } finally {
      setMcpCatalogLoading(false)
    }
  }, [client])

  const refreshMcp = useCallback(async () => {
    await Promise.all([loadMcpServers(), loadMcpCatalog()])
  }, [loadMcpCatalog, loadMcpServers])

  const loadSpecialists = useCallback(async () => {
    setSpecialistsLoading(true)
    try {
      setSpecialists(await client.listSpecialists())
    } catch {
      setSpecialists([])
    } finally {
      setSpecialistsLoading(false)
    }
  }, [client])

  const loadModelOptions = useCallback(async () => {
    try {
      const [models, profiles] = await Promise.all([
        client.listModels({
          enabledOnly: true,
          discover: true
        }),
        client.listModelProfiles().catch(() => [])
      ])
      const backendsByProfileId = Object.fromEntries(
        (profiles || []).map(profile => [profile.id, profile.backend])
      )
      setModelOptions(
        toComposerModelOptions(
          models.map(model => ({
            ...model,
            backend:
              model.backend ??
              (model.profileId
                ? backendsByProfileId[model.profileId] || null
                : null)
          }))
        )
      )
    } catch {
      // Keep the last known selector list if the catalog request fails.
    }
  }, [client])

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

  const loadStorage = useCallback(
    (signal?: AbortSignal) => client.getStorage(signal),
    [client]
  )
  const loadEnvironment = useCallback(
    (signal?: AbortSignal) => client.getEnvironment(signal),
    [client]
  )
  const loadServerStatus = useCallback(
    (signal?: AbortSignal) => client.getServerStatus(signal),
    [client]
  )

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
      setRuntimeSettings(settings)
      setSandboxSettings(sandbox)
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
    navigate
  ])

  const submitAuthLogin = useCallback(
    async (apiKey: string, remember: boolean) => {
      setAuthLoggingIn(true)
      setAuthLoginError(null)
      try {
        await client.login(apiKey, { remember })
        setClientApiKey(apiKey.trim())
        setBackendApiKey('')
        needsAuthLoginRef.current = false
        await connect()
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
    [client, connect]
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
  }, [client, location.pathname, location.search, navigate])

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
    backendUrl,
    setBackendUrl,
    backendApiKey,
    setBackendApiKey,
    clientApiKey,
    setClientApiKey,
    client,
    health,
    cloudUserName,
    sidebarUserName,
    needsAuthLogin,
    authBootstrapped,
    authLoggingIn,
    authLoginError,
    setAuthLoginError,
    connecting,
    error,
    errorStack,
    setError,
    sessions,
    setSessions,
    projects,
    sessionPreviews,
    skills,
    integrations,
    mcpServers,
    mcpCatalog,
    mcpCatalogLoading,
    specialists,
    specialistsLoading,
    runtimeSettings,
    setRuntimeSettings,
    sandboxSettings,
    setSandboxSettings,
    modelOptions,
    loadSessionsRef,
    loadSessions,
    loadProjects,
    loadSkills,
    loadIntegrations,
    loadMcpServers,
    loadMcpCatalog,
    refreshMcp,
    loadSpecialists,
    loadModelOptions,
    loadAccount,
    loadAccountForUi,
    logoutAccount,
    refreshCloudUserName,
    loadStorage,
    loadEnvironment,
    loadServerStatus,
    connect,
    submitAuthLogin,
    logoutSession
  }
}
