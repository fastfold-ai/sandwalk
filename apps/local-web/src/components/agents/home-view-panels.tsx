import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import { MoreHorizontal, Pin, Plus, Trash2 } from 'lucide-react'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
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

export function HomeProjectSessions({
  sessions,
  previews,
  onOpenSession,
  onCreateSession,
  projectId
}: {
  sessions: AgentSession[]
  previews: Record<string, string>
  onOpenSession: (id: string) => void
  onCreateSession: (projectId: string | null) => void
  projectId: string | null
}) {
  if (sessions.length === 0) {
    return (
      <HomeEmptySessions
        onCreateSession={onCreateSession}
        projectId={projectId}
      />
    )
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {sessions.map(item => (
        <button
          key={item.id}
          type="button"
          className="bg-card hover:bg-muted/40 flex min-h-[8.5rem] flex-col rounded-xl border p-4 text-left transition-colors"
          onClick={() => onOpenSession(item.id)}
          title={previews[item.id] || undefined}
        >
          <div className="flex items-start justify-between gap-3">
            <span className="line-clamp-2 text-sm font-medium">
              {item.title || 'Untitled'}
            </span>
            <span className="text-muted-foreground shrink-0 text-xs">
              {relativeTime(item.lastMessageAt || item.updatedAt)}
            </span>
          </div>
          <p className="text-muted-foreground mt-2 line-clamp-3 flex-1 text-xs leading-relaxed">
            {previews[item.id] || 'No messages yet'}
          </p>
        </button>
      ))}
    </div>
  )
}

export function HomeProjectView({
  project,
  sessions,
  previews,
  onCreateSession,
  onOpenSession
}: {
  project: AgentProject
  sessions: AgentSession[]
  previews: Record<string, string>
  onCreateSession: (projectId: string | null) => void
  onOpenSession: (id: string) => void
}) {
  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-5xl px-6 py-8 md:px-10">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0">
            <h2 className="truncate text-xl font-semibold">{project.name}</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              {project.description ||
                'Pick up where you left off or start something new.'}
            </p>
          </div>
          {sessions.length > 0 ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onCreateSession(project.id)}
            >
              <Plus className="size-3.5" />
              New Agent
            </Button>
          ) : null}
        </div>
        <section>
          <h3 className="mb-3 text-sm font-medium">Recent sessions</h3>
          <HomeProjectSessions
            sessions={sessions}
            previews={previews}
            onOpenSession={onOpenSession}
            onCreateSession={onCreateSession}
            projectId={project.id}
          />
        </section>
      </div>
    </ScrollArea>
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
            className="min-w-0 flex-1 text-left"
            onClick={() => onOpenProject(project.id)}
          >
            <div className="flex items-center gap-1.5">
              <span className="truncate text-sm font-medium">{project.name}</span>
              {project.pinned ? <Pin className="size-3 shrink-0" /> : null}
            </div>
            <p className="text-muted-foreground mt-0.5 text-xs">
              {project.sessionCount} sessions · {relativeTime(project.updatedAt)}
            </p>
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
    <div className="bg-card divide-y rounded-xl border">
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
