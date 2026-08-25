import type { Dispatch, SetStateAction } from 'react'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Location, NavigateFunction } from 'react-router-dom'

import { hasDesktopBackendInject, isLocalBackendUrl } from '@/lib/backend-url'
import {
  hideDesktopWindow,
  isMainDesktopWindow,
  isTauri,
  listDesktopWindowRecents
} from '@/lib/desktop'
import { openDesktopRecent } from '@/lib/open-desktop-recent'
import type { SessionChatState } from '@/lib/sessions'

import { useAppBootstrapAuth } from './useAppBootstrapAuth'
import { useAppBootstrapClient } from './useAppBootstrapClient'
import { useAppBootstrapConnect } from './useAppBootstrapConnect'
import { useAppBootstrapLoaders } from './useAppBootstrapLoaders'

type UseAppBootstrapArgs = {
  navigate: NavigateFunction
  location: Location
  setChatBySessionId: Dispatch<
    SetStateAction<Record<string, SessionChatState>>
  >
  isDashboardModels: boolean
}

function shouldAttemptColdRestore(): boolean {
  return isTauri() && isMainDesktopWindow() && !hasDesktopBackendInject()
}

export function useAppBootstrap({
  navigate,
  location,
  setChatBySessionId,
  isDashboardModels
}: UseAppBootstrapArgs) {
  const clientBundle = useAppBootstrapClient()
  const [authLoginError, setAuthLoginError] = useState<unknown>(null)
  const loaders = useAppBootstrapLoaders({
    client: clientBundle.client,
    setChatBySessionId
  })
  const connectRef = useRef<(() => Promise<void>) | null>(null)
  const connectBundle = useAppBootstrapConnect({
    client: clientBundle.client,
    backendUrl: clientBundle.backendUrl,
    navigate,
    location,
    isDashboardModels,
    loaders,
    connectRef,
    setClientApiKey: clientBundle.setClientApiKey,
    setAuthLoginError
  })
  const auth = useAppBootstrapAuth({
    client: clientBundle.client,
    navigate,
    location,
    health: connectBundle.health,
    setHealth: connectBundle.setHealth,
    setBackendUrl: clientBundle.setBackendUrl,
    setBackendApiKey: clientBundle.setBackendApiKey,
    setClientApiKey: clientBundle.setClientApiKey,
    setRuntimeSettings: loaders.setRuntimeSettings,
    setError: connectBundle.setError,
    needsAuthLoginRef: connectBundle.needsAuthLoginRef,
    setNeedsAuthLogin: connectBundle.setNeedsAuthLogin,
    setAuthBootstrapped: connectBundle.setAuthBootstrapped,
    setConnectionPaused: connectBundle.setConnectionPaused,
    setAuthLoginError
  })

  const skipAutoRestoreRef = useRef(false)
  const autoRestoreStartedRef = useRef(false)
  const changeBackendRef = useRef(auth.changeBackend)
  changeBackendRef.current = auth.changeBackend
  const [autoRestoring, setAutoRestoring] = useState(shouldAttemptColdRestore)

  const disconnectBackend = useCallback(async () => {
    skipAutoRestoreRef.current = true
    setAutoRestoring(false)
    await auth.disconnectBackend()
  }, [auth])

  // Cold-start main window: reopen the most recent local/remote session.
  // Disconnect skips this so Welcome Home stays up. File → New Window opens a
  // client window on the chooser (no cold restore; no focused-backend bind).
  useEffect(() => {
    if (!connectBundle.connectionPaused) {
      setAutoRestoring(false)
      return
    }
    if (!shouldAttemptColdRestore()) {
      setAutoRestoring(false)
      return
    }
    if (skipAutoRestoreRef.current || autoRestoreStartedRef.current) {
      setAutoRestoring(false)
      return
    }
    autoRestoreStartedRef.current = true

    void (async () => {
      try {
        const rows = (await listDesktopWindowRecents()) ?? []
        const last = rows[0]
        if (!last?.url) {
          setAutoRestoring(false)
          return
        }
        if (isLocalBackendUrl(last.url)) {
          await changeBackendRef.current(last.url)
          setAutoRestoring(false)
          return
        }
        const result = await openDesktopRecent({
          url: last.url,
          route: last.route,
          title: last.title,
          id: last.id,
          hostname: last.hostname,
          platform: last.platform
        })
        if (result.opened) {
          void hideDesktopWindow().catch(() => {
            // ignore
          })
        }
        setAutoRestoring(false)
      } catch {
        setAutoRestoring(false)
      }
    })()
  }, [connectBundle.connectionPaused])

  return {
    backendUrl: clientBundle.backendUrl,
    setBackendUrl: clientBundle.setBackendUrl,
    backendApiKey: clientBundle.backendApiKey,
    setBackendApiKey: clientBundle.setBackendApiKey,
    clientApiKey: clientBundle.clientApiKey,
    setClientApiKey: clientBundle.setClientApiKey,
    client: clientBundle.client,
    health: connectBundle.health,
    cloudUserName: auth.cloudUserName,
    sidebarUserName: auth.sidebarUserName,
    needsAuthLogin: connectBundle.needsAuthLogin,
    authBootstrapped: connectBundle.authBootstrapped,
    authLoggingIn: auth.authLoggingIn,
    authLoginError,
    setAuthLoginError,
    connecting: connectBundle.connecting,
    connectionPaused: connectBundle.connectionPaused,
    setConnectionPaused: connectBundle.setConnectionPaused,
    autoRestoring,
    error: connectBundle.error,
    errorStack: connectBundle.errorStack,
    localStarting: connectBundle.localStarting,
    setError: connectBundle.setError,
    sessions: loaders.sessions,
    setSessions: loaders.setSessions,
    sessionsInitialLoadDone: loaders.sessionsInitialLoadDone,
    projects: loaders.projects,
    sessionPreviews: loaders.sessionPreviews,
    loadSessionPreviews: loaders.loadSessionPreviews,
    skills: loaders.skills,
    integrations: loaders.integrations,
    mcpServers: loaders.mcpServers,
    mcpCatalog: loaders.mcpCatalog,
    mcpCatalogLoading: loaders.mcpCatalogLoading,
    specialists: loaders.specialists,
    specialistsLoading: loaders.specialistsLoading,
    runtimeSettings: loaders.runtimeSettings,
    setRuntimeSettings: loaders.setRuntimeSettings,
    sandboxSettings: loaders.sandboxSettings,
    setSandboxSettings: loaders.setSandboxSettings,
    modelOptions: loaders.modelOptions,
    loadSessionsRef: loaders.loadSessionsRef,
    loadSkillsRef: loaders.loadSkillsRef,
    loadSessions: loaders.loadSessions,
    loadForeignSessions: loaders.loadForeignSessions,
    loadProjects: loaders.loadProjects,
    loadSkills: loaders.loadSkills,
    loadIntegrations: loaders.loadIntegrations,
    loadMcpServers: loaders.loadMcpServers,
    loadMcpCatalog: loaders.loadMcpCatalog,
    refreshMcp: loaders.refreshMcp,
    loadSpecialists: loaders.loadSpecialists,
    loadModelOptions: loaders.loadModelOptions,
    loadAccount: auth.loadAccount,
    loadAccountForUi: auth.loadAccountForUi,
    logoutAccount: auth.logoutAccount,
    refreshCloudUserName: auth.refreshCloudUserName,
    loadStorage: loaders.loadStorage,
    loadEnvironment: loaders.loadEnvironment,
    loadServerStatus: loaders.loadServerStatus,
    connect: connectBundle.connect,
    submitAuthLogin: auth.submitAuthLogin,
    logoutSession: auth.logoutSession,
    disconnectBackend,
    changeBackend: auth.changeBackend
  }
}
