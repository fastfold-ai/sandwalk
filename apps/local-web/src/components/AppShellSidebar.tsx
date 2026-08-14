import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  BackendHealth,
  SessionGroup
} from '@sandwalk/agent-ui-core'
import type { RefObject } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import type { NavigateFunction } from 'react-router-dom'

import { AgentSessionSidebar } from '@/components/agents/AgentSessionSidebar'
import {
  type DashboardSection,
  DashboardSidebar
} from '@/components/agents/DashboardSidebar'
import { ShellNavStrip } from '@/components/ShellNavStrip'
import { ResizablePanel } from '@/components/ui/resizable'
import { useSidebarPixelWidth } from '@/hooks/useSidebarPixelWidth'
import type { CreateDraftSession } from '@/lib/draft-agent'
import { type SessionChatState, type TabItemSection } from '@/lib/sessions'
import { cn } from '@/lib/utils'

export type AppShellSidebarProps = {
  sidebarPanelRef: RefObject<ImperativePanelHandle | null>
  isDashboard: boolean
  dashboardSection: DashboardSection
  sidebarUserName: string | null
  sidebarCollapsed: boolean
  setSidebarCollapsed: (
    value: boolean | ((current: boolean) => boolean)
  ) => void
  logoutSession: () => void | Promise<void>
  refreshCloudUserName: () => void | Promise<void>
  health: BackendHealth | null
  backendUrl: string
  projects: AgentProject[]
  activeProjectId: string | null
  sections: TabItemSection[]
  collapsedSidebarSections: Record<string, boolean>
  sessionId: string | null
  chatBySessionId: Record<string, SessionChatState>
  orderedVisibleSessionIds: string[]
  selectedSessionIds: Set<string>
  threadMenuOpenId: string | null
  batchBusy: boolean
  navigate: NavigateFunction
  setProjectScopeId: (
    value: string | null | ((current: string | null) => string | null)
  ) => void
  selectAllProjects: () => void
  selectProjectScope: (projectId: string) => void
  setNewProjectOpen: (value: boolean | ((current: boolean) => boolean)) => void
  setGlobalSearchOpen: (
    value: boolean | ((current: boolean) => boolean)
  ) => void
  loadProjects: () => void | Promise<void>
  createSession: CreateDraftSession
  clearSessionSelection: () => void
  batchMarkReadSelected: () => void
  batchArchiveSelected: () => void | Promise<void>
  batchMoveSelected: (projectId: string | null) => void | Promise<void>
  batchExportSelected: () => void | Promise<void>
  setBatchDeletePending: (
    value: boolean | ((current: boolean) => boolean)
  ) => void
  onBatchSplitView?: () => void
  canBatchSplitView?: boolean
  onSelectTabGroup?: (groupId: string) => void
  onRenameTabGroup?: (group: SessionGroup) => void
  onDissolveTabGroup?: (groupId: string) => void
  onSetTabGroupColor?: (groupId: string, color: string | null) => void
  onGoToChatProject?: (chat: AgentSession) => void
  activeGroupChildId?: string | null
  setTabGroupActiveChat?: (groupId: string, chatId: string) => void
  setCollapsedSidebarSections: (
    value:
      | Record<string, boolean>
      | ((current: Record<string, boolean>) => Record<string, boolean>)
  ) => void
  selectSessionRange: (orderedIds: string[], targetId: string) => void
  toggleSessionSelected: (id: string) => void
  setSelectionAnchorId: (
    value: string | null | ((current: string | null) => string | null)
  ) => void
  openSessionTab: (id: string, scopeKey?: string) => void
  prefetchSessionMessages: (
    id: string,
    signal?: AbortSignal
  ) => void | Promise<void>
  setThreadMenuOpenId: (
    value: string | null | ((current: string | null) => string | null)
  ) => void
  openRenameDialog: (target: AgentSession) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  exportTranscript: (target: AgentSession) => void | Promise<void>
  setDeleteTarget: (
    value:
      | AgentSession
      | null
      | ((current: AgentSession | null) => AgentSession | null)
  ) => void
}

export function AppShellSidebar({
  sidebarPanelRef,
  isDashboard,
  dashboardSection,
  sidebarUserName,
  sidebarCollapsed,
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
  navigate,
  selectAllProjects,
  selectProjectScope,
  setNewProjectOpen,
  setGlobalSearchOpen,
  loadProjects,
  createSession,
  clearSessionSelection,
  batchMarkReadSelected,
  batchArchiveSelected,
  batchMoveSelected,
  batchExportSelected,
  setBatchDeletePending,
  onBatchSplitView,
  canBatchSplitView,
  onSelectTabGroup,
  onRenameTabGroup,
  onDissolveTabGroup,
  onSetTabGroupColor,
  onGoToChatProject,
  activeGroupChildId,
  setTabGroupActiveChat,
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
  const { onSidebarResize } = useSidebarPixelWidth(
    sidebarPanelRef,
    sidebarCollapsed
  )

  return (
    <ResizablePanel
      id="sidebar"
      order={1}
      ref={sidebarPanelRef}
      collapsible
      collapsedSize={0}
      defaultSize={23}
      // Soft % floor; CSS pixel floor + pixel-width hook are the real constraints.
      // Drag past minSize → collapses (hide sidebar).
      minSize={5}
      maxSize={32}
      onCollapse={() => setSidebarCollapsed(true)}
      onExpand={() => setSidebarCollapsed(false)}
      onResize={onSidebarResize}
      // Floor only while open — a persistent min-width blocks collapse to 0.
      className={cn(!sidebarCollapsed && 'min-w-[243px]')}
    >
      <aside className="sandwalk-shell-sidebar bg-sidebar flex h-full flex-col overflow-hidden">
        <div
          className={cn(
            'sandwalk-shell-nav-fade',
            sidebarCollapsed && 'pointer-events-none opacity-0'
          )}
        >
          <ShellNavStrip
            sidebarCollapsed={false}
            surface="sidebar"
            onToggleSidebar={() => setSidebarCollapsed(true)}
          />
        </div>
        {isDashboard ? (
          <DashboardSidebar
            active={dashboardSection}
            userName={sidebarUserName}
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
            sidebarUserName={sidebarUserName}
            health={health}
            backendUrl={backendUrl}
            navigate={navigate}
            onNavigateHome={() => {
              // Home: blank draft composer with All projects selected.
              void createSession(null)
            }}
            onSelectAllProjects={selectAllProjects}
            onSelectProject={selectProjectScope}
            onNewProject={() => setNewProjectOpen(true)}
            onRefreshProjects={loadProjects}
            onOpenGlobalSearch={() => setGlobalSearchOpen(true)}
            onCreateSession={() => createSession(activeProjectId)}
            onClearSessionSelection={clearSessionSelection}
            onBatchMarkReadSelected={batchMarkReadSelected}
            onBatchArchiveSelected={batchArchiveSelected}
            onBatchMoveSelected={batchMoveSelected}
            onBatchExportSelected={batchExportSelected}
            onBatchDeletePending={() => setBatchDeletePending(true)}
            onBatchSplitView={onBatchSplitView}
            canBatchSplitView={canBatchSplitView}
            onSelectTabGroup={onSelectTabGroup}
            onRenameTabGroup={onRenameTabGroup}
            onDissolveTabGroup={onDissolveTabGroup}
            onSetTabGroupColor={onSetTabGroupColor}
            onGoToChatProject={onGoToChatProject}
            activeGroupChildId={activeGroupChildId}
            setTabGroupActiveChat={setTabGroupActiveChat}
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
