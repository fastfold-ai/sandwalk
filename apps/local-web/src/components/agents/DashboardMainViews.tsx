import { Suspense } from 'react'

import {
  DashboardPageSkeleton
} from '@/components/agents/PageSkeletons'
import { AppErrorBoundary } from '@/components/AppErrorBoundary'

import { DashboardMainIntegrationsPanel } from './dashboard-main-integrations-panel'
import { DashboardMainMcpPanel } from './dashboard-main-mcp-panel'
import { DashboardMainOverviewPanel } from './dashboard-main-overview-panel'
import { DashboardMainSettingsPanels } from './dashboard-main-settings-panels'
import { DashboardMainSkillsPanel } from './dashboard-main-skills-panel'
import {
  DashboardMainHomePanel,
  DashboardMainSpecialistsPanel
} from './dashboard-main-specialists-home-panel'
import { LibraryView } from './dashboard-main-views-lazy'
export type { DashboardMainViewsProps } from './dashboard-main-views-types'
import type { DashboardMainViewsProps } from './dashboard-main-views-types'

export function DashboardMainViews(props: DashboardMainViewsProps) {
  const {
    location,
    dashboardSection,
    dashboardSkeletonKind,
    isDashboardOverview,
    isSkills,
    isIntegrations,
    isDashboardMcp,
    isDashboardSpecialists,
    isHome,
    isLibrary,
    isProjectHome,
    client,
    navigate,
    activeProjectId,
    pendingAttachmentsRef,
    openSessionTab,
    loadSessions
  } = props

  const settingsPanel = DashboardMainSettingsPanels(props)

  return (
    <Suspense
      fallback={<DashboardPageSkeleton kind={dashboardSkeletonKind} />}
    >
      <div className="flex min-h-0 flex-1 flex-col">
        <AppErrorBoundary
          variant="panel"
          resetKeys={[dashboardSection, location.pathname]}
        >
          {isDashboardOverview ? (
            <DashboardMainOverviewPanel {...props} />
          ) : settingsPanel ? (
            settingsPanel
          ) : isSkills ? (
            <DashboardMainSkillsPanel {...props} />
          ) : isIntegrations ? (
            <DashboardMainIntegrationsPanel {...props} />
          ) : isDashboardMcp ? (
            <DashboardMainMcpPanel {...props} />
          ) : isDashboardSpecialists ? (
            <DashboardMainSpecialistsPanel {...props} />
          ) : isLibrary ? (
            <LibraryView
              client={client}
              navigate={navigate}
              projectId={activeProjectId}
              pendingAttachmentsRef={pendingAttachmentsRef}
              openSessionTab={openSessionTab}
              loadSessions={loadSessions}
            />
          ) : isHome || isProjectHome ? (
            <DashboardMainHomePanel {...props} />
          ) : null}
        </AppErrorBoundary>
      </div>
    </Suspense>
  )
}
