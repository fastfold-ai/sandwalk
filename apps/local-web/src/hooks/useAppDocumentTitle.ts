import { useEffect, useState } from 'react'

import { isLocalBackendUrl, readStoredBackendUrl } from '@/lib/backend-url'
import {
  isTauri,
  persistDesktopSnapshotId,
  readDesktopSnapshotId,
  setDesktopWindowTitle,
  upsertDesktopWindowSnapshot
} from '@/lib/desktop'
import { onboardingStepDef } from '@/lib/onboarding'
import {
  readCachedRemoteHostname,
  remoteDockSuffix,
  resolveRemoteHostname
} from '@/lib/remote-hostname'

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

/**
 * Browser tab title + native window title (Dock / Mission Control).
 * Local: `Hello`. Remote Dock: `Hello — Julios-Mac-mini`.
 * Open Recent stores page title + hostname separately (hostname · IP in the menu).
 */
export function useAppDocumentTitle(args: DocumentTitleArgs) {
  const backendUrl = readStoredBackendUrl()
  const [hostname, setHostname] = useState<string | null>(() =>
    readCachedRemoteHostname(backendUrl)
  )

  useEffect(() => {
    let cancelled = false
    void resolveRemoteHostname(backendUrl).then(name => {
      if (!cancelled && name) setHostname(name)
    })
    return () => {
      cancelled = true
    }
  }, [backendUrl])

  useEffect(() => {
    const label = pageLabel(args)
    const remote = remoteDockSuffix(backendUrl, hostname)
    document.title = `${label} · sandwalk`

    if (!isTauri()) return
    // Dock: session title + hostname (not IP when discover is available).
    const dockTitle = remote ? `${label} — ${remote}` : label
    void setDesktopWindowTitle(dockTitle)
    const route =
      typeof window !== 'undefined'
        ? `${window.location.pathname}${window.location.search}`
        : '/'
    const timer = window.setTimeout(() => {
      const path = route || '/'
      const genericLocal =
        isLocalBackendUrl(backendUrl) &&
        (path === '/' || path === '') &&
        (!label.trim() || label.trim() === 'Sandwalk')
      // Don't spam Open Recent with blank local home windows.
      if (genericLocal) return
      void upsertDesktopWindowSnapshot({
        snapshotId: readDesktopSnapshotId(),
        url: backendUrl,
        route: path,
        // Page title only — native Open Recent appends hostname · IP.
        title: label,
        hostname: hostname
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
    args.sessionTitle,
    backendUrl,
    hostname
  ])
}
