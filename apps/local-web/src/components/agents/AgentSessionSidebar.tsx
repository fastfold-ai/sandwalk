import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  BackendHealth
} from '@sandwalk/agent-ui-core'
import {
  Archive,
  Check,
  ChevronDown,
  Download,
  Folder,
  LayoutDashboard,
  MoreHorizontal,
  PanelLeft,
  Pin,
  Search,
  Send,
  Trash2,
  X
} from 'lucide-react'
import type { Dispatch, MouseEvent, SetStateAction } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { ProjectSelector } from '@/components/agents/ProjectSelector'
import { SessionActionsMenu } from '@/components/agents/SessionActionsMenu'
import { SessionStatusIcon } from '@/components/agents/SessionStatusIcon'
import { SidebarUserMenu } from '@/components/agents/SidebarUserMenu'
import { SandwalkMark } from '@/components/SandwalkMark'
import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { groupSessions, relativeTime, type SessionChatState } from '@/lib/sessions'
import { cn } from '@/lib/utils'

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
      {selectedSessionIds.size > 0 ? (
        <div className="border-border/60 mx-2 mb-1 space-y-2 rounded-lg border bg-sidebar-accent/40 px-2.5 py-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-foreground text-[12px] font-medium">
              {selectedSessionIds.size} selected
            </span>
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground inline-flex size-6 items-center justify-center rounded-md"
              aria-label="Clear selection"
              disabled={batchBusy}
              onClick={onClearSessionSelection}
            >
              <X className="size-3.5" />
            </button>
          </div>
          <div className="flex flex-wrap gap-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 px-2 text-[11px]"
              disabled={batchBusy}
              onClick={() => void onBatchArchiveSelected()}
            >
              <Archive className="size-3" />
              Archive
            </Button>
            <ProjectPicker
              projects={projects}
              value={null}
              disabled={batchBusy}
              noneLabel="No project"
              trigger={
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-[11px]"
                  disabled={batchBusy}
                >
                  <Folder className="size-3" />
                  Move
                </Button>
              }
              onChange={projectId => {
                void onBatchMoveSelected(projectId)
              }}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 px-2 text-[11px]"
              disabled={batchBusy}
              onClick={() => void onBatchExportSelected()}
            >
              <Download className="size-3" />
              Export
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive h-7 px-2 text-[11px]"
              disabled={batchBusy}
              onClick={onBatchDeletePending}
            >
              <Trash2 className="size-3" />
              Delete
            </Button>
          </div>
          <p className="text-muted-foreground text-[10px] leading-snug">
            Shift+click range · ⌘/Ctrl+click toggle · Esc clears
          </p>
        </div>
      ) : null}
      <ScrollArea className="flex-1">
        <div className="space-y-3 p-3">
          {sections.length === 0 ? (
            <p className="text-muted-foreground px-1.5 py-2 text-[13px]">
              No Agents Yet
            </p>
          ) : (
            sections.map(section => {
              const collapsed = Boolean(collapsedSidebarSections[section.id])
              return (
                <div key={section.id} className="space-y-1">
                  <button
                    type="button"
                    className="text-muted-foreground/80 hover:text-foreground flex w-full items-center gap-1 rounded-md px-1.5 py-0.5 text-left text-[13px]"
                    aria-expanded={!collapsed}
                    onClick={() =>
                      setCollapsedSidebarSections(current => ({
                        ...current,
                        [section.id]: !current[section.id]
                      }))
                    }
                  >
                    <ChevronDown
                      className={cn(
                        'size-3.5 shrink-0 transition-transform',
                        collapsed && '-rotate-90'
                      )}
                    />
                    <span className="min-w-0 flex-1 truncate">
                      {section.title}
                    </span>
                    <span className="text-muted-foreground/60 shrink-0 text-[11px] tabular-nums">
                      {section.items.length}
                    </span>
                  </button>
                  {!collapsed ? (
                    <ul className="space-y-0.5">
                      {section.items.map(item => {
                        const isSelected = selectedSessionIds.has(item.id)
                        return (
                          <li key={item.id}>
                            <div
                              className={cn(
                                'hover:bg-sidebar-accent/70 group grid grid-cols-[minmax(0,1fr)_2.75rem] items-center rounded px-1.5 py-1.5',
                                item.id === sessionId && 'bg-sidebar-accent',
                                isSelected &&
                                  'bg-sidebar-accent ring-primary/30 ring-1'
                              )}
                            >
                              <button
                                type="button"
                                className="flex min-w-0 items-center gap-1.5 text-left"
                                onClick={(event: MouseEvent<HTMLButtonElement>) => {
                                  if (event.shiftKey) {
                                    event.preventDefault()
                                    selectSessionRange(
                                      orderedVisibleSessionIds,
                                      item.id
                                    )
                                    return
                                  }
                                  if (event.metaKey || event.ctrlKey) {
                                    event.preventDefault()
                                    toggleSessionSelected(item.id)
                                    return
                                  }
                                  if (selectedSessionIds.size > 0) {
                                    onClearSessionSelection()
                                  }
                                  setSelectionAnchorId(item.id)
                                  openSessionTab(item.id)
                                  void prefetchSessionMessages(item.id)
                                  navigate(`/agents/${item.id}`)
                                }}
                              >
                                {isSelected || selectedSessionIds.size > 0 ? (
                                  <span
                                    className={cn(
                                      'grid size-3.5 shrink-0 place-items-center rounded-[4px] border',
                                      isSelected
                                        ? 'border-primary bg-primary text-primary-foreground'
                                        : 'border-muted-foreground/40'
                                    )}
                                    aria-hidden
                                  >
                                    {isSelected ? (
                                      <Check
                                        className="size-2.5"
                                        strokeWidth={3}
                                      />
                                    ) : null}
                                  </span>
                                ) : (
                                  <SessionStatusIcon
                                    status={
                                      chatBySessionId[item.id]?.runActive
                                        ? 'running'
                                        : item.status
                                    }
                                  />
                                )}
                                {item.organizeLabel === 'pinned' ? (
                                  <Pin className="text-muted-foreground/70 size-3 shrink-0" />
                                ) : null}
                                <span className="text-foreground/90 group-hover:text-foreground truncate text-[13px]">
                                  {item.title || 'Untitled'}
                                </span>
                              </button>
                              <div className="relative h-7 w-11 justify-self-end">
                                <span
                                  className={cn(
                                    'text-muted-foreground/70 pointer-events-none absolute inset-0 flex items-center justify-end pr-0.5 text-[11px] transition-opacity',
                                    threadMenuOpenId === item.id
                                      ? 'opacity-0'
                                      : 'opacity-100 group-hover:opacity-0'
                                  )}
                                >
                                  {relativeTime(
                                    item.lastMessageAt || item.updatedAt
                                  )}
                                </span>
                                <Popover
                                  open={threadMenuOpenId === item.id}
                                  onOpenChange={open => {
                                    setThreadMenuOpenId(open ? item.id : null)
                                  }}
                                >
                                  <PopoverTrigger asChild>
                                    <button
                                      type="button"
                                      className={cn(
                                        'text-muted-foreground hover:bg-muted absolute right-0 top-0 inline-flex h-7 w-7 items-center justify-center rounded-md',
                                        threadMenuOpenId === item.id
                                          ? 'opacity-100'
                                          : 'opacity-0 group-hover:opacity-100'
                                      )}
                                      aria-label="Thread options"
                                    >
                                      <MoreHorizontal className="h-4 w-4" />
                                    </button>
                                  </PopoverTrigger>
                                  <PopoverContent
                                    align="start"
                                    className="w-44 p-1.5"
                                  >
                                    <SessionActionsMenu
                                      session={item}
                                      projects={projects}
                                      onRename={() => {
                                        setThreadMenuOpenId(null)
                                        openRenameDialog(item)
                                      }}
                                      onTogglePin={() => {
                                        setThreadMenuOpenId(null)
                                        void updateSession(item, {
                                          organizeLabel:
                                            item.organizeLabel === 'pinned'
                                              ? null
                                              : 'pinned'
                                        })
                                      }}
                                      onMoveToProject={projectId => {
                                        setThreadMenuOpenId(null)
                                        void updateSession(item, { projectId })
                                      }}
                                      onExport={() => {
                                        setThreadMenuOpenId(null)
                                        void exportTranscript(item)
                                      }}
                                      onInspect={() => {
                                        setThreadMenuOpenId(null)
                                        navigate(
                                          `/agents/${item.id}?inspect=1`
                                        )
                                      }}
                                      onArchive={() => {
                                        setThreadMenuOpenId(null)
                                        const nextLabel =
                                          item.organizeLabel === 'archive'
                                            ? null
                                            : 'archive'
                                        void updateSession(item, {
                                          organizeLabel: nextLabel
                                        })
                                        if (nextLabel === 'archive') {
                                          setCollapsedSidebarSections(
                                            current => ({
                                              ...current,
                                              archive: false
                                            })
                                          )
                                        }
                                      }}
                                      onDelete={() => {
                                        setThreadMenuOpenId(null)
                                        setDeleteTarget(item)
                                      }}
                                    />
                                  </PopoverContent>
                                </Popover>
                              </div>
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                  ) : null}
                </div>
              )
            })
          )}
        </div>
      </ScrollArea>
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
