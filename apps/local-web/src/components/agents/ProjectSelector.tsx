import type { AgentProject } from '@sandwalk/agent-ui-core'
import { Check, ChevronDown, Plus, Settings } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import { ProjectMark } from './ProjectMark'

export function ProjectSelector({
  projects,
  value,
  onSelectAll,
  onSelectProject,
  onOpenSettings,
  onNewProject
}: {
  projects: AgentProject[]
  value: string | null
  onSelectAll: () => void
  onSelectProject: (projectId: string) => void
  onOpenSettings: () => void
  onNewProject: () => void
}) {
  const [open, setOpen] = useState(false)

  const active = useMemo(
    () => projects.find(project => project.id === value) || null,
    [projects, value]
  )

  const ordered = useMemo(() => {
    return [...projects].sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
      return a.name.localeCompare(b.name)
    })
  }, [projects])

  const label = active?.name || 'All'

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
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
      <DropdownMenuContent align="start" className="w-72 p-1.5">
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
        ) : null}

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
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
