import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession, WorkspaceFile } from '@sandwalk/agent-ui-core'
import { Command as CommandPrimitive } from 'cmdk'
import {
  Activity,
  AtSign,
  Box,
  Boxes,
  Cpu,
  Database,
  GitBranch,
  HardDrive,
  Hash,
  LayoutDashboard,
  MessageSquare,
  Network,
  Plug,
  Search,
  Settings2,
  Sparkles,
  Stethoscope,
  Wrench,
  X,
  Zap
} from 'lucide-react'
import {
  type KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react'

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList
} from '@/components/ui/command'
import { getFileIcon } from '@/lib/file-icons'
import { cn, relativeTime } from '@/lib/utils'

export type SearchScope = 'all' | 'artifacts' | 'sessions'

export type IndexedArtifact = {
  path: string
  name: string
  sessionId: string
  sessionTitle: string
  mtime: string | null
}

type GlobalSearchDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  client: LocalAgentClient
  sessions: AgentSession[]
  currentSessionId: string | null
  currentSessionTitle?: string | null
  workspaceFiles: WorkspaceFile[]
  onOpenSession: (sessionId: string) => void
  onOpenArtifact: (sessionId: string, path: string) => void
  onMentionArtifact: (sessionId: string, path: string) => void
  onCreateSession: () => void
  onNavigate: (path: string) => void
}

const ARTIFACT_LIMIT = 40
const SESSION_LIMIT = 30
const INDEX_SESSION_LIMIT = 40

function matchesQuery(haystack: string, query: string) {
  if (!query) return true
  return haystack.toLowerCase().includes(query.toLowerCase())
}

function sessionRecency(session: AgentSession) {
  const stamp = session.lastMessageAt || session.updatedAt || session.createdAt
  const time = stamp ? new Date(stamp).getTime() : 0
  return Number.isFinite(time) ? time : 0
}

/** One row per title (case-insensitive); keep the most recently active session. */
function uniqueSessionsByTitle(sessions: AgentSession[]) {
  const byId = new Map<string, AgentSession>()
  for (const session of sessions) {
    if (!byId.has(session.id)) byId.set(session.id, session)
  }
  const sorted = [...byId.values()].sort(
    (a, b) => sessionRecency(b) - sessionRecency(a)
  )
  const seenTitles = new Set<string>()
  const unique: AgentSession[] = []
  for (const session of sorted) {
    const key = session.title.trim().toLowerCase() || session.id
    if (seenTitles.has(key)) continue
    seenTitles.add(key)
    unique.push(session)
  }
  return unique
}

function scopeLabel(scope: SearchScope) {
  if (scope === 'artifacts') return 'Artifacts'
  if (scope === 'sessions') return 'Sessions'
  return null
}

function placeholderFor(scope: SearchScope) {
  if (scope === 'artifacts') return 'Search artifacts...'
  if (scope === 'sessions') return 'Search sessions...'
  return 'Search this project...'
}

const DASHBOARD_COMMANDS = [
  {
    id: 'status',
    label: 'Status',
    path: '/dashboard/status',
    value: 'command status server health system ram cache',
    icon: Activity
  },
  {
    id: 'overview',
    label: 'Overview',
    path: '/dashboard',
    value: 'command overview dashboard',
    icon: LayoutDashboard
  },
  {
    id: 'general',
    label: 'General',
    path: '/dashboard/general',
    value: 'command general settings',
    icon: Settings2
  },
  {
    id: 'agent_runtime',
    label: 'Agent Runtime',
    path: '/dashboard/agent/runtime',
    value: 'command agent runtime recursion langgraph tool mode',
    icon: Cpu
  },
  {
    id: 'models',
    label: 'Models',
    path: '/dashboard/models',
    value: 'command models llm providers profiles',
    icon: Box
  },
  {
    id: 'datasets',
    label: 'Datasets',
    path: '/dashboard/datasets',
    value: 'command datasets data download install',
    icon: Database
  },
  {
    id: 'tools',
    label: 'Tools',
    path: '/dashboard/tools',
    value: 'command tools registry enable disable',
    icon: Wrench
  },
  {
    id: 'doctor',
    label: 'Doctor',
    path: '/dashboard/doctor',
    value: 'command doctor diagnostics health',
    icon: Stethoscope
  },
  {
    id: 'storage',
    label: 'Storage',
    path: '/dashboard/storage',
    value: 'command storage disk usage datasets artifacts',
    icon: HardDrive
  },
  {
    id: 'environment',
    label: 'Environment',
    path: '/dashboard/environment',
    value: 'command environment python packages install torch rdkit',
    icon: Boxes
  },
  {
    id: 'skills',
    label: 'Skills',
    path: '/dashboard/skills',
    value: 'command skills',
    icon: Sparkles
  },
  {
    id: 'specialists',
    label: 'Specialists',
    path: '/dashboard/specialists',
    value: 'command specialists agent profiles',
    icon: GitBranch
  },
  {
    id: 'integrations',
    label: 'Integrations',
    path: '/dashboard/integrations',
    value: 'command integrations',
    icon: Plug
  },
  {
    id: 'mcp',
    label: 'MCPs',
    path: '/dashboard/mcp',
    value: 'command mcp servers',
    icon: Network
  }
] as const

export function GlobalSearchDialog({
  open,
  onOpenChange,
  client,
  sessions,
  currentSessionId,
  currentSessionTitle,
  workspaceFiles,
  onOpenSession,
  onOpenArtifact,
  onMentionArtifact,
  onCreateSession,
  onNavigate
}: GlobalSearchDialogProps) {
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState<SearchScope>('all')
  const [indexedArtifacts, setIndexedArtifacts] = useState<IndexedArtifact[]>(
    []
  )
  const [indexing, setIndexing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) {
      setQuery('')
      setScope('all')
      return
    }
    const timer = window.setTimeout(() => inputRef.current?.focus(), 20)
    return () => window.clearTimeout(timer)
  }, [open])

  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    setIndexing(true)

    const currentFiles: IndexedArtifact[] = workspaceFiles
      .filter(file => file.type === 'file')
      .map(file => ({
        path: file.path,
        name: file.name,
        sessionId: currentSessionId || '',
        sessionTitle: currentSessionTitle || 'Current session',
        mtime: file.mtime
      }))
      .filter(item => item.sessionId)

    setIndexedArtifacts(currentFiles)

    void (async () => {
      const otherSessions = sessions
        .filter(session => session.id !== currentSessionId)
        .slice(0, INDEX_SESSION_LIMIT)

      const batches = await Promise.all(
        otherSessions.map(async session => {
          try {
            const files = await client.listFiles(session.id, controller.signal)
            return files
              .filter(file => file.type === 'file')
              .map(file => ({
                path: file.path,
                name: file.name,
                sessionId: session.id,
                sessionTitle: session.title,
                mtime: file.mtime
              }))
          } catch {
            return [] as IndexedArtifact[]
          }
        })
      )

      if (controller.signal.aborted) return

      const byKey = new Map<string, IndexedArtifact>()
      for (const item of [...currentFiles, ...batches.flat()]) {
        byKey.set(`${item.sessionId}:${item.path}`, item)
      }
      const merged = [...byKey.values()].sort((a, b) => {
        const aTime = a.mtime ? new Date(a.mtime).getTime() : 0
        const bTime = b.mtime ? new Date(b.mtime).getTime() : 0
        return bTime - aTime
      })
      setIndexedArtifacts(merged)
      setIndexing(false)
    })()

    return () => {
      controller.abort()
    }
  }, [
    client,
    currentSessionId,
    currentSessionTitle,
    open,
    sessions,
    workspaceFiles
  ])

  const filteredArtifacts = useMemo(() => {
    const needle = query.trim()
    return indexedArtifacts
      .filter(
        item =>
          matchesQuery(item.name, needle) || matchesQuery(item.path, needle)
      )
      .slice(0, ARTIFACT_LIMIT)
  }, [indexedArtifacts, query])

  const filteredSessions = useMemo(() => {
    const needle = query.trim()
    return uniqueSessionsByTitle(sessions)
      .filter(session => matchesQuery(session.title, needle))
      .slice(0, SESSION_LIMIT)
  }, [query, sessions])

  const showArtifacts = scope === 'all' || scope === 'artifacts'
  const showSessions = scope === 'all' || scope === 'sessions'
  const showCommands = scope === 'all'

  const applyScopeFromKey = (next: SearchScope) => {
    setScope(next)
    setQuery('')
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }

  const clearScope = () => {
    setScope('all')
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }

  const handleQueryChange = (value: string) => {
    if (scope === 'all') {
      if (value === '@' || value.startsWith('@')) {
        setScope('artifacts')
        setQuery(value.slice(1))
        return
      }
      if (value === '#' || value.startsWith('#')) {
        setScope('sessions')
        setQuery(value.slice(1))
        return
      }
    }
    setQuery(value)
  }

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (
      (event.key === 'Backspace' || event.key === 'Delete') &&
      !query &&
      scope !== 'all'
    ) {
      event.preventDefault()
      clearScope()
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      onOpenChange(false)
    }
  }

  const close = () => onOpenChange(false)

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      contentClassName="top-[18%] translate-y-0 max-w-2xl gap-0 rounded-xl border-border/70 bg-popover shadow-2xl"
      overlayClassName="bg-black/50 backdrop-blur-[1px]"
      commandProps={{
        shouldFilter: false,
        className: 'rounded-xl'
      }}
    >
      <div
        className="flex items-center gap-2 border-b px-3 py-2.5"
        cmdk-input-wrapper=""
      >
        <Search className="text-muted-foreground size-4 shrink-0 opacity-70" />
        {scope !== 'all' ? (
          <button
            type="button"
            onClick={clearScope}
            className="bg-muted text-foreground inline-flex h-6 shrink-0 items-center gap-1 rounded-full px-2 text-xs"
          >
            {scopeLabel(scope)}
            <X className="size-3 opacity-70" />
          </button>
        ) : null}
        <CommandPrimitive.Input
          ref={inputRef}
          value={query}
          onValueChange={handleQueryChange}
          onKeyDown={handleInputKeyDown}
          placeholder={placeholderFor(scope)}
          className="placeholder:text-muted-foreground h-8 min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
        {currentSessionTitle ? (
          <span className="text-muted-foreground/70 max-w-[7rem] truncate rounded-md border px-1.5 py-0.5 text-[10px]">
            {currentSessionTitle}
          </span>
        ) : null}
      </div>

      <CommandList className="chat-scrollbar max-h-[420px] overflow-y-auto px-1 py-1">
        <CommandEmpty>
          {indexing ? 'Indexing files…' : 'No results found.'}
        </CommandEmpty>

        {showArtifacts && filteredArtifacts.length > 0 ? (
          <CommandGroup heading="Recent artifacts">
            {filteredArtifacts.map(item => (
              <CommandItem
                key={`artifact:${item.sessionId}:${item.path}`}
                value={`artifact ${item.sessionId} ${item.path} ${item.name}`}
                onSelect={() => {
                  onOpenArtifact(item.sessionId, item.path)
                  close()
                }}
                className="group gap-2.5 py-2"
              >
                <Icon
                  icon={getFileIcon(item.name)}
                  className="size-4 shrink-0"
                />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {item.name}
                  </div>
                  <div className="text-muted-foreground truncate text-[11px]">
                    {item.sessionTitle}
                    {item.mtime ? ` · ${relativeTime(item.mtime)}` : ''}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-data-[selected=true]:opacity-100">
                  <button
                    type="button"
                    className="hover:bg-background/60 rounded p-1"
                    title="Mention in chat"
                    onClick={event => {
                      event.preventDefault()
                      event.stopPropagation()
                      onMentionArtifact(item.sessionId, item.path)
                      close()
                    }}
                  >
                    <AtSign className="size-3.5" />
                  </button>
                </div>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}

        {showSessions && filteredSessions.length > 0 ? (
          <CommandGroup heading="Recent sessions">
            {filteredSessions.map(session => (
              <CommandItem
                key={`session:${session.id}`}
                value={`session ${session.id} ${session.title}`}
                onSelect={() => {
                  onOpenSession(session.id)
                  close()
                }}
                className="gap-2.5 py-2"
              >
                <MessageSquare className="text-muted-foreground size-4 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {session.title}
                  </div>
                  <div className="text-muted-foreground truncate text-[11px]">
                    {relativeTime(session.lastMessageAt || session.updatedAt)}
                  </div>
                </div>
                <span className="text-primary shrink-0 text-[11px] font-medium">
                  Session
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}

        {showCommands ? (
          <CommandGroup heading="Commands">
            <CommandItem
              value="command new session"
              onSelect={() => {
                onCreateSession()
                close()
              }}
              className="gap-2.5 py-2"
            >
              <Zap className="text-muted-foreground size-4 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">New session</div>
              </div>
              <span className="text-muted-foreground text-[11px]">⌘N</span>
            </CommandItem>
            {DASHBOARD_COMMANDS.map(command => {
              const Icon = command.icon
              return (
                <CommandItem
                  key={command.id}
                  value={command.value}
                  onSelect={() => {
                    onNavigate(command.path)
                    close()
                  }}
                  className="gap-2.5 py-2"
                >
                  <Icon className="text-muted-foreground size-4 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{command.label}</div>
                  </div>
                </CommandItem>
              )
            })}
          </CommandGroup>
        ) : null}
      </CommandList>

      <div className="text-muted-foreground flex items-center justify-between gap-3 border-t px-3 py-2 text-[11px]">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>↑↓ navigate</span>
          <span>↵ open</span>
          {scope === 'artifacts' || scope === 'all' ? (
            <span>@ mention</span>
          ) : null}
          <span>esc close</span>
          {scope !== 'all' ? <span>⌫ clear filter</span> : null}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {scope !== 'artifacts' ? (
            <button
              type="button"
              onClick={() => applyScopeFromKey('artifacts')}
              className={cn(
                'inline-flex items-center gap-1 rounded-full border px-2 py-0.5',
                scope === 'all' && 'hover:bg-muted/60'
              )}
            >
              <AtSign className="size-3" />
              artifacts
            </button>
          ) : null}
          {scope !== 'sessions' ? (
            <button
              type="button"
              onClick={() => applyScopeFromKey('sessions')}
              className={cn(
                'inline-flex items-center gap-1 rounded-full border px-2 py-0.5',
                scope === 'all' && 'hover:bg-muted/60'
              )}
            >
              <Hash className="size-3" />
              sessions
            </button>
          ) : null}
        </div>
      </div>
    </CommandDialog>
  )
}

export function useGlobalSearchHotkey(
  open: boolean,
  setOpen: (open: boolean) => void
) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return
      if (event.key.toLowerCase() !== 'k') return
      if (!(event.metaKey || event.ctrlKey)) return
      if (event.altKey || event.shiftKey) return
      event.preventDefault()
      setOpen(!open)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, setOpen])
}
