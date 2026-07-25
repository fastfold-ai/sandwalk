import { useEffect } from 'react'

import { onboardingStepDef } from '@/lib/onboarding'

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
  isDashboardVoice: boolean
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
      document.title = `Context · ${base}`
      return
    }
    if (args.isDashboardVoice) {
      document.title = `Voice · ${base}`
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
    args.isDashboardVoice,
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
