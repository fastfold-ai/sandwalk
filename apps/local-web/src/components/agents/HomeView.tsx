import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import { Plus } from 'lucide-react'
import { useEffect, useMemo } from 'react'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import {
  HomeEmptySessions,
  HomeProjectView,
  HomeProjectsList,
  HomeRecentSessionsList
} from './home-view-panels'

export function HomeView({
  projects,
  sessions,
  previews,
  userName,
  activeProjectId,
  onLoadPreviews,
  onCreateProject,
  onCreateSession,
  onOpenProject,
  onOpenSession,
  onTogglePinProject,
  onDeleteProject
}: {
  projects: AgentProject[]
  sessions: AgentSession[]
  previews: Record<string, string>
  userName: string | null
  activeProjectId: string | null
  onLoadPreviews: (
    sessionIds: string[],
    signal?: AbortSignal
  ) => void | Promise<void>
  onCreateProject: () => void
  onCreateSession: (projectId: string | null) => void
  onOpenProject: (id: string) => void
  onOpenSession: (id: string) => void
  onTogglePinProject: (project: AgentProject) => void
  onDeleteProject: (project: AgentProject) => void
}) {
  const hour = new Date().getHours()
  const greeting =
    hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const pagePad = 'mx-auto w-full px-6 py-8 md:px-10'
  const activeProject =
    projects.find(project => project.id === activeProjectId) || null
  const recent = useMemo(
    () =>
      sessions
        .filter(
          item =>
            item.organizeLabel !== 'archive' &&
            (!activeProjectId || item.projectId === activeProjectId)
        )
        .slice(0, activeProjectId ? 20 : 8),
    [activeProjectId, sessions]
  )
  const recentIdsKey = recent.map(item => item.id).join(',')

  useEffect(() => {
    if (!recentIdsKey) return
    // Do not AbortController here — React StrictMode remounts abort in-flight
    // previews and show noisy canceled requests. In-flight + cache dedupe is enough.
    void onLoadPreviews(recentIdsKey.split(',').filter(Boolean))
  }, [onLoadPreviews, recentIdsKey])

  const projectNames = new Map(
    projects.map(project => [project.id, project.name])
  )
  const orderedProjects = [...projects].sort(
    (a, b) =>
      Number(b.pinned) - Number(a.pinned) ||
      new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  )

  if (activeProject) {
    return (
      <HomeProjectView
        project={activeProject}
        sessions={recent}
        previews={previews}
        onCreateSession={onCreateSession}
        onOpenSession={onOpenSession}
      />
    )
  }

  if (recent.length === 0 && orderedProjects.length === 0) {
    return (
      <ScrollArea className="flex-1">
        <div className={cn(pagePad, 'max-w-3xl')}>
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold">
                {greeting}
                {userName ? `, ${userName}` : ''}
              </h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Pick up where you left off or start something new.
              </p>
            </div>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={onCreateProject}>
                <Plus className="size-3.5" />
                New project
              </Button>
            </div>
          </div>
          <section>
            <h3 className="mb-3 text-sm font-medium">Recent sessions</h3>
            <HomeEmptySessions
              onCreateSession={onCreateSession}
              projectId={null}
            />
          </section>
        </div>
      </ScrollArea>
    )
  }

  return (
    <ScrollArea className="flex-1">
      <div className={cn(pagePad, 'max-w-6xl')}>
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">
              {greeting}
              {userName ? `, ${userName}` : ''}
            </h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Pick up where you left off or start something new.
            </p>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={onCreateProject}>
              <Plus className="size-3.5" />
              New project
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onCreateSession(null)}
            >
              <Plus className="size-3.5" />
              New Agent
            </Button>
          </div>
        </div>
        <div className="grid gap-8 lg:grid-cols-2">
          <section>
            <h3 className="mb-3 text-sm font-medium">Projects</h3>
            <div className="bg-card divide-y rounded-xl border">
              <HomeProjectsList
                projects={orderedProjects}
                onOpenProject={onOpenProject}
                onTogglePinProject={onTogglePinProject}
                onDeleteProject={onDeleteProject}
              />
            </div>
          </section>
          <section>
            <h3 className="mb-3 text-sm font-medium">Recent sessions</h3>
            <HomeRecentSessionsList
              sessions={recent}
              previews={previews}
              projectNames={projectNames}
              onOpenSession={onOpenSession}
              onCreateSession={onCreateSession}
            />
          </section>
        </div>
      </div>
    </ScrollArea>
  )
}
