import type { Dispatch, SetStateAction } from 'react'
import { useRef } from 'react'
import type { Location, NavigateFunction } from 'react-router-dom'

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

export function useAppBootstrap({
  navigate,
  location,
  setChatBySessionId,
  isDashboardModels
}: UseAppBootstrapArgs) {
  const clientBundle = useAppBootstrapClient()
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
    setClientApiKey: clientBundle.setClientApiKey
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
    setConnectionPaused: connectBundle.setConnectionPaused
  })

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
    authLoginError: auth.authLoginError,
    setAuthLoginError: auth.setAuthLoginError,
    connecting: connectBundle.connecting,
    connectionPaused: connectBundle.connectionPaused,
    setConnectionPaused: connectBundle.setConnectionPaused,
    error: connectBundle.error,
    errorStack: connectBundle.errorStack,
    setError: connectBundle.setError,
    sessions: loaders.sessions,
    setSessions: loaders.setSessions,
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
    disconnectBackend: auth.disconnectBackend,
    changeBackend: auth.changeBackend
  }
}
