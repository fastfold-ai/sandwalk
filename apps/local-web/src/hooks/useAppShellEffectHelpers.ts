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
import type { AgentMessage, AgentSession } from '@sandwalk/agent-ui-core'

type LegacyRouteRedirectArgs = {
  locationPathname: string
  navigate: NavigateFunction
  legacySkillRouteName: string | undefined
  legacyIntegrationRouteKey: string | undefined
  onOnboardingPath: boolean
  onboardingStep: number
}

export function useAppLegacyRouteRedirects({
  locationPathname,
  navigate,
  legacySkillRouteName,
  legacyIntegrationRouteKey,
  onOnboardingPath,
  onboardingStep
}: LegacyRouteRedirectArgs) {
  useEffect(() => {
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
      navigate(`/dashboard/skills/${legacySkillRouteName}`, { replace: true })
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
}

type DocumentTitleArgs = {
  onOnboardingPath: boolean
  onboardingStep: number
  sessionTitle: string | undefined
  activeIntegration: { name: string } | null
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
}

export function useAppDocumentTitle(args: DocumentTitleArgs) {
  useEffect(() => {
    const base = 'sandwalk'
    if (args.onOnboardingPath) {
      const stepTitle = onboardingStepDef(args.onboardingStep).title
      document.title = `Onboarding ${stepTitle} - ${base}`
      return
    }
    if (args.sessionTitle) {
      document.title = `${args.sessionTitle} · ${base}`
      return
    }
    if (args.isDashboardOverview) {
      document.title = `Dashboard · ${base}`
      return
    }
    if (args.isDashboardStatus) {
      document.title = `Status · ${base}`
      return
    }
    if (args.isDashboardGeneral) {
      document.title = `General · ${base}`
      return
    }
    if (args.isDashboardModels) {
      document.title = `Models · ${base}`
      return
    }
    if (args.isDashboardTools) {
      document.title = `Tools · ${base}`
      return
    }
    if (args.isDashboardDoctor) {
      document.title = `Doctor · ${base}`
      return
    }
    if (args.isDashboardStorage) {
      document.title = `Storage · ${base}`
      return
    }
    if (args.isDashboardEnvironment) {
      document.title = `Environment · ${base}`
      return
    }
    if (args.isSkills) {
      document.title = `Skills · ${base}`
      return
    }
    if (args.isDashboardSpecialists) {
      document.title = `Specialists · ${base}`
      return
    }
    if (args.isIntegrations) {
      if (args.activeIntegration) {
        document.title = `${args.activeIntegration.name} · Integrations · ${base}`
        return
      }
      document.title = `Integrations · ${base}`
      return
    }
    if (args.isDashboardData) {
      document.title = `Datasets · ${base}`
      return
    }
    if (args.isDashboardAgentSandbox) {
      if (args.isSandboxLocalDetail) {
        document.title = `Local Sandbox · ${base}`
        return
      }
      if (args.isSandboxModalDetail) {
        document.title = `Modal Sandbox · ${base}`
        return
      }
      document.title = `Sandbox · ${base}`
      return
    }
    if (args.isDashboardAgentPrompts) {
      document.title = `Prompts · ${base}`
      return
    }
    if (args.isDashboardAgentRuntime) {
      document.title = `Runtime · ${base}`
      return
    }
    if (args.isDashboardMcp) {
      document.title = `MCP · ${base}`
      return
    }
    if (args.activeProject) {
      document.title = `${args.activeProject.name} · ${base}`
      return
    }
    document.title = base
  }, [
    args.activeIntegration,
    args.activeProject,
    args.isDashboardDoctor,
    args.isDashboardStorage,
    args.isDashboardEnvironment,
    args.isDashboardAgentSandbox,
    args.isDashboardAgentPrompts,
    args.isDashboardAgentRuntime,
    args.isSandboxLocalDetail,
    args.isSandboxModalDetail,
    args.isDashboardMcp,
    args.isDashboardOverview,
    args.isDashboardStatus,
    args.isDashboardGeneral,
    args.isDashboardModels,
    args.isDashboardData,
    args.isDashboardTools,
    args.isDashboardSpecialists,
    args.isIntegrations,
    args.isSkills,
    args.onOnboardingPath,
    args.onboardingStep,
    args.sessionTitle
  ])
}

type AutoTitleArgs = {
  sessionId: string | null
  runActive: boolean
  sessionTitle: string | undefined
  messages: AgentMessage[]
  client: LocalAgentClient
  setSessions: Dispatch<SetStateAction<AgentSession[]>>
}

export function useAppAutoTitle({
  sessionId,
  runActive,
  sessionTitle,
  messages,
  client,
  setSessions
}: AutoTitleArgs) {
  const autoTitlePassCountRef = useRef<Record<string, number>>({})
  const autoTitleInFlightRef = useRef<Record<string, boolean>>({})
  const prevRunActiveForTitleRef = useRef<Record<string, boolean>>({})

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
}

export function useAppChatSkeleton(messagesLoaded: boolean, runActive: boolean, sessionId: string | null) {
  const [showChatSkeleton, setShowChatSkeleton] = useState(false)

  useEffect(() => {
    if (messagesLoaded || runActive || !sessionId) {
      setShowChatSkeleton(false)
      return
    }
    const timer = window.setTimeout(() => setShowChatSkeleton(true), 180)
    return () => window.clearTimeout(timer)
  }, [messagesLoaded, runActive, sessionId])

  return showChatSkeleton
}

type PanelPersistenceArgs = {
  sidebarCollapsed: boolean
  filesPanelCollapsed: boolean
  terminalOpen: boolean
  sidebarPanelRef: RefObject<ImperativePanelHandle | null>
  filesPanelRef: RefObject<ImperativePanelHandle | null>
  collapsedSidebarSections: Record<string, boolean>
  sessionId: string | null
}

export function useAppPanelPersistence({
  sidebarCollapsed,
  filesPanelCollapsed,
  terminalOpen,
  sidebarPanelRef,
  filesPanelRef,
  collapsedSidebarSections,
  sessionId
}: PanelPersistenceArgs) {
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
  }, [sidebarCollapsed, sidebarPanelRef])

  useEffect(() => {
    const panel = filesPanelRef.current
    if (!panel) return
    if (filesPanelCollapsed) {
      if (!panel.isCollapsed()) panel.collapse()
    } else if (panel.isCollapsed()) {
      panel.expand()
    }
  }, [filesPanelCollapsed, sessionId, filesPanelRef])

  useEffect(() => {
    writeCollapsedSidebarSections(collapsedSidebarSections)
  }, [collapsedSidebarSections])
}
