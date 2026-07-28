import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentMessage,
  AgentSession,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'
import type { Dispatch, RefObject, SetStateAction } from 'react'
import { useEffect } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import type { NavigateFunction } from 'react-router-dom'

import {
  useAppAutoTitle,
  useAppChatSkeleton,
  useAppDocumentTitle,
  useAppLegacyRouteRedirects,
  useAppPanelPersistence
} from '@/hooks/useAppShellEffectHelpers'

type UseAppShellEffectsArgs = {
  locationPathname: string
  navigate: NavigateFunction
  legacySkillRouteName: string | undefined
  legacyIntegrationRouteKey: string | undefined
  onOnboardingPath: boolean
  onboardingStep: number
  sessionTitle: string | undefined
  titleSource: AgentSession['titleSource']
  activeIntegration: IntegrationSummary | null
  activeProject: { name: string } | null
  isDashboardOverview: boolean
  isDashboardStatus: boolean
  isDashboardGeneral: boolean
  isDashboardAppearance: boolean
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
  isDashboardAgentSecurity: boolean
  isSandboxLocalDetail: boolean
  isSandboxModalDetail: boolean
  isDashboardAgentPrompts: boolean
  isDashboardVoice: boolean
  isDashboardAgentRuntime: boolean
  isDashboardMcp: boolean
  isLibrary: boolean
  isSites: boolean
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

export function useAppShellEffects(args: UseAppShellEffectsArgs) {
  useAppLegacyRouteRedirects({
    locationPathname: args.locationPathname,
    navigate: args.navigate,
    legacySkillRouteName: args.legacySkillRouteName,
    legacyIntegrationRouteKey: args.legacyIntegrationRouteKey,
    onOnboardingPath: args.onOnboardingPath,
    onboardingStep: args.onboardingStep
  })

  useAppDocumentTitle({
    onOnboardingPath: args.onOnboardingPath,
    onboardingStep: args.onboardingStep,
    sessionTitle: args.sessionTitle,
    activeIntegration: args.activeIntegration,
    activeProject: args.activeProject,
    isDashboardOverview: args.isDashboardOverview,
    isDashboardStatus: args.isDashboardStatus,
    isDashboardGeneral: args.isDashboardGeneral,
    isDashboardAppearance: args.isDashboardAppearance,
    isDashboardModels: args.isDashboardModels,
    isDashboardTools: args.isDashboardTools,
    isDashboardDoctor: args.isDashboardDoctor,
    isDashboardStorage: args.isDashboardStorage,
    isDashboardEnvironment: args.isDashboardEnvironment,
    isSkills: args.isSkills,
    isDashboardSpecialists: args.isDashboardSpecialists,
    isIntegrations: args.isIntegrations,
    isDashboardData: args.isDashboardData,
    isDashboardAgentSandbox: args.isDashboardAgentSandbox,
    isDashboardAgentSecurity: args.isDashboardAgentSecurity,
    isSandboxLocalDetail: args.isSandboxLocalDetail,
    isSandboxModalDetail: args.isSandboxModalDetail,
    isDashboardAgentPrompts: args.isDashboardAgentPrompts,
    isDashboardVoice: args.isDashboardVoice,
    isDashboardAgentRuntime: args.isDashboardAgentRuntime,
    isDashboardMcp: args.isDashboardMcp,
    isLibrary: args.isLibrary,
    isSites: args.isSites
  })

  useAppPanelPersistence({
    sidebarCollapsed: args.sidebarCollapsed,
    filesPanelCollapsed: args.filesPanelCollapsed,
    terminalOpen: args.terminalOpen,
    sidebarPanelRef: args.sidebarPanelRef,
    filesPanelRef: args.filesPanelRef,
    collapsedSidebarSections: args.collapsedSidebarSections,
    sessionId: args.sessionId
  })

  useEffect(() => {
    if (args.runningCount < args.concurrentRunSoftLimit) {
      args.setConnectionLimitDismissed(false)
    }
  }, [
    args.concurrentRunSoftLimit,
    args.runningCount,
    args.setConnectionLimitDismissed
  ])

  useEffect(() => {
    if (args.routeProjectId) {
      args.setProjectScopeId(args.routeProjectId)
    }
  }, [args.locationPathname, args.routeProjectId, args.setProjectScopeId])

  const showChatSkeleton = useAppChatSkeleton(
    args.messagesLoaded,
    args.runActive,
    args.sessionId
  )

  useAppAutoTitle({
    sessionId: args.sessionId,
    runActive: args.runActive,
    sessionTitle: args.sessionTitle,
    titleSource: args.titleSource,
    messages: args.messages,
    client: args.client,
    setSessions: args.setSessions
  })

  return { showChatSkeleton }
}
