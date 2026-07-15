import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  BackendHealth
} from '@sandwalk/agent-ui-core'
import {
  Folder,
  LayoutDashboard,
  PanelLeft,
  Search,
  Send
} from 'lucide-react'
import type { Dispatch, SetStateAction } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { ProjectSelector } from '@/components/agents/ProjectSelector'
import { SidebarUserMenu } from '@/components/agents/SidebarUserMenu'
import { SandwalkMark } from '@/components/SandwalkMark'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { groupSessions, type SessionChatState } from '@/lib/sessions'
import { cn } from '@/lib/utils'

import { SidebarBatchBar } from './session-sidebar/sidebar-batch-bar'
import { SidebarSessionList } from './session-sidebar/sidebar-session-list'

type SessionSection = ReturnType<typeof groupSessions>[number]

type AgentSessionSidebarProps = {
  projects: AgentProject[]
  activeProjectId: string | null
  sections: SessionSection[]
  collapsedSidebarSections: Record<string, boolean>
  sessionId: string | null
  chatBySessionId: Record<string, SessionChatState>
  orderedVisibleSessionIds: string[]
  selectedSessionIds: Set<string>
  threadMenuOpenId: string | null
  batchBusy: boolean
  canShowFilesPanel: boolean
  filesPanelCollapsed: boolean
  sidebarUserName: string | null
  health: BackendHealth | null
  backendUrl: string | null
  navigate: NavigateFunction
  onNavigateHome: () => void
  onSelectAllProjects: () => void
  onSelectProject: (projectId: string) => void
  onOpenProjectSettings: () => void
  onNewProject: () => void
  onOpenGlobalSearch: () => void
  onCollapseSidebar: () => void
  onCreateSession: () => void
  onToggleFilesPanel: () => void
  onClearSessionSelection: () => void
  onBatchArchiveSelected: () => void | Promise<void>
  onBatchMoveSelected: (projectId: string | null) => void | Promise<void>
  onBatchExportSelected: () => void | Promise<void>
  onBatchDeletePending: () => void
  setCollapsedSidebarSections: Dispatch<SetStateAction<Record<string, boolean>>>
  selectSessionRange: (orderedIds: string[], targetId: string) => void
  toggleSessionSelected: (targetId: string) => void
  setSelectionAnchorId: (targetId: string) => void
  openSessionTab: (sessionId: string) => void
  prefetchSessionMessages: (sessionId: string) => void | Promise<void>
  setThreadMenuOpenId: Dispatch<SetStateAction<string | null>>
  openRenameDialog: (target: AgentSession) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  exportTranscript: (target: AgentSession) => void | Promise<void>
  setDeleteTarget: Dispatch<SetStateAction<AgentSession | null>>
  onLogout: () => void | Promise<void>
  onRefreshUser: () => void | Promise<void>
}

export function AgentSessionSidebar({
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
  sidebarUserName,
  health,
  backendUrl,
  navigate,
  onNavigateHome,
  onSelectAllProjects,
  onSelectProject,
  onOpenProjectSettings,
  onNewProject,
  onOpenGlobalSearch,
  onCollapseSidebar,
  onCreateSession,
  onToggleFilesPanel,
  onClearSessionSelection,
  onBatchArchiveSelected,
  onBatchMoveSelected,
  onBatchExportSelected,
  onBatchDeletePending,
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
  setDeleteTarget,
  onLogout,
  onRefreshUser
}: AgentSessionSidebarProps) {
  return (
    <>
      <div className="shrink-0 p-3">
        <div className="mb-2 flex items-center gap-1">
          <button
            type="button"
            className="hover:bg-sidebar-accent/70 inline-flex size-8 shrink-0 items-center justify-center rounded-md"
            onClick={onNavigateHome}
            aria-label="Home"
            title="Home"
          >
            <SandwalkMark className="h-5 w-5" />
          </button>
          <ProjectSelector
            projects={projects}
            value={activeProjectId}
            onSelectAll={onSelectAllProjects}
            onSelectProject={onSelectProject}
            onOpenSettings={onOpenProjectSettings}
            onNewProject={onNewProject}
          />
          <div className="min-w-0 flex-1" />
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 shrink-0"
                  onClick={onOpenGlobalSearch}
                  aria-label="Search"
                >
                  <Search className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">Search ⌘K</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <Button
            variant="ghost"
            size="icon"
            className="size-8 shrink-0"
            onClick={onCollapseSidebar}
            aria-label="Hide sidebar"
          >
            <PanelLeft className="size-4" />
          </Button>
        </div>
        <button
          type="button"
          className="text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground flex w-full items-center justify-between rounded-md px-2 py-1.5 text-[13px]"
          onClick={() => void onCreateSession()}
        >
          <span className="inline-flex items-center gap-2">
            <Send className="size-3.5" />
            New Agent
          </span>
          <span className="text-muted-foreground/70 text-[11px]">⌘N</span>
        </button>
        {canShowFilesPanel ? (
          <button
            type="button"
            className={cn(
              'mt-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[13px]',
              !filesPanelCollapsed
                ? 'bg-sidebar-accent text-foreground'
                : 'text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground'
            )}
            onClick={onToggleFilesPanel}
          >
            <Folder className="size-3.5" />
            Files
          </button>
        ) : null}
        <button
          type="button"
          className="text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground mt-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[13px]"
          onClick={() => navigate('/dashboard')}
        >
          <LayoutDashboard className="size-3.5" />
          Dashboard
        </button>
      </div>
      <SidebarBatchBar
        selectedCount={selectedSessionIds.size}
        batchBusy={batchBusy}
        projects={projects}
        onClearSelection={onClearSessionSelection}
        onBatchArchive={() => void onBatchArchiveSelected()}
        onBatchMove={projectId => void onBatchMoveSelected(projectId)}
        onBatchExport={() => void onBatchExportSelected()}
        onBatchDelete={onBatchDeletePending}
      />
      <SidebarSessionList
        sections={sections}
        collapsedSidebarSections={collapsedSidebarSections}
        sessionId={sessionId}
        chatBySessionId={chatBySessionId}
        orderedVisibleSessionIds={orderedVisibleSessionIds}
        selectedSessionIds={selectedSessionIds}
        threadMenuOpenId={threadMenuOpenId}
        projects={projects}
        navigate={navigate}
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
        onClearSessionSelection={onClearSessionSelection}
      />
      <div className="shrink-0 p-2">
        <SidebarUserMenu
          userName={sidebarUserName}
          onLogout={onLogout}
          onRefreshUser={onRefreshUser}
          backendVersion={health?.version ?? null}
          backendUrl={backendUrl}
          connected={Boolean(health)}
        />
      </div>
    </>
  )
}
