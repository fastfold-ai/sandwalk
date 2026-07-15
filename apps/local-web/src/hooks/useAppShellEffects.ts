import { useEffect, useRef, useState } from 'react'
import type { Dispatch, RefObject, SetStateAction } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import type { NavigateFunction } from 'react-router-dom'

import {
  FILES_PANEL_COLLAPSED_STORAGE_KEY,
  SIDEBAR_COLLAPSED_STORAGE_KEY,
  TERMINAL_OPEN_STORAGE_KEY,
  writeCollapsedSidebarSections
} from '@/lib/app-storage'
import {
  onboardingPath,
  onboardingStepDef
} from '@/lib/onboarding'
import {
  AUTO_TITLE_FIRST_RESPONSE_THRESHOLD,
  isLowSignalTitle
} from '@/lib/sessions'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentMessage,
  AgentSession,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'

type UseAppShellEffectsArgs = {
  locationPathname: string
  navigate: NavigateFunction
  legacySkillRouteName: string | undefined
  legacyIntegrationRouteKey: string | undefined
  onOnboardingPath: boolean
  onboardingStep: number
  sessionTitle: string | undefined
  activeIntegration: IntegrationSummary | null
  activeProject: { name: string } | null
  isDashboardOverview: boolean
  isDashboardStatus: boolean
  isDashboardGeneral: boolean
  isDashboardModels: boolean
  isDashboardTools: boolean
  isDashboardDoctor: boolean
  isDashboardStorage: boolean
  isDashboardEnvironment: boolean
  isSkills: boolean
  isDashboardSpecialists: boolean
  isIntegrations: boolean
  isDashboardData: boolean
  isDashboardAgentSandbox: boolean
  isSandboxLocalDetail: boolean
  isSandboxModalDetail: boolean
  isDashboardAgentPrompts: boolean
  isDashboardAgentRuntime: boolean
  isDashboardMcp: boolean
  sidebarCollapsed: boolean
  filesPanelCollapsed: boolean
  terminalOpen: boolean
  sidebarPanelRef: RefObject<ImperativePanelHandle | null>
  filesPanelRef: RefObject<ImperativePanelHandle | null>
  collapsedSidebarSections: Record<string, boolean>
  runningCount: number
  concurrentRunSoftLimit: number
  setConnectionLimitDismissed: Dispatch<SetStateAction<boolean>>
  routeProjectId: string | null
  setProjectScopeId: Dispatch<SetStateAction<string | null>>
  messagesLoaded: boolean
  runActive: boolean
  sessionId: string | null
  client: LocalAgentClient
  messages: AgentMessage[]
  setSessions: Dispatch<SetStateAction<AgentSession[]>>
}

export function useAppShellEffects({
  locationPathname,
  navigate,
  legacySkillRouteName,
  legacyIntegrationRouteKey,
  onOnboardingPath,
  onboardingStep,
  sessionTitle,
  activeIntegration,
  activeProject,
  isDashboardOverview,
  isDashboardStatus,
  isDashboardGeneral,
  isDashboardModels,
  isDashboardTools,
  isDashboardDoctor,
  isDashboardStorage,
  isDashboardEnvironment,
  isSkills,
  isDashboardSpecialists,
  isIntegrations,
  isDashboardData,
  isDashboardAgentSandbox,
  isSandboxLocalDetail,
  isSandboxModalDetail,
  isDashboardAgentPrompts,
  isDashboardAgentRuntime,
  isDashboardMcp,
  sidebarCollapsed,
  filesPanelCollapsed,
  terminalOpen,
  sidebarPanelRef,
  filesPanelRef,
  collapsedSidebarSections,
  runningCount,
  concurrentRunSoftLimit,
  setConnectionLimitDismissed,
  routeProjectId,
  setProjectScopeId,
  messagesLoaded,
  runActive,
  sessionId,
  client,
  messages,
  setSessions
}: UseAppShellEffectsArgs) {
  const autoTitlePassCountRef = useRef<Record<string, number>>({})
  const autoTitleInFlightRef = useRef<Record<string, boolean>>({})
  const prevRunActiveForTitleRef = useRef<Record<string, boolean>>({})

  const [showChatSkeleton, setShowChatSkeleton] = useState(false)

  useEffect(() => {
    // Legacy /login URL → root (login renders under / when unauthenticated).
    if (locationPathname === '/login') {
      navigate('/', { replace: true })
      return
    }
    if (locationPathname === '/agents/home') {
      navigate('/', { replace: true })
      return
    }
    if (locationPathname === '/dashboard/settings') {
      navigate('/dashboard/general', { replace: true })
      return
    }
    if (locationPathname === '/agents/skills') {
      navigate('/dashboard/skills', { replace: true })
      return
    }
    if (legacySkillRouteName) {
      navigate(
        `/dashboard/skills/${legacySkillRouteName}`,
        { replace: true }
      )
      return
    }
    if (locationPathname === '/agents/integrations') {
      navigate('/dashboard/integrations', { replace: true })
      return
    }
    if (legacyIntegrationRouteKey) {
      navigate(
        `/dashboard/integrations/${legacyIntegrationRouteKey}`,
        { replace: true }
      )
      return
    }
    if (onOnboardingPath) {
      const canonical = onboardingPath(onboardingStep)
      if (locationPathname !== canonical) {
        navigate(canonical, { replace: true })
      }
    }
  }, [
    legacyIntegrationRouteKey,
    legacySkillRouteName,
    locationPathname,
    navigate,
    onOnboardingPath,
    onboardingStep
  ])

  useEffect(() => {
    const base = 'sandwalk'
    if (onOnboardingPath) {
      const stepTitle = onboardingStepDef(onboardingStep).title
      document.title = `Onboarding ${stepTitle} - ${base}`
      return
    }
    if (sessionTitle) {
      document.title = `${sessionTitle} · ${base}`
      return
    }
    if (isDashboardOverview) {
      document.title = `Dashboard · ${base}`
      return
    }
    if (isDashboardStatus) {
      document.title = `Status · ${base}`
      return
    }
    if (isDashboardGeneral) {
      document.title = `General · ${base}`
      return
    }
    if (isDashboardModels) {
      document.title = `Models · ${base}`
      return
    }
    if (isDashboardTools) {
      document.title = `Tools · ${base}`
      return
    }
    if (isDashboardDoctor) {
      document.title = `Doctor · ${base}`
      return
    }
    if (isDashboardStorage) {
      document.title = `Storage · ${base}`
      return
    }
    if (isDashboardEnvironment) {
      document.title = `Environment · ${base}`
      return
    }
    if (isSkills) {
      document.title = `Skills · ${base}`
      return
    }
    if (isDashboardSpecialists) {
      document.title = `Specialists · ${base}`
      return
    }
    if (isIntegrations) {
      if (activeIntegration) {
        document.title = `${activeIntegration.name} · Integrations · ${base}`
        return
      }
      document.title = `Integrations · ${base}`
      return
    }
    if (isDashboardData) {
      document.title = `Datasets · ${base}`
      return
    }
    if (isDashboardAgentSandbox) {
      if (isSandboxLocalDetail) {
        document.title = `Local Sandbox · ${base}`
        return
      }
      if (isSandboxModalDetail) {
        document.title = `Modal Sandbox · ${base}`
        return
      }
      document.title = `Sandbox · ${base}`
      return
    }
    if (isDashboardAgentPrompts) {
      document.title = `Prompts · ${base}`
      return
    }
    if (isDashboardAgentRuntime) {
      document.title = `Runtime · ${base}`
      return
    }
    if (isDashboardMcp) {
      document.title = `MCP · ${base}`
      return
    }
    if (activeProject) {
      document.title = `${activeProject.name} · ${base}`
      return
    }
    document.title = base
  }, [
    activeIntegration,
    activeProject,
    isDashboardDoctor,
    isDashboardStorage,
    isDashboardEnvironment,
    isDashboardAgentSandbox,
    isDashboardAgentPrompts,
    isDashboardAgentRuntime,
    isSandboxLocalDetail,
    isSandboxModalDetail,
    isDashboardMcp,
    isDashboardOverview,
    isDashboardStatus,
    isDashboardGeneral,
    isDashboardModels,
    isDashboardData,
    isDashboardTools,
    isDashboardSpecialists,
    isIntegrations,
    isSkills,
    onOnboardingPath,
    onboardingStep,
    sessionTitle
  ])

  useEffect(() => {
    try {
      localStorage.setItem(
        SIDEBAR_COLLAPSED_STORAGE_KEY,
        sidebarCollapsed ? '1' : '0'
      )
    } catch {
      // ignore storage failures
    }
  }, [sidebarCollapsed])

  useEffect(() => {
    try {
      localStorage.setItem(
        FILES_PANEL_COLLAPSED_STORAGE_KEY,
        filesPanelCollapsed ? '1' : '0'
      )
    } catch {
      // ignore storage failures
    }
  }, [filesPanelCollapsed])

  useEffect(() => {
    try {
      localStorage.setItem(TERMINAL_OPEN_STORAGE_KEY, terminalOpen ? '1' : '0')
    } catch {
      // ignore storage failures
    }
  }, [terminalOpen])

  useEffect(() => {
    const panel = sidebarPanelRef.current
    if (!panel) return
    if (sidebarCollapsed) {
      if (!panel.isCollapsed()) panel.collapse()
    } else if (panel.isCollapsed()) {
      panel.expand()
    }
  }, [sidebarCollapsed])

  useEffect(() => {
    const panel = filesPanelRef.current
    if (!panel) return
    if (filesPanelCollapsed) {
      if (!panel.isCollapsed()) panel.collapse()
    } else if (panel.isCollapsed()) {
      panel.expand()
    }
  }, [filesPanelCollapsed, sessionId])

  useEffect(() => {
    writeCollapsedSidebarSections(collapsedSidebarSections)
  }, [collapsedSidebarSections])

  useEffect(() => {
    if (runningCount < concurrentRunSoftLimit) {
      setConnectionLimitDismissed(false)
    }
  }, [concurrentRunSoftLimit, runningCount, setConnectionLimitDismissed])

  useEffect(() => {
    if (routeProjectId) {
      setProjectScopeId(routeProjectId)
      return
    }
    if (
      locationPathname === '/' ||
      locationPathname === '/agents/home'
    ) {
      setProjectScopeId(null)
    }
  }, [locationPathname, routeProjectId, setProjectScopeId])

  useEffect(() => {
    if (messagesLoaded || runActive || !sessionId) {
      setShowChatSkeleton(false)
      return
    }
    const timer = window.setTimeout(() => setShowChatSkeleton(true), 180)
    return () => window.clearTimeout(timer)
  }, [messagesLoaded, runActive, sessionId])

  useEffect(() => {
    if (!sessionId) return
    const justFinished =
      Boolean(prevRunActiveForTitleRef.current[sessionId]) && !runActive
    prevRunActiveForTitleRef.current[sessionId] = runActive
    if (!justFinished || autoTitleInFlightRef.current[sessionId]) return
    const conversationCount = messages.filter(
      message => message.role === 'user' || message.role === 'assistant'
    ).length
    if (conversationCount < AUTO_TITLE_FIRST_RESPONSE_THRESHOLD) return
    if (!isLowSignalTitle(sessionTitle || '')) return
    // Keep retrying while the stored title is still a placeholder (e.g. after
    // a bad overwrite). Cap attempts so intentional untitled chats settle.
    if ((autoTitlePassCountRef.current[sessionId] || 0) >= 3) return

    autoTitleInFlightRef.current[sessionId] = true
    const titledSessionId = sessionId
    void (async () => {
      try {
        const updated = await client.autoTitleSession(titledSessionId, {
          force: true
        })
        const title = String(updated.title || '').trim()
        if (!title) return
        setSessions(current =>
          current.map(item =>
            item.id === titledSessionId
              ? { ...item, title, updatedAt: updated.updatedAt }
              : item
          )
        )
        autoTitlePassCountRef.current[titledSessionId] =
          (autoTitlePassCountRef.current[titledSessionId] || 0) + 1
      } catch {
        // Best effort; retry on a later completed run.
      } finally {
        autoTitleInFlightRef.current[titledSessionId] = false
      }
    })()
  }, [client, messages, runActive, sessionTitle, sessionId, setSessions])

  return { showChatSkeleton }
}
