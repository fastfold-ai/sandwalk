import type { RefObject } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import type { NavigateFunction } from 'react-router-dom'

import { AgentSessionSidebar } from '@/components/agents/AgentSessionSidebar'
import {
  type DashboardSection,
  DashboardSidebar
} from '@/components/agents/DashboardSidebar'
import { ResizablePanel } from '@/components/ui/resizable'
import { type SessionChatState, groupSessions } from '@/lib/sessions'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, AgentSession, BackendHealth } from '@sandwalk/agent-ui-core'

export type AppShellSidebarProps = {
  sidebarPanelRef: RefObject<ImperativePanelHandle | null>
  isDashboard: boolean
  dashboardSection: DashboardSection
  sidebarUserName: string | null
  setSidebarCollapsed: (value: boolean | ((current: boolean) => boolean)) => void
  logoutSession: () => void | Promise<void>
  refreshCloudUserName: () => void | Promise<void>
  health: BackendHealth | null
  backendUrl: string
  projects: AgentProject[]
  activeProjectId: string | null
  sections: ReturnType<typeof groupSessions>
  collapsedSidebarSections: Record<string, boolean>
  sessionId: string | null
  chatBySessionId: Record<string, SessionChatState>
  orderedVisibleSessionIds: string[]
  selectedSessionIds: Set<string>
  threadMenuOpenId: string | null
  batchBusy: boolean
  canShowFilesPanel: boolean
  filesPanelCollapsed: boolean
  navigate: NavigateFunction
  setProjectScopeId: (value: string | null | ((current: string | null) => string | null)) => void
  selectAllProjects: () => void
  selectProjectScope: (projectId: string) => void
  setProjectSettingsOpen: (value: boolean | ((current: boolean) => boolean)) => void
  setNewProjectOpen: (value: boolean | ((current: boolean) => boolean)) => void
  setGlobalSearchOpen: (value: boolean | ((current: boolean) => boolean)) => void
  createSession: (projectId?: string | null) => Promise<void>
  setFilesPanelCollapsed: (value: boolean | ((current: boolean) => boolean)) => void
  clearSessionSelection: () => void
  batchArchiveSelected: () => void | Promise<void>
  batchMoveSelected: (projectId: string | null) => void | Promise<void>
  batchExportSelected: () => void | Promise<void>
  setBatchDeletePending: (value: boolean | ((current: boolean) => boolean)) => void
  setCollapsedSidebarSections: (
    value:
      | Record<string, boolean>
      | ((current: Record<string, boolean>) => Record<string, boolean>)
  ) => void
  selectSessionRange: (orderedIds: string[], targetId: string) => void
  toggleSessionSelected: (id: string) => void
  setSelectionAnchorId: (value: string | null | ((current: string | null) => string | null)) => void
  openSessionTab: (id: string, scopeKey?: string) => void
  prefetchSessionMessages: (id: string, signal?: AbortSignal) => void | Promise<void>
  setThreadMenuOpenId: (value: string | null | ((current: string | null) => string | null)) => void
  openRenameDialog: (target: AgentSession) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  exportTranscript: (target: AgentSession) => void | Promise<void>
  setDeleteTarget: (value: AgentSession | null | ((current: AgentSession | null) => AgentSession | null)) => void
}

export function AppShellSidebar({
  sidebarPanelRef,
  isDashboard,
  dashboardSection,
  sidebarUserName,
  setSidebarCollapsed,
  logoutSession,
  refreshCloudUserName,
  health,
  backendUrl,
  projects,
  activeProjectId,
  sections,
  collapsedSidebarSections,
  sessionId,
  chatBySessionId,
  orderedVisibleSessionIds,
  selectedSessionIds,
  threadMenuOpenId,
  batchBusy,
  canShowFilesPanel,
  filesPanelCollapsed,
  navigate,
  setProjectScopeId,
  selectAllProjects,
  selectProjectScope,
  setProjectSettingsOpen,
  setNewProjectOpen,
  setGlobalSearchOpen,
  createSession,
  setFilesPanelCollapsed,
  clearSessionSelection,
  batchArchiveSelected,
  batchMoveSelected,
  batchExportSelected,
  setBatchDeletePending,
  setCollapsedSidebarSections,
  selectSessionRange,
  toggleSessionSelected,
  setSelectionAnchorId,
  openSessionTab,
  prefetchSessionMessages,
  setThreadMenuOpenId,
  openRenameDialog,
  updateSession,
  exportTranscript,
  setDeleteTarget
}: AppShellSidebarProps) {
  return (
    <ResizablePanel
      id="sidebar"
      order={1}
      ref={sidebarPanelRef}
      collapsible
      collapsedSize={0}
      defaultSize={18}
      minSize={12}
      maxSize={30}
      onCollapse={() => setSidebarCollapsed(true)}
      onExpand={() => setSidebarCollapsed(false)}
      className="min-w-0"
    >
      <aside className="bg-sidebar flex h-full flex-col overflow-hidden">
        {isDashboard ? (
          <DashboardSidebar
            active={dashboardSection}
            userName={sidebarUserName}
            onCollapse={() => setSidebarCollapsed(true)}
            onLogout={logoutSession}
            onRefreshUser={refreshCloudUserName}
            backendVersion={health?.version ?? null}
            backendUrl={backendUrl}
            connected={Boolean(health)}
          />
        ) : (
          <AgentSessionSidebar
            projects={projects}
            activeProjectId={activeProjectId}
            sections={sections}
            collapsedSidebarSections={collapsedSidebarSections}
            sessionId={sessionId}
            chatBySessionId={chatBySessionId}
            orderedVisibleSessionIds={orderedVisibleSessionIds}
            selectedSessionIds={selectedSessionIds}
            threadMenuOpenId={threadMenuOpenId}
            batchBusy={batchBusy}
            canShowFilesPanel={canShowFilesPanel}
            filesPanelCollapsed={filesPanelCollapsed}
            sidebarUserName={sidebarUserName}
            health={health}
            backendUrl={backendUrl}
            navigate={navigate}
            onNavigateHome={() => {
              setProjectScopeId(null)
              navigate('/')
            }}
            onSelectAllProjects={selectAllProjects}
            onSelectProject={selectProjectScope}
            onOpenProjectSettings={() => setProjectSettingsOpen(true)}
            onNewProject={() => setNewProjectOpen(true)}
            onOpenGlobalSearch={() => setGlobalSearchOpen(true)}
            onCollapseSidebar={() => setSidebarCollapsed(true)}
            onCreateSession={() => createSession(activeProjectId)}
            onToggleFilesPanel={() =>
              setFilesPanelCollapsed(current => !current)
            }
            onClearSessionSelection={clearSessionSelection}
            onBatchArchiveSelected={batchArchiveSelected}
            onBatchMoveSelected={batchMoveSelected}
            onBatchExportSelected={batchExportSelected}
            onBatchDeletePending={() => setBatchDeletePending(true)}
            setCollapsedSidebarSections={setCollapsedSidebarSections}
            selectSessionRange={selectSessionRange}
            toggleSessionSelected={toggleSessionSelected}
            setSelectionAnchorId={setSelectionAnchorId}
            openSessionTab={openSessionTab}
            prefetchSessionMessages={prefetchSessionMessages}
            setThreadMenuOpenId={setThreadMenuOpenId}
            openRenameDialog={openRenameDialog}
            updateSession={updateSession}
            exportTranscript={exportTranscript}
            setDeleteTarget={setDeleteTarget}
            onLogout={logoutSession}
            onRefreshUser={refreshCloudUserName}
          />
        )}
      </aside>
    </ResizablePanel>
  )
}
