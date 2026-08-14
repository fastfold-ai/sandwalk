import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  SessionGroup
} from '@sandwalk/agent-ui-core'
import { ChevronDown, Loader2, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { ProjectMark } from '@/components/agents/ProjectMark'
import { SessionStatusIcon } from '@/components/agents/SessionStatusIcon'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

/**
 * Panel de picker que aparece en el lado derecho cuando el usuario dispara
 * "Create split view" desde un chat. Reemplaza el segundo panel del split
 * hasta que se elija un chat — ahí recién se crea el grupo.
 *
 * Flujo:
 *  - Dropdown de proyecto arriba (default: proyecto activo, o "All").
 *  - Input de búsqueda que filtra por título.
 *  - Lista de chats del proyecto seleccionado (excluye el chat de origen
 *    y los que ya viven en algún grupo).
 *  - Estados: loading, error con reintento, sin resultados, resultados.
 *  - X arriba a la derecha cancela el split (no crea nada).
 */

export type SplitChatPickerPanelProps = {
  client: LocalAgentClient
  sourceChatId: string
  activeProjectId: string | null
  projects: AgentProject[]
  /** Todos los grupos existentes — para excluir chats ya agrupados. */
  allTabGroups: SessionGroup[]
  /**
   * Sesiones del scope activo (las que ya vive en `bootstrap.sessions`
   * del app). Evita fetch redundante al abrir el picker si el usuario
   * elige el mismo proyecto que el activo — el estado global ya está
   * cargado y hidratado con el ciclo de vida del bootstrap. Solo
   * fetcheamos si el usuario cambia a otro proyecto.
   */
  cachedSessions: AgentSession[]
  onPick: (chatId: string) => void
}

type LoadState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; sessions: AgentSession[] }

export function SplitChatPickerPanel({
  client,
  sourceChatId,
  activeProjectId,
  projects,
  allTabGroups,
  cachedSessions,
  onPick
}: SplitChatPickerPanelProps) {
  const [projectId, setProjectId] = useState<string | null>(activeProjectId)
  const [projectMenuOpen, setProjectMenuOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [state, setState] = useState<LoadState>({ kind: 'idle' })
  const [reloadTick, setReloadTick] = useState(0)
  const searchRef = useRef<HTMLInputElement | null>(null)

  // Chats that already live inside some group — excluded from the
  // picker (rule: a chat can only be in one split at a time).
  const chatIdsInAnyGroup = useMemo(() => {
    const s = new Set<string>()
    for (const g of allTabGroups) for (const id of g.chatIds) s.add(id)
    return s
  }, [allTabGroups])

  useEffect(() => {
    // Fast path: if the picked project matches the app's active one,
    // reuse the sessions already cached by bootstrap — no fetch. This
    // eliminates the boot race (server still starting) and the
    // "eternal loading" state when the user opens the picker right
    // after a dev reset. Bootstrap stays fresh on its own via the
    // SSE / loadSessions cycle.
    if (projectId === activeProjectId) {
      setState({ kind: 'ready', sessions: cachedSessions })
      return
    }
    let cancelled = false
    setState({ kind: 'loading' })
    ;(async () => {
      try {
        const sessions = await client.listSessions(
          projectId ? { projectId } : undefined
        )
        if (!cancelled) setState({ kind: 'ready', sessions })
      } catch (cause) {
        if (cancelled) return
        setState({
          kind: 'error',
          message:
            cause instanceof Error
              ? cause.message
              : 'We could not load the chats. Please retry.'
        })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [client, projectId, activeProjectId, cachedSessions, reloadTick])

  useEffect(() => {
    // Focus the input on open so the user can start typing immediately.
    searchRef.current?.focus()
  }, [])

  const filtered = useMemo(() => {
    if (state.kind !== 'ready') return []
    const needle = query.trim().toLowerCase()
    return state.sessions.filter(s => {
      if (s.id === sourceChatId) return false
      if (chatIdsInAnyGroup.has(s.id)) return false
      if (!needle) return true
      return (s.title || '').toLowerCase().includes(needle)
    })
  }, [state, query, sourceChatId, chatIdsInAnyGroup])

  const activeProject = projects.find(p => p.id === projectId) || null

  return (
    // INNER card — compact widget centered inside the outer card
    // (which owns the border/focus and the X in the top-right).
    // Max-width so it reads as a small modal; max-height at 65% of
    // the parent so it never stretches to fill the panel — the list
    // scroll lives inside the body.
    <div className="bg-background flex w-full max-w-sm max-h-[65%] min-h-0 flex-col overflow-hidden rounded-lg border shadow-sm">
      {/* Toolbar: project + search. */}
      <div className="flex shrink-0 flex-col gap-2 px-3 py-3">
        <div className="flex flex-col gap-1">
          <label className="text-muted-foreground text-[10px] font-semibold uppercase tracking-wide">
            Projects
          </label>
          <Popover
            open={projectMenuOpen}
            onOpenChange={setProjectMenuOpen}
          >
          <PopoverTrigger asChild>
            <button
              type="button"
              className="hover:bg-muted text-foreground flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-left text-[12px]"
            >
              {activeProject ? (
                <ProjectMark
                  icon={activeProject.icon}
                  color={activeProject.color}
                  className="size-4"
                  iconClassName="size-2.5"
                />
              ) : (
                <span className="bg-muted inline-flex size-4 items-center justify-center rounded-full text-[8px] font-semibold">
                  All
                </span>
              )}
              <span className="min-w-0 flex-1 truncate">
                {activeProject ? activeProject.name : 'All projects'}
              </span>
              <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-64 p-1">
            <button
              type="button"
              className={cn(
                'hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px]',
                projectId === null && 'bg-muted'
              )}
              onClick={() => {
                setProjectId(null)
                setProjectMenuOpen(false)
              }}
            >
              <span className="bg-muted inline-flex size-5 items-center justify-center rounded-full text-[9px] font-semibold">
                All
              </span>
              All projects
            </button>
            {projects.length > 0 ? (
              <div className="border-border/60 my-1 border-t" />
            ) : null}
            {projects.map(p => (
              <button
                key={p.id}
                type="button"
                className={cn(
                  'hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px]',
                  projectId === p.id && 'bg-muted'
                )}
                onClick={() => {
                  setProjectId(p.id)
                  setProjectMenuOpen(false)
                }}
              >
                <ProjectMark
                  icon={p.icon}
                  color={p.color}
                  className="size-5"
                  iconClassName="size-3"
                />
                <span className="min-w-0 flex-1 truncate">{p.name}</span>
              </button>
            ))}
          </PopoverContent>
        </Popover>
        </div>

        <div className="relative">
          <Search className="text-muted-foreground pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2" />
          <Input
            ref={searchRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search by title…"
            className="h-8 pl-7 text-[12px]"
          />
        </div>
      </div>

      {/* Body: lista o estados */}
      <div className="min-h-0 flex-1">
        {state.kind === 'loading' ? (
          <PickerState>
            <Loader2 className="text-muted-foreground size-4 animate-spin" />
            <span className="text-muted-foreground text-[12px]">
              Loading chats…
            </span>
          </PickerState>
        ) : state.kind === 'error' ? (
          <PickerState>
            <p className="text-foreground text-[13px] font-medium">
              Could not load the chats
            </p>
            <p className="text-muted-foreground max-w-[240px] text-center text-[12px]">
              {state.message}
            </p>
            <button
              type="button"
              onClick={() => setReloadTick(t => t + 1)}
              className="hover:bg-muted text-foreground mt-1 rounded-md border px-3 py-1 text-[12px]"
            >
              Retry
            </button>
          </PickerState>
        ) : state.kind === 'ready' && filtered.length === 0 ? (
          <PickerState>
            <p className="text-foreground text-[13px] font-medium">
              {query.trim() ? 'No results' : 'No chats available'}
            </p>
            <p className="text-muted-foreground max-w-[240px] text-center text-[12px]">
              {query.trim()
                ? 'Try another term or switch projects.'
                : 'This project has no other chats to group. Pick another project above.'}
            </p>
          </PickerState>
        ) : state.kind === 'ready' ? (
          <ScrollArea className="h-full">
            <ul className="space-y-px px-2 pb-3 pt-1">
              {filtered.map(session => (
                <li key={session.id}>
                  <button
                    type="button"
                    onClick={() => onPick(session.id)}
                    className="hover:bg-muted flex w-full min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-left"
                  >
                    <span className="grid size-3.5 shrink-0 place-items-center">
                      <SessionStatusIcon status={session.status} />
                    </span>
                    <span className="text-foreground min-w-0 flex-1 truncate text-[13px] leading-4">
                      {session.title || 'Untitled'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </ScrollArea>
        ) : null}
      </div>
    </div>
  )
}

function PickerState({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-4 py-8">
      {children}
    </div>
  )
}
