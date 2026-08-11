import type {
  BenchResultSummary,
  LocalAgentClient
} from '@sandwalk/agent-local-client'
import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  ExternalLink,
  MoreHorizontal,
  Pin,
  Plus,
  Target,
  Trash2
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { ProjectMark } from '@/components/agents/ProjectMark'
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
import { cn } from '@/lib/utils'

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
          className="bg-card sandwalk-surface-shadow hover:bg-muted/40 flex min-h-[8.5rem] flex-col rounded-xl p-4 text-left transition-colors"
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

function HomeProjectBenchLinks({
  client,
  projectId
}: {
  client: LocalAgentClient
  projectId: string
}) {
  const navigate = useNavigate()
  const [rows, setRows] = useState<BenchResultSummary[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoaded(false)
    void client
      .listBenchResults()
      .then(items => {
        if (cancelled) return
        setRows(items.filter(item => item.projectId === projectId))
      })
      .catch(() => {
        if (!cancelled) setRows([])
      })
      .finally(() => {
        if (!cancelled) setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [client, projectId])

  if (!loaded || rows.length === 0) return null

  return (
    <section className="mb-8">
      <h3 className="mb-3 text-sm font-medium">Bench results</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {rows.map(row => {
          const pct = Math.round((row.accuracy || 0) * 1000) / 10
          return (
            <button
              key={row.runId}
              type="button"
              className="bg-card sandwalk-surface-shadow hover:bg-muted/40 flex min-h-[6.5rem] flex-col rounded-xl p-4 text-left transition-colors"
              onClick={() =>
                navigate(`/dashboard/bench/${encodeURIComponent(row.runId)}`)
              }
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-2.5">
                  <span
                    className={cn(
                      'flex size-8 shrink-0 items-center justify-center rounded-md',
                      pct >= 70
                        ? 'bg-emerald-500/15 text-emerald-600'
                        : pct >= 40
                          ? 'bg-amber-500/15 text-amber-600'
                          : 'bg-red-500/15 text-red-600'
                    )}
                  >
                    <Target className="size-3.5" />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {row.benchmark}
                    </p>
                    <p className="text-muted-foreground mt-0.5 truncate text-xs">
                      {row.modelId}
                    </p>
                  </div>
                </div>
                <p
                  className={cn(
                    'text-lg font-semibold tabular-nums',
                    pct >= 70
                      ? 'text-emerald-600'
                      : pct >= 40
                        ? 'text-amber-600'
                        : 'text-red-600'
                  )}
                >
                  {pct.toFixed(1)}%
                </p>
              </div>
              <div className="text-muted-foreground mt-auto flex items-center justify-between gap-2 pt-3 text-xs">
                <span className="tabular-nums">
                  {row.correct}/{row.total}
                  {row.timeS ? ` · ${row.timeS}s` : ''}
                </span>
                <span className="inline-flex items-center gap-1">
                  Open result
                  <ExternalLink className="size-3" />
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}

export function HomeProjectView({
  project,
  sessions,
  previews,
  client,
  onCreateSession,
  onOpenSession,
  onDeleteProject
}: {
  project: AgentProject
  sessions: AgentSession[]
  previews: Record<string, string>
  client: LocalAgentClient
  onCreateSession: (projectId: string | null) => void
  onOpenSession: (id: string) => void
  onDeleteProject: (project: AgentProject) => void
}) {
  const [confirmRemove, setConfirmRemove] = useState(false)
  const description =
    project.description?.trim() ||
    'Pick up where you left off or start something new.'
  const isDenseMeta =
    description.includes('\n') ||
    /sandwalk-bench|matrix:|sessions:/i.test(description)
  const sessionCount = Math.max(sessions.length, project.sessionCount || 0)
  const sessionLabel =
    sessionCount === 1 ? '1 session' : `${sessionCount} sessions`

  return (
    <>
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-6xl px-6 pt-8 pb-8 md:px-10">
          <div className="mb-8 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <ProjectMark
                  icon={project.icon}
                  color={project.color}
                  className="size-9 shrink-0"
                  iconClassName="size-4"
                />
                <h2 className="truncate text-xl font-semibold">{project.name}</h2>
              </div>
              <div className="flex flex-wrap items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onCreateSession(project.id)}
                >
                  <Plus className="size-3.5" />
                  New Agent
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/40"
                  onClick={() => setConfirmRemove(true)}
                >
                  <Trash2 className="size-3.5" />
                  Remove
                </Button>
              </div>
            </div>
            {isDenseMeta ? (
              <pre className="bg-muted/35 text-muted-foreground max-w-3xl overflow-x-auto rounded-xl px-4 py-3 font-sans text-xs leading-relaxed whitespace-pre-wrap">
                {description}
              </pre>
            ) : (
              <p className="text-muted-foreground max-w-2xl text-sm leading-relaxed">
                {description}
              </p>
            )}
          </div>
          <HomeProjectBenchLinks client={client} projectId={project.id} />
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
    </>
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
