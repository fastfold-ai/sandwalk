import type { AgentProject } from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronDown,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Settings
} from 'lucide-react'
import { type UIEvent,useEffect, useMemo, useState } from 'react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { relativeTime } from '@/lib/sessions'
import { cn } from '@/lib/utils'

import { ProjectMark } from './ProjectMark'

const SHOW_BENCH_PROJECTS_KEY = 'sandwalk.projects.showBench'
const PROJECT_PAGE_SIZE = 20

function isBenchProject(project: AgentProject): boolean {
  if (project.name.trim().toLowerCase().startsWith('bench ·')) return true
  return /sandwalk-bench/i.test(project.description || '')
}

function readShowBenchProjects(): boolean {
  try {
    return localStorage.getItem(SHOW_BENCH_PROJECTS_KEY) === '1'
  } catch {
    return false
  }
}

function writeShowBenchProjects(value: boolean) {
  try {
    localStorage.setItem(SHOW_BENCH_PROJECTS_KEY, value ? '1' : '0')
  } catch {
    // ignore quota / private mode
  }
}

export function ProjectSelector({
  projects,
  value,
  onSelectAll,
  onSelectProject,
  onOpenSettings,
  onNewProject,
  onRefresh
}: {
  projects: AgentProject[]
  value: string | null
  onSelectAll: () => void
  onSelectProject: (projectId: string) => void
  onOpenSettings: () => void
  onNewProject: () => void
  onRefresh?: () => void | Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [showBench, setShowBench] = useState(readShowBenchProjects)
  const [visibleCount, setVisibleCount] = useState(PROJECT_PAGE_SIZE)

  const active = useMemo(
    () => projects.find(project => project.id === value) || null,
    [projects, value]
  )

  const benchCount = useMemo(
    () => projects.filter(isBenchProject).length,
    [projects]
  )

  const ordered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const rows = [...projects]
      .filter(project => {
        if (showBench || project.id === value) return true
        return !isBenchProject(project)
      })
      .sort((a, b) => {
        if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
        return (
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        )
      })
    if (!needle) return rows
    return rows.filter(
      project =>
        project.name.toLowerCase().includes(needle) ||
        (project.description || '').toLowerCase().includes(needle)
    )
  }, [projects, query, showBench, value])

  useEffect(() => {
    setVisibleCount(PROJECT_PAGE_SIZE)
  }, [query, showBench, open])

  const visible = ordered.slice(0, visibleCount)
  const hasMore = visibleCount < ordered.length

  const label = active?.name || 'All'

  const refresh = async () => {
    if (!onRefresh || refreshing) return
    setRefreshing(true)
    try {
      await onRefresh()
    } finally {
      setRefreshing(false)
    }
  }

  const onListScroll = (event: UIEvent<HTMLDivElement>) => {
    if (!hasMore) return
    const target = event.currentTarget
    const remaining =
      target.scrollHeight - target.scrollTop - target.clientHeight
    if (remaining > 48) return
    setVisibleCount(current =>
      Math.min(current + PROJECT_PAGE_SIZE, ordered.length)
    )
  }

  return (
    <DropdownMenu
      open={open}
      onOpenChange={next => {
        setOpen(next)
        if (!next) setQuery('')
      }}
    >
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="hover:bg-muted/50 inline-flex min-w-0 max-w-[11rem] items-center gap-1 rounded-md px-1.5 py-1 text-left text-sm font-medium"
          aria-label="Select project"
        >
          {active ? (
            <ProjectMark
              icon={active.icon}
              color={active.color}
              className="size-5"
              iconClassName="size-3"
            />
          ) : null}
          <span className="truncate">{label}</span>
          <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72 p-0">
        <div className="flex items-center gap-1.5 border-b px-2 py-1.5">
          <Search className="text-muted-foreground size-3.5 shrink-0" />
          <Input
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Search projects…"
            className="h-8 border-0 px-0 shadow-none focus-visible:ring-0"
            onKeyDown={event => event.stopPropagation()}
            onClick={event => event.stopPropagation()}
          />
          {onRefresh ? (
            <button
              type="button"
              title="Refresh projects"
              aria-label="Refresh projects"
              className="text-muted-foreground hover:text-foreground hover:bg-muted inline-flex size-7 shrink-0 items-center justify-center rounded-md"
              onPointerDown={event => {
                // Keep the menu open while refreshing.
                event.preventDefault()
                event.stopPropagation()
              }}
              onClick={event => {
                event.preventDefault()
                event.stopPropagation()
                void refresh()
              }}
            >
              {refreshing ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <RefreshCw className="size-3.5" />
              )}
            </button>
          ) : null}
        </div>

        <div className="p-1.5">
          {active ? (
            <>
              <DropdownMenuItem
                className="gap-2"
                onSelect={() => {
                  setOpen(false)
                  onOpenSettings()
                }}
              >
                <Settings className="size-3.5" />
                Project settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          ) : null}

          <DropdownMenuItem
            className="gap-2"
            onSelect={() => {
              setOpen(false)
              onSelectAll()
            }}
          >
            <span className="min-w-0 flex-1 truncate">All</span>
            {value === null ? <Check className="size-3.5 shrink-0" /> : null}
          </DropdownMenuItem>

          {benchCount > 0 ? (
            <DropdownMenuItem
              className="gap-2"
              onSelect={event => {
                // Keep the menu open while toggling the filter.
                event.preventDefault()
                const next = !showBench
                setShowBench(next)
                writeShowBenchProjects(next)
              }}
            >
              <span className="min-w-0 flex-1 truncate">
                Show bench ({benchCount})
              </span>
              <Check
                className={cn(
                  'size-3.5 shrink-0',
                  showBench ? 'opacity-100' : 'opacity-0'
                )}
              />
            </DropdownMenuItem>
          ) : null}

          {ordered.length > 0 ? (
            <>
              <DropdownMenuSeparator />
              {/* Fixed height so Radix ScrollArea viewport can scroll (max-h alone won't). */}
              <ScrollArea
                className={cn(ordered.length > 6 ? 'h-64' : 'max-h-64')}
                onScroll={onListScroll}
              >
                <div className="pr-1">
                  {visible.map(project => (
                    <DropdownMenuItem
                      key={project.id}
                      className="items-start gap-2 py-2"
                      onSelect={() => {
                        setOpen(false)
                        onSelectProject(project.id)
                      }}
                    >
                      <ProjectMark
                        icon={project.icon}
                        color={project.color}
                        className="mt-0.5 size-6"
                        iconClassName="size-3"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm">{project.name}</div>
                        <div className="text-muted-foreground mt-0.5 flex items-center gap-2 text-xs">
                          {project.description ? (
                            <span className="min-w-0 flex-1 truncate">
                              {project.description}
                            </span>
                          ) : (
                            <span className="min-w-0 flex-1" />
                          )}
                          <span className="shrink-0 tabular-nums">
                            {relativeTime(project.updatedAt)}
                          </span>
                        </div>
                      </div>
                      <Check
                        className={cn(
                          'mt-0.5 size-3.5 shrink-0',
                          value === project.id ? 'opacity-100' : 'opacity-0'
                        )}
                      />
                    </DropdownMenuItem>
                  ))}
                  {hasMore ? (
                    <div className="text-muted-foreground px-2 py-2 text-center text-[11px]">
                      Scroll for more ({visible.length} of {ordered.length})
                    </div>
                  ) : null}
                </div>
              </ScrollArea>
            </>
          ) : (
            <>
              <DropdownMenuSeparator />
              <div className="text-muted-foreground px-2 py-3 text-xs">
                {query.trim()
                  ? 'No projects match your search.'
                  : showBench || benchCount === 0
                    ? 'No projects yet.'
                    : 'No non-bench projects. Enable “Show bench” above.'}
              </div>
            </>
          )}

          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="gap-2"
            onSelect={() => {
              setOpen(false)
              onNewProject()
            }}
          >
            <Plus className="size-3.5" />
            New project
          </DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
