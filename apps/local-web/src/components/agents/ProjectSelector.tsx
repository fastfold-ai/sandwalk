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
import { useMemo, useState } from 'react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import { ProjectMark } from './ProjectMark'

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

  const active = useMemo(
    () => projects.find(project => project.id === value) || null,
    [projects, value]
  )

  const ordered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const rows = [...projects].sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    if (!needle) return rows
    return rows.filter(
      project =>
        project.name.toLowerCase().includes(needle) ||
        (project.description || '').toLowerCase().includes(needle)
    )
  }, [projects, query])

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

          {ordered.length > 0 ? (
            <>
              <DropdownMenuSeparator />
              <ScrollArea className="max-h-64">
                <div className="pr-1">
                  {ordered.map(project => (
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
                        {project.description ? (
                          <div className="text-muted-foreground truncate text-xs">
                            {project.description}
                          </div>
                        ) : null}
                      </div>
                      <Check
                        className={cn(
                          'mt-0.5 size-3.5 shrink-0',
                          value === project.id ? 'opacity-100' : 'opacity-0'
                        )}
                      />
                    </DropdownMenuItem>
                  ))}
                </div>
              </ScrollArea>
            </>
          ) : (
            <>
              <DropdownMenuSeparator />
              <div className="text-muted-foreground px-2 py-3 text-xs">
                {query.trim()
                  ? 'No projects match your search.'
                  : 'No projects yet.'}
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
