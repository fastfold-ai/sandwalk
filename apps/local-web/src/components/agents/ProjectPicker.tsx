import type { AgentProject } from '@sandwalk/agent-ui-core'
import { ChevronDown, Folder, Plus, Search } from 'lucide-react'
import { type ReactNode, useMemo, useState } from 'react'

import { ProjectMark } from '@/components/agents/ProjectMark'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

export function ProjectPicker({
  projects,
  value,
  recentIds = [],
  disabled,
  trigger,
  noneLabel = 'All',
  onNewProject,
  onChange
}: {
  projects: AgentProject[]
  value: string | null
  recentIds?: string[]
  disabled?: boolean
  trigger?: ReactNode
  noneLabel?: string
  onNewProject?: () => void
  onChange: (projectId: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')

  const active = useMemo(
    () => projects.find(project => project.id === value) || null,
    [projects, value]
  )

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return projects
    return projects.filter(
      project =>
        project.name.toLowerCase().includes(needle) ||
        (project.description || '').toLowerCase().includes(needle)
    )
  }, [projects, query])

  const recent = useMemo(() => {
    const byId = new Map(projects.map(project => [project.id, project]))
    return recentIds
      .map(id => byId.get(id))
      .filter((project): project is AgentProject => Boolean(project))
      .slice(0, 5)
  }, [projects, recentIds])

  const recentIdsSet = useMemo(
    () => new Set(recent.map(project => project.id)),
    [recent]
  )

  const allProjects = useMemo(() => {
    if (!query.trim() && recentIdsSet.size > 0) {
      return filtered.filter(project => !recentIdsSet.has(project.id))
    }
    return filtered
  }, [filtered, query, recentIdsSet])

  const select = (projectId: string | null) => {
    onChange(projectId)
    setOpen(false)
    setQuery('')
  }

  const defaultTrigger = (
    <button
      type="button"
      className="text-muted-foreground hover:text-foreground inline-flex max-w-full items-center gap-1.5 rounded-md px-1 py-1 text-sm"
      disabled={disabled}
    >
      <Folder className="size-3.5 shrink-0" />
      <span className="truncate font-medium">
        {active?.name || noneLabel}
      </span>
      <ChevronDown className="size-3.5 shrink-0 opacity-70" />
    </button>
  )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild disabled={disabled}>
        {trigger ?? defaultTrigger}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 gap-0 p-0" sideOffset={8}>
        <div className="flex items-center gap-2 border-b px-3 py-2">
          <Search className="text-muted-foreground size-3.5 shrink-0" />
          <Input
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Search projects..."
            className="h-8 border-0 px-0 shadow-none focus-visible:ring-0"
          />
        </div>
        <ScrollArea className="max-h-72">
          <div className="p-1.5">
            <button
              type="button"
              className={cn(
                'hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                value === null && 'bg-muted'
              )}
              onClick={() => select(null)}
            >
              <Folder className="text-muted-foreground size-3.5" />
              <span className="flex-1 truncate">{noneLabel}</span>
              {/*
                Chats sin proyecto asignado aparecen sólo en la vista "All
                projects" del sidebar (no cuelgan de ninguna carpeta). El
                sufijo lo hace explícito para que el usuario no confunda
                "No project" con "borrar la asignación".
              */}
              <span className="text-muted-foreground shrink-0 text-xs">
                (All)
              </span>
            </button>

            {!query.trim() && recent.length > 0 ? (
              <div className="mt-2">
                <div className="text-muted-foreground px-2 py-1 text-[11px] font-medium">
                  Recents
                </div>
                {recent.map(project => (
                  <button
                    key={`recent-${project.id}`}
                    type="button"
                    className={cn(
                      'hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                      value === project.id && 'bg-muted'
                    )}
                    onClick={() => select(project.id)}
                  >
                    <ProjectMark
                      icon={project.icon}
                      color={project.color}
                      className="size-5 shrink-0"
                      iconClassName="size-3"
                    />
                    <span className="truncate">{project.name}</span>
                  </button>
                ))}
              </div>
            ) : null}

            {allProjects.length > 0 || filtered.length === 0 ? (
              <div className="mt-2">
                <div className="text-muted-foreground px-2 py-1 text-[11px] font-medium">
                  All Projects
                </div>
                {allProjects.length === 0 ? (
                  <div className="text-muted-foreground px-2 py-3 text-xs">
                    {filtered.length === 0
                      ? 'No projects found.'
                      : 'No other projects.'}
                  </div>
                ) : (
                  allProjects.map(project => (
                    <button
                      key={project.id}
                      type="button"
                      className={cn(
                        'hover:bg-muted flex w-full flex-col items-start gap-0.5 rounded-md px-2 py-1.5 text-left text-sm',
                        value === project.id && 'bg-muted'
                      )}
                      onClick={() => select(project.id)}
                    >
                      <span className="flex w-full items-center gap-2">
                        <ProjectMark
                          icon={project.icon}
                          color={project.color}
                          className="size-5 shrink-0"
                          iconClassName="size-3"
                        />
                        <span className="min-w-0 flex-1 truncate">
                          {project.name}
                        </span>
                      </span>
                      {project.description ? (
                        // pl-7 alinea la descripción con el nombre (icono 20 px + gap 8 px).
                        <span className="text-muted-foreground truncate pl-7 text-xs">
                          {project.description}
                        </span>
                      ) : null}
                    </button>
                  ))
                )}
              </div>
            ) : null}
          </div>
        </ScrollArea>
        {onNewProject ? (
          <div className="border-t p-1.5">
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              onClick={() => {
                setOpen(false)
                setQuery('')
                onNewProject()
              }}
            >
              <Plus className="size-3.5" />
              New project
            </button>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  )
}
