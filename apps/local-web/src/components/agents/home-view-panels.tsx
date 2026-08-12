import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Folder,
  MoreHorizontal,
  Pin,
  Plus,
  Settings,
  Trash2
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { ProjectMark } from '@/components/agents/ProjectMark'
import {
  AddWidgetButton,
  catalogEntry,
  createDefaultProjectHomeLayout,
  normalizeProjectHomeLayout,
  WidgetBoard,
  type WidgetType
} from '@/components/agents/widget-board'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { relativeTime } from '@/lib/sessions'

export function HomeEmptySessions({
  onCreateSession,
  projectId
}: {
  onCreateSession: (projectId: string | null) => void
  projectId: string | null
}) {
  return (
    <div className="flex flex-col items-center px-4 py-14 text-center">
      <AuraIconPulse className="text-muted-foreground/40 mb-4 h-10 w-10" />
      <p className="text-muted-foreground text-sm">No sessions here</p>
      <Button
        variant="ghost"
        className="mt-2"
        onClick={() => onCreateSession(projectId)}
      >
        <Plus className="size-3.5" />
        New Agent
      </Button>
    </div>
  )
}


export function HomeProjectView({
  project,
  client,
  onOpenProjectSettings,
  onDeleteProject
}: {
  project: AgentProject
  client: LocalAgentClient
  onCreateSession?: (projectId: string | null) => void
  onOpenProjectSettings: () => void
  onDeleteProject: (project: AgentProject) => void
}) {
  const [confirmRemove, setConfirmRemove] = useState(false)
  const sessionCount = project.sessionCount || 0
  const sessionLabel =
    sessionCount === 1 ? '1 session' : `${sessionCount} sessions`
  const folderPath = project.folderPath?.trim() || ''
  const [layout, setLayout] = useState(() =>
    normalizeProjectHomeLayout(project.homeLayout)
  )
  const presentTypes = useMemo(
    () => new Set(layout.widgets.map(widget => widget.type)),
    [layout.widgets]
  )

  useEffect(() => {
    const next = normalizeProjectHomeLayout(project.homeLayout)
    setLayout(next)
    // Persist seed reseeds / catalog migrations.
    const prevVersion = project.homeLayout?.version || 0
    const prevTypes = (project.homeLayout?.widgets || []).map(w => w.type)
    const nextTypes = next.widgets.map(w => w.type)
    const migrated =
      prevVersion !== next.version || prevTypes.join('|') !== nextTypes.join('|')
    if (migrated) {
      void client.updateProject(project.id, { homeLayout: next })
    }
  }, [client, project.homeLayout, project.id, project.updatedAt])

  const persistLayout = async (
    next: ReturnType<typeof createDefaultProjectHomeLayout>
  ) => {
    setLayout(next)
    await client.updateProject(project.id, { homeLayout: next })
  }

  const addWidget = (type: WidgetType) => {
    const entry = catalogEntry(type)
    if (!entry) return
    void persistLayout({
      ...layout,
      widgets: [
        ...layout.widgets,
        {
          id: crypto.randomUUID(),
          type,
          size: entry.defaultSize
        }
      ]
    })
  }

  const resetLayout = () => {
    void persistLayout(createDefaultProjectHomeLayout())
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Same height chain as BenchView — Radix ScrollArea needs a bounded flex child. */}
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto w-full max-w-6xl px-6 pt-8 pb-8 md:px-10">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-1.5">
              <div className="flex min-w-0 items-center gap-3">
                <ProjectMark
                  icon={project.icon}
                  color={project.color}
                  className="size-9 shrink-0"
                  iconClassName="size-4"
                />
                <h2 className="truncate text-xl font-semibold">
                  {project.name}
                </h2>
              </div>
              <button
                type="button"
                onClick={onOpenProjectSettings}
                className="text-muted-foreground hover:text-foreground ml-12 flex max-w-full items-center gap-1.5 text-left text-xs transition-colors"
                title="Open project settings"
              >
                <Folder className="size-3.5 shrink-0 opacity-70" />
                {folderPath ? (
                  <span className="min-w-0 truncate font-mono">
                    {folderPath}
                  </span>
                ) : (
                  <span className="min-w-0 truncate">No project folder</span>
                )}
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-1">
              <AddWidgetButton
                surface="project"
                presentTypes={presentTypes}
                onAdd={addWidget}
                onReset={resetLayout}
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={onOpenProjectSettings}
              >
                <Settings className="size-3.5" />
                Settings
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/40"
                onClick={() => setConfirmRemove(true)}
                aria-label="Remove project"
                title="Remove project"
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          </div>
          <WidgetBoard
            client={client}
            surface="project"
            layout={layout}
            project={project}
            showAddBar={false}
            onLayoutChange={persistLayout}
          />
        </div>
      </ScrollArea>

      <AlertDialog open={confirmRemove} onOpenChange={setConfirmRemove}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove project?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 text-sm">
                <p>
                  This permanently deletes the project and all of its sessions.
                  This cannot be undone.
                </p>
                <div className="bg-muted/50 rounded-lg px-3 py-2.5 text-left">
                  <div className="text-foreground truncate font-medium">
                    {project.name}
                  </div>
                  <div className="text-muted-foreground mt-0.5 text-xs">
                    {sessionLabel} will be removed
                  </div>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 text-white hover:bg-red-700 focus:ring-red-600"
              onClick={() => {
                setConfirmRemove(false)
                onDeleteProject(project)
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export function HomeProjectsList({
  projects,
  onOpenProject,
  onTogglePinProject,
  onDeleteProject
}: {
  projects: AgentProject[]
  onOpenProject: (id: string) => void
  onTogglePinProject: (project: AgentProject) => void
  onDeleteProject: (project: AgentProject) => void
}) {
  if (projects.length === 0) {
    return (
      <div className="text-muted-foreground px-4 py-8 text-center text-sm">
        No projects yet. Create one to organize your work.
      </div>
    )
  }

  return (
    <>
      {projects.map(project => (
        <div
          key={project.id}
          className="hover:bg-muted/50 flex items-center gap-3 px-4 py-3"
        >
          <button
            type="button"
            className="flex min-w-0 flex-1 items-start gap-2.5 text-left"
            onClick={() => onOpenProject(project.id)}
          >
            <ProjectMark
              icon={project.icon}
              color={project.color}
              className="mt-0.5 size-7"
            />
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="truncate text-sm font-medium">
                  {project.name}
                </span>
                {project.pinned ? <Pin className="size-3 shrink-0" /> : null}
              </div>
              <p className="text-muted-foreground mt-0.5 text-xs">
                {project.sessionCount} sessions ·{' '}
                {relativeTime(project.updatedAt)}
              </p>
            </div>
          </button>
          <Popover>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="text-muted-foreground hover:bg-muted inline-flex size-7 items-center justify-center rounded-md"
                aria-label={`Actions for ${project.name}`}
              >
                <MoreHorizontal className="size-4" />
              </button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-36 p-1">
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm"
                onClick={() => onTogglePinProject(project)}
              >
                <Pin className="size-3.5" />
                {project.pinned ? 'Unpin' : 'Pin'}
              </button>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-red-600 hover:bg-red-50"
                onClick={() => onDeleteProject(project)}
              >
                <Trash2 className="size-3.5" />
                Delete
              </button>
            </PopoverContent>
          </Popover>
        </div>
      ))}
    </>
  )
}

export function HomeRecentSessionsList({
  sessions,
  previews,
  projectNames,
  onOpenSession,
  onCreateSession
}: {
  sessions: AgentSession[]
  previews: Record<string, string>
  projectNames: Map<string, string>
  onOpenSession: (id: string) => void
  onCreateSession: (projectId: string | null) => void
}) {
  if (sessions.length === 0) {
    return (
      <div className="flex flex-col items-center px-4 py-10 text-center">
        <p className="text-muted-foreground text-sm">No sessions here</p>
        <Button
          variant="ghost"
          className="mt-2"
          onClick={() => onCreateSession(null)}
        >
          <Plus className="size-3.5" />
          New Agent
        </Button>
      </div>
    )
  }

  return (
    <div className="bg-card sandwalk-surface-shadow divide-y rounded-xl">
      {sessions.map(item => (
        <button
          key={item.id}
          type="button"
          className="hover:bg-muted/50 flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
          onClick={() => onOpenSession(item.id)}
          title={previews[item.id] || undefined}
        >
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">
              {item.title || 'Untitled'}
            </span>
            <span className="text-muted-foreground block truncate text-xs">
              {item.projectId
                ? projectNames.get(item.projectId) || 'Project'
                : 'No project'}
            </span>
          </span>
          <span className="text-muted-foreground shrink-0 text-xs">
            {relativeTime(item.lastMessageAt || item.updatedAt)}
          </span>
        </button>
      ))}
    </div>
  )
}
