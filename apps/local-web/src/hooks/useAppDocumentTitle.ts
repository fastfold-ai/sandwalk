import { useEffect } from 'react'

import {
  isLocalBackendUrl,
  readStoredBackendUrl
} from '@/lib/backend-url'
import {
  isTauri,
  persistDesktopSnapshotId,
  readDesktopSnapshotId,
  setDesktopWindowTitle,
  upsertDesktopWindowSnapshot
} from '@/lib/desktop'
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
  isDashboardAppearance: boolean
  isDashboardModels: boolean
  isDashboardTools: boolean
  isDashboardDoctor: boolean
  isDashboardBench: boolean
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
  isDashboardAgentSecurity: boolean
  isDashboardMcp: boolean
  isLibrary: boolean
  isSites: boolean
}

function pageLabel(args: DocumentTitleArgs): string {
  if (args.onOnboardingPath) {
    return `Onboarding ${onboardingStepDef(args.onboardingStep).title}`
  }
  if (args.sessionTitle?.trim()) return args.sessionTitle.trim()
  if (args.isLibrary) return 'Library'
  if (args.isSites) return 'Sites'
  if (args.isDashboardOverview) return 'Dashboard'
  if (args.isDashboardStatus) return 'Status'
  if (args.isDashboardGeneral) return 'General'
  if (args.isDashboardAppearance) return 'Appearance'
  if (args.isDashboardModels) return 'Models'
  if (args.isDashboardTools) return 'Tools'
  if (args.isDashboardDoctor) return 'Doctor'
  if (args.isDashboardBench) {
    if (typeof window !== 'undefined') {
      const path = window.location.pathname
      if (path.includes('/compare')) return 'Compare · Benchmarking'
      const match = path.match(/\/bench\/([^/]+)/)
      if (match?.[1] && match[1] !== 'compare') return 'Bench result'
    }
    return 'Benchmarking'
  }
  if (args.isDashboardStorage) return 'Storage'
  if (args.isDashboardEnvironment) return 'Environment'
  if (args.isSkills) return 'Skills'
  if (args.isDashboardSpecialists) return 'Specialists'
  if (args.isIntegrations) {
    if (args.activeIntegration?.name) {
      return `${args.activeIntegration.name} · Integrations`
    }
    return 'Integrations'
  }
  if (args.isDashboardData) return 'Datasets'
  if (args.isSandboxLocalDetail) return 'Local Sandbox'
  if (args.isSandboxModalDetail) return 'Modal Sandbox'
  if (args.isDashboardAgentSandbox) return 'Sandbox'
  if (args.isDashboardAgentPrompts) return 'Context'
  if (args.isDashboardVoice) return 'Voice'
  if (args.isDashboardAgentRuntime) return 'Runtime'
  if (args.isDashboardAgentSecurity) return 'Security'
  if (args.isDashboardMcp) return 'MCP'
  if (args.activeProject?.name) return args.activeProject.name
  return 'Sandwalk'
}

/** Host:port for remote backends — used in Dock window titles. */
function remoteHostSuffix(backendUrl: string): string | null {
  if (isLocalBackendUrl(backendUrl)) return null
  try {
    const parsed = new URL(backendUrl)
    const host = parsed.hostname || 'remote'
    return parsed.port ? `${host}:${parsed.port}` : host
  } catch {
    return null
  }
}

/**
 * Browser tab title + native window title (Dock / Mission Control).
 * Cursor-style: `hi again friend` locally, `hi again friend — host:port` remote.
 */
export function useAppDocumentTitle(args: DocumentTitleArgs) {
  useEffect(() => {
    const label = pageLabel(args)
    const backendUrl = readStoredBackendUrl()
    const remote = remoteHostSuffix(backendUrl)
    document.title = `${label} · sandwalk`

    if (!isTauri()) return
    // Dock / Mission Control: session or page title; remote adds host:port.
    const dockTitle = remote ? `${label} — ${remote}` : label
    void setDesktopWindowTitle(dockTitle)
    // Open Recent: debounce snapshot writes (title can change often while streaming).
    const route =
      typeof window !== 'undefined'
        ? `${window.location.pathname}${window.location.search}`
        : '/'
    const timer = window.setTimeout(() => {
      void upsertDesktopWindowSnapshot({
        snapshotId: readDesktopSnapshotId(),
        url: backendUrl,
        route: route || '/',
        title: dockTitle
      })
        .then(id => persistDesktopSnapshotId(id))
        .catch(() => {
          // Native bridge unavailable during early boot.
        })
    }, 400)
    return () => window.clearTimeout(timer)
  }, [
    args.activeIntegration,
    args.activeProject,
    args.isDashboardDoctor,
    args.isDashboardBench,
    args.isDashboardStorage,
    args.isDashboardEnvironment,
    args.isDashboardAgentSandbox,
    args.isDashboardAgentPrompts,
    args.isDashboardVoice,
    args.isDashboardAgentRuntime,
    args.isDashboardAgentSecurity,
    args.isSandboxLocalDetail,
    args.isSandboxModalDetail,
    args.isDashboardMcp,
    args.isLibrary,
    args.isSites,
    args.isDashboardOverview,
    args.isDashboardStatus,
    args.isDashboardGeneral,
    args.isDashboardAppearance,
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
