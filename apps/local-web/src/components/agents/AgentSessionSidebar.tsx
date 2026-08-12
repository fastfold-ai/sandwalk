import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  BackendHealth
} from '@sandwalk/agent-ui-core'
import {
  Globe2,
  Home,
  LayoutDashboard,
  LibraryBig,
  Search,
  Send
} from 'lucide-react'
import type { Dispatch, SetStateAction } from 'react'
import { type NavigateFunction, useLocation } from 'react-router-dom'

import { ProjectSelector } from '@/components/agents/ProjectSelector'
import { SidebarUserMenu } from '@/components/agents/SidebarUserMenu'
import { DesktopDragRegion } from '@/components/DesktopDragRegion'
import { SandwalkMark } from '@/components/SandwalkMark'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { type SessionChatState, type TabItemSection } from '@/lib/sessions'
import { cn } from '@/lib/utils'

import { SidebarBatchBar } from './session-sidebar/sidebar-batch-bar'
import { SidebarSessionList } from './session-sidebar/sidebar-session-list'

type SessionSection = TabItemSection

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
  sidebarUserName: string | null
  health: BackendHealth | null
  backendUrl: string | null
  navigate: NavigateFunction
  onNavigateHome: () => void
  onSelectAllProjects: () => void
  onSelectProject: (projectId: string) => void
  onOpenProjectSettings: () => void
  onNewProject: () => void
  onRefreshProjects?: () => void | Promise<void>
  onOpenGlobalSearch: () => void
  onCreateSession: () => void
  onClearSessionSelection: () => void
  onBatchMarkReadSelected: () => void
  onBatchArchiveSelected: () => void | Promise<void>
  onBatchMoveSelected: (projectId: string | null) => void | Promise<void>
  onBatchExportSelected: () => void | Promise<void>
  onBatchDeletePending: () => void
  onBatchSplitView?: () => void
  canBatchSplitView?: boolean
  onSelectTabGroup?: (groupId: string) => void
  onDissolveTabGroup?: (groupId: string) => void
  activeGroupChildId?: string | null
  setTabGroupActiveChat?: (groupId: string, chatId: string) => void
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
  sidebarUserName,
  health,
  backendUrl,
  navigate,
  onNavigateHome,
  onSelectAllProjects,
  onSelectProject,
  onOpenProjectSettings,
  onNewProject,
  onRefreshProjects,
  onOpenGlobalSearch,
  onCreateSession,
  onClearSessionSelection,
  onBatchMarkReadSelected,
  onBatchArchiveSelected,
  onBatchMoveSelected,
  onBatchExportSelected,
  onBatchDeletePending,
  onBatchSplitView,
  canBatchSplitView,
  onSelectTabGroup,
  onDissolveTabGroup,
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
  setDeleteTarget,
  onLogout,
  onRefreshUser
}: AgentSessionSidebarProps) {
  const location = useLocation()
  const isLibrary =
    location.pathname === '/library' ||
    location.pathname.startsWith('/library/')
  const isSites =
    location.pathname === '/sites' || location.pathname.startsWith('/sites/')
  const isProjectHome =
    Boolean(activeProjectId) &&
    location.pathname === `/projects/${activeProjectId}`
  return (
    <>
      <div className="sandwalk-sidebar-chrome shrink-0 px-3 pb-2 pt-0.5">
        {/* Same px-2.5 as nav rows; mark is larger but left-aligned to the icon column. */}
        <div className="mb-2 flex items-center gap-1.5 px-2.5">
          <button
            type="button"
            className="hover:bg-sidebar-accent/50 -ml-2 inline-flex size-8 shrink-0 items-center justify-center rounded-md"
            onClick={onNavigateHome}
            aria-label="Home"
            title="Home"
          >
            <SandwalkMark className="size-5" />
          </button>
          <ProjectSelector
            projects={projects}
            value={activeProjectId}
            onSelectAll={onSelectAllProjects}
            onSelectProject={onSelectProject}
            onOpenSettings={onOpenProjectSettings}
            onNewProject={onNewProject}
            onRefresh={onRefreshProjects}
          />
          <DesktopDragRegion className="min-h-8 min-w-0 flex-1 self-stretch" />
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-foreground size-6 shrink-0"
                  onClick={onOpenGlobalSearch}
                  aria-label="Search"
                >
                  <Search className="size-3" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">Search ⌘K</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        {activeProjectId ? (
          <button
            type="button"
            className={cn(
              'mb-0.5 flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-[13px]',
              isProjectHome
                ? 'bg-sidebar-accent/55 text-foreground'
                : 'text-foreground/80 hover:bg-sidebar-accent/50 hover:text-foreground'
            )}
            onClick={() => navigate(`/projects/${activeProjectId}`)}
          >
            <Home className="size-3.5" />
            Project Home
          </button>
        ) : null}
        <button
          type="button"
          className="text-foreground/80 hover:bg-sidebar-accent/50 hover:text-foreground flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-[13px]"
          onClick={() => void onCreateSession()}
        >
          <span className="inline-flex items-center gap-2">
            <Send className="size-3.5" />
            New Agent
          </span>
          <span className="text-muted-foreground/80 text-[11px]">⌘N</span>
        </button>
        <button
          type="button"
          className="text-foreground/80 hover:bg-sidebar-accent/50 hover:text-foreground mt-0.5 flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-[13px]"
          onClick={() => navigate('/dashboard')}
        >
          <LayoutDashboard className="size-3.5" />
          Dashboard
        </button>
        <button
          type="button"
          className={cn(
            'mt-0.5 flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-[13px]',
            isLibrary
              ? 'bg-sidebar-accent/55 text-foreground'
              : 'text-foreground/80 hover:bg-sidebar-accent/50 hover:text-foreground'
          )}
          onClick={() => navigate('/library')}
        >
          <LibraryBig className="size-3.5" />
          Library
        </button>
        <button
          type="button"
          className={cn(
            'mt-0.5 flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-[13px]',
            isSites
              ? 'bg-sidebar-accent/55 text-foreground'
              : 'text-foreground/80 hover:bg-sidebar-accent/50 hover:text-foreground'
          )}
          onClick={() => navigate('/sites')}
        >
          <Globe2 className="size-3.5" />
          Sites
        </button>
      </div>
      {/* SidebarGroupsRow removido: los grupos ahora viven como items
          dentro de las secciones (Pinned/Today/…) con chevron collapsible
          en `SidebarSessionList`, mismo nivel que un chat. */}
      <SidebarSessionList
        sections={sections}
        scopeKey={activeProjectId}
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
        onSelectTabGroup={onSelectTabGroup}
        onDissolveTabGroup={onDissolveTabGroup}
        activeGroupChildId={activeGroupChildId}
        setTabGroupActiveChat={setTabGroupActiveChat}
      />
      <div className="relative shrink-0 p-2">
        <SidebarBatchBar
          selectedCount={selectedSessionIds.size}
          batchBusy={batchBusy}
          projects={projects}
          onClearSelection={onClearSessionSelection}
          onBatchMarkRead={onBatchMarkReadSelected}
          onBatchArchive={() => void onBatchArchiveSelected()}
          onBatchMove={projectId => void onBatchMoveSelected(projectId)}
          onBatchExport={() => void onBatchExportSelected()}
          onBatchDelete={onBatchDeletePending}
          onBatchSplitView={onBatchSplitView}
          canSplitView={canBatchSplitView}
        />
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

