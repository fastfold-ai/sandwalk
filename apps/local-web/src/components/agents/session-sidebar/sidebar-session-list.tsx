import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronDown,
  Columns2,
  MoreHorizontal,
  Pin
} from 'lucide-react'
import {
  type Dispatch,
  type MouseEvent,
  type SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { useSessionTabColors } from '@/components/agents/session-tab-colors'
import { SessionActionsMenu } from '@/components/agents/SessionActionsMenu'
import { GroupDissolveDialog } from '@/components/agents/SessionTabs'
import { SessionSourceIcon } from '@/components/agents/SessionSourceIcon'
import { SessionStatusIcon } from '@/components/agents/SessionStatusIcon'
import {
  TAB_INLINE_COLORS,
  TabInlineColorRow
} from '@/components/agents/tab-context-menu'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useSessionAttentionIds } from '@/hooks/useSessionAttention'
import { navigateToSession } from '@/lib/navigate-session'
import { relativeTime, type SessionChatState, type TabItemSection } from '@/lib/sessions'
import {
  isSidebarGroupExpanded,
  setSidebarGroupExpanded
} from '@/lib/sidebar-group-expanded'
import { cn } from '@/lib/utils'

/** Same Blue pastel as the tab color tag — marks unread notification sessions. */
const UNREAD_DOT_COLOR =
  TAB_INLINE_COLORS.find(item => item.name === 'Blue')?.value ?? '#8BB8F5'

/** Initial rows per sidebar section; "Load more" reveals the next page. */
const SECTION_PAGE_SIZE = 40

/** Hover: scroll truncated titles RTL so the full label can be read. */
function SidebarMarqueeTitle({ text }: { text: string }) {
  const wrapRef = useRef<HTMLSpanElement>(null)
  const textRef = useRef<HTMLSpanElement>(null)
  const revealTimerRef = useRef<number | null>(null)
  const [overflow, setOverflow] = useState(0)
  const [hovering, setHovering] = useState(false)
  // Drop the right-edge fade early so the end of the title reads cleanly
  // before the scroll animation fully settles.
  const [revealEnd, setRevealEnd] = useState(false)

  const measureOverflow = () => {
    const wrap = wrapRef.current
    const node = textRef.current
    if (!wrap || !node) return 0
    return Math.max(0, node.scrollWidth - wrap.clientWidth)
  }

  const clearRevealTimer = () => {
    if (revealTimerRef.current == null) return
    window.clearTimeout(revealTimerRef.current)
    revealTimerRef.current = null
  }

  useEffect(() => {
    const update = () => setOverflow(measureOverflow())
    update()
    const wrap = wrapRef.current
    if (!wrap || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(update)
    observer.observe(wrap)
    return () => observer.disconnect()
  }, [text])

  useEffect(() => () => clearRevealTimer(), [])

  // Soft start, then crawl to a stop; snap back instantly on leave.
  const durationSec =
    overflow > 0 ? Math.min(13, Math.max(2.6, overflow / 24)) : 0.45
  // Mild ease-in, stronger ease-out — slower takeoff, slow finish.
  const easing = 'cubic-bezier(0.35, 0.12, 0.2, 1)'

  // Edge “diffusion”: fade into the row so hard crops disappear.
  // Idle → right fade; early scroll → both; after ~40% → left only.
  const edgeFade =
    overflow <= 0
      ? undefined
      : hovering && revealEnd
        ? 'linear-gradient(to right, transparent, #000 14px, #000 100%)'
        : hovering
          ? 'linear-gradient(to right, transparent, #000 14px, #000 calc(100% - 14px), transparent)'
          : 'linear-gradient(to right, #000 0%, #000 calc(100% - 16px), transparent)'

  return (
    <span
      ref={wrapRef}
      className="min-w-0 flex-1 overflow-hidden"
      style={
        edgeFade
          ? {
              maskImage: edgeFade,
              WebkitMaskImage: edgeFade
            }
          : undefined
      }
      onMouseEnter={() => {
        const next = measureOverflow()
        setOverflow(next)
        setRevealEnd(false)
        clearRevealTimer()
        if (next <= 0) return
        setHovering(true)
        const duration =
          Math.min(13, Math.max(2.6, next / 24)) * 1000
        // Reveal the trailing edge mid-scroll (~40%), not at the end.
        revealTimerRef.current = window.setTimeout(() => {
          setRevealEnd(true)
          revealTimerRef.current = null
        }, duration * 0.4)
      }}
      onMouseLeave={() => {
        clearRevealTimer()
        setHovering(false)
        setRevealEnd(false)
      }}
    >
      <span
        ref={textRef}
        className="text-foreground/90 group-hover:text-foreground inline-block whitespace-nowrap text-[13px] leading-snug will-change-transform"
        style={{
          transform:
            hovering && overflow > 0
              ? `translateX(-${overflow}px)`
              : 'translateX(0)',
          transition: hovering
            ? `transform ${durationSec}s ${easing}`
            : 'none'
        }}
      >
        {text}
      </span>
    </span>
  )
}

type SessionSection = TabItemSection

export type SidebarSessionListProps = {
  sections: SessionSection[]
  /** When this changes, the list cross-fades instead of hard-swapping. */
  scopeKey?: string | null
  collapsedSidebarSections: Record<string, boolean>
  sessionId: string | null
  chatBySessionId: Record<string, SessionChatState>
  orderedVisibleSessionIds: string[]
  selectedSessionIds: Set<string>
  threadMenuOpenId: string | null
  projects: AgentProject[]
  navigate: NavigateFunction
  setCollapsedSidebarSections: Dispatch<SetStateAction<Record<string, boolean>>>
  selectSessionRange: (orderedIds: string[], targetId: string) => void
  toggleSessionSelected: (targetId: string) => void
  setSelectionAnchorId: (targetId: string) => void
  openSessionTab: (sessionId: string) => void
  prefetchSessionMessages: (sessionId: string) => void | Promise<void>
  setThreadMenuOpenId: Dispatch<SetStateAction<string | null>>
  openRenameDialog: (target: AgentSession) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  exportTranscript: (target: AgentSession) => void | Promise<void>
  setDeleteTarget: Dispatch<SetStateAction<AgentSession | null>>
  onClearSessionSelection: () => void
  onSelectTabGroup?: (groupId: string) => void
  onRenameTabGroup?: (group: import('@sandwalk/agent-ui-core').SessionGroup) => void
  onDissolveTabGroup?: (groupId: string) => void
  onSetTabGroupColor?: (groupId: string, color: string | null) => void
  /**
   * ID del chat focused dentro del grupo activo (si hay). Sirve para
   * pintar en el sidebar cuál chat del split está activo — no solo el
   * grupo. Cuando no estás en un grupo, es null.
   */
  activeGroupChildId?: string | null
  /**
   * Setea el chat activo dentro de un grupo. Se llama cuando el usuario
   * clickea un chat hijo desde el sidebar: en vez de navegar al chat como
   * tab individual, abrimos el grupo con ese chat enfocado en el split.
   */
  setTabGroupActiveChat?: (groupId: string, chatId: string) => void
}

export function SidebarSessionList({
  sections,
  scopeKey = null,
  collapsedSidebarSections,
  sessionId,
  chatBySessionId,
  selectedSessionIds,
  threadMenuOpenId,
  projects,
  navigate,
  setCollapsedSidebarSections,
  selectSessionRange,
  toggleSessionSelected,
  setSelectionAnchorId,
  openSessionTab,
  prefetchSessionMessages,
  setThreadMenuOpenId,
  openRenameDialog,
  updateSession,
  exportTranscript,
  setDeleteTarget,
  onSelectTabGroup,
  onRenameTabGroup,
  onDissolveTabGroup,
  onSetTabGroupColor,
  activeGroupChildId,
  setTabGroupActiveChat
}: SidebarSessionListProps) {
  const [displayedSections, setDisplayedSections] = useState(sections)
  const [listOpacity, setListOpacity] = useState(1)
  const [visibleBySection, setVisibleBySection] = useState<
    Record<string, number>
  >({})
  const { tabColors, setTabColor } = useSessionTabColors()
  const attentionIds = useSessionAttentionIds()
  const previousScopeRef = useRef(scopeKey)
  const sectionsRef = useRef(sections)
  sectionsRef.current = sections

  useEffect(() => {
    if (previousScopeRef.current === scopeKey) return
    previousScopeRef.current = scopeKey
    // Soft cross-fade when the project scope filter changes.
    let cancelled = false
    setListOpacity(0)
    setVisibleBySection({})
    const timer = window.setTimeout(() => {
      if (cancelled) return
      setDisplayedSections(sectionsRef.current)
      requestAnimationFrame(() => {
        if (!cancelled) setListOpacity(1)
      })
    }, 90)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [scopeKey])

  useEffect(() => {
    // Keep the list fresh for pin/rename/status updates without fading.
    if (listOpacity < 1) return
    setDisplayedSections(sections)
  }, [sections, listOpacity])

  // Keep the active session in view even if it sits past the first page.
  useEffect(() => {
    if (!sessionId) return
    setVisibleBySection(current => {
      let next: Record<string, number> | null = null
      for (const section of displayedSections) {
        const index = section.items.findIndex(item => item.id === sessionId)
        if (index < 0) continue
        const needed =
          Math.ceil((index + 1) / SECTION_PAGE_SIZE) * SECTION_PAGE_SIZE
        const shown = current[section.id] ?? SECTION_PAGE_SIZE
        if (shown >= needed) continue
        if (!next) next = { ...current }
        next[section.id] = needed
      }
      return next ?? current
    })
  }, [displayedSections, sessionId])

  const orderedRenderedSessionIds = useMemo(() => {
    const ids: string[] = []
    for (const section of displayedSections) {
      if (collapsedSidebarSections[section.id]) continue
      const limit = visibleBySection[section.id] ?? SECTION_PAGE_SIZE
      for (const item of section.items.slice(0, limit)) ids.push(item.id)
    }
    return ids
  }, [collapsedSidebarSections, displayedSections, visibleBySection])

  return (
    <ScrollArea className="flex-1">
      <div
        className="space-y-2.5 p-2.5 transition-opacity duration-150 ease-out"
        style={{ opacity: listOpacity }}
      >
        {displayedSections.length === 0 ? (
          <p className="text-muted-foreground px-1.5 py-2 text-[13px]">
            No Agents Yet
          </p>
        ) : (
          displayedSections.map(section => {
            const limit = visibleBySection[section.id] ?? SECTION_PAGE_SIZE
            const visibleItems = section.items.slice(0, limit)
            const remaining = Math.max(0, section.items.length - visibleItems.length)
            return (
              <div key={section.id} className="space-y-0.5">
                {/*
                 * Header de sección sin chevron: los headers de tramo
                 * (Today / Yesterday / …) siempre están expandidos, así
                 * los únicos chevrones visibles en el sidebar son los de
                 * los split view groups — se destacan más y no compiten
                 * con los chevrones de sección.
                 */}
                <div className="text-muted-foreground/80 flex w-full items-center gap-1 rounded-md px-2 py-0.5 text-left text-[12px]">
                  <span className="min-w-0 flex-1 truncate">
                    {section.title}
                  </span>
                  <span className="sandwalk-notification-count text-muted-foreground/60 shrink-0 text-[11px] tabular-nums">
                    {section.items.length}
                  </span>
                </div>
                <ul className="space-y-px">
                    {visibleItems.map(item => {
                      if (item.kind === 'group') {
                        return (
                          <SidebarGroupItem
                            key={item.id}
                            group={item.group}
                            chats={item.children}
                            activeId={sessionId}
                            chatBySessionId={chatBySessionId}
                            tabColors={tabColors}
                            selectedSessionIds={selectedSessionIds}
                            attentionIds={attentionIds}
                            activeChildId={activeGroupChildId ?? null}
                            onSelectGroup={onSelectTabGroup}
                            onRenameGroup={onRenameTabGroup}
                            onDissolveGroup={onDissolveTabGroup}
                            onSetGroupColor={onSetTabGroupColor}
                            projects={projects}
                            navigate={navigate}
                            setTabColor={setTabColor}
                            openRenameDialog={openRenameDialog}
                            updateSession={updateSession}
                            exportTranscript={exportTranscript}
                            setDeleteTarget={setDeleteTarget}
                            onSelectChat={chatId => {
                              /*
                               * Chat hijo del split: en vez de abrir el
                               * chat como tab individual, seteamos ese
                               * chat como el activo del grupo y navegamos
                               * al grupo. Así el split se abre con ese
                               * panel enfocado — no un tab suelto.
                               */
                              setSelectionAnchorId(chatId)
                              if (setTabGroupActiveChat) {
                                setTabGroupActiveChat(item.group.id, chatId)
                              }
                              navigate(`/agents/${item.group.id}`)
                            }}
                          />
                        )
                      }
                      const chat = item.session
                      const isSelected = selectedSessionIds.has(item.id)
                      const selecting = selectedSessionIds.size > 0
                      const tabColor = tabColors[item.id]
                      return (
                        <li key={item.id}>
                          <div
                            className={cn(
                              'hover:bg-sidebar-accent/45 group grid grid-cols-[minmax(0,1fr)_2.5rem] items-center rounded-md px-2 py-1.5',
                              item.id === sessionId &&
                                !isSelected &&
                                'bg-sidebar-accent/55',
                              isSelected && 'bg-sidebar-accent'
                            )}
                            onContextMenu={event => {
                              event.preventDefault()
                              setThreadMenuOpenId(item.id)
                            }}
                          >
                            <div className="flex min-w-0 items-center gap-1.5">
                              <button
                                type="button"
                                className={cn(
                                  'grid size-3.5 shrink-0 place-items-center',
                                  (isSelected || selecting) &&
                                    'rounded-[4px] border',
                                  isSelected
                                    ? 'border-primary bg-primary text-primary-foreground'
                                    : selecting
                                      ? 'border-muted-foreground/45 bg-background'
                                      : null
                                )}
                                aria-label={
                                  isSelected
                                    ? `Deselect ${chat.title || 'chat'}`
                                    : `Select ${chat.title || 'chat'}`
                                }
                                aria-pressed={isSelected}
                                onClick={(
                                  event: MouseEvent<HTMLButtonElement>
                                ) => {
                                  event.preventDefault()
                                  event.stopPropagation()
                                  if (event.shiftKey) {
                                    selectSessionRange(
                                      orderedRenderedSessionIds,
                                      item.id
                                    )
                                    return
                                  }
                                  toggleSessionSelected(item.id)
                                }}
                              >
                                {isSelected ? (
                                  <Check
                                    className="size-2.5"
                                    strokeWidth={3}
                                  />
                                ) : selecting ? null : (
                                  <SessionStatusIcon
                                    status={
                                      chat.status === 'awaiting_approval' ||
                                      chatBySessionId[item.id]?.pendingApproval
                                        ? 'awaiting_approval'
                                        : chatBySessionId[item.id]?.runActive
                                          ? 'running'
                                          : chat.status
                                    }
                                  />
                                )}
                              </button>
                              <button
                                type="button"
                                className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                                onClick={(
                                  event: MouseEvent<HTMLButtonElement>
                                ) => {
                                  if (event.shiftKey) {
                                    event.preventDefault()
                                    selectSessionRange(
                                      orderedRenderedSessionIds,
                                      item.id
                                    )
                                    return
                                  }
                                  if (event.metaKey || event.ctrlKey) {
                                    event.preventDefault()
                                    toggleSessionSelected(item.id)
                                    return
                                  }
                                  if (selecting) {
                                    toggleSessionSelected(item.id)
                                    return
                                  }
                                  setSelectionAnchorId(item.id)
                                  void navigateToSession({
                                    id: item.id,
                                    openSessionTab,
                                    prefetchSessionMessages,
                                    navigate
                                  })
                                }}
                              >
                              <SessionSourceIcon
                                source={chat.source}
                                label={chat.sourceLabel}
                              />
                              {chat.organizeLabel === 'pinned' ? (
                                <Pin className="text-muted-foreground/70 size-3 shrink-0" />
                              ) : null}
                              {attentionIds.has(item.id) ? (
                                <span
                                  className="size-2 shrink-0 rounded-full border border-black/10"
                                  style={{ backgroundColor: UNREAD_DOT_COLOR }}
                                  aria-label="Unread"
                                />
                              ) : null}
                              {tabColor ? (
                                <span
                                  className="size-2 shrink-0 rounded-full border border-black/10"
                                  style={{ backgroundColor: tabColor }}
                                  aria-hidden
                                />
                              ) : null}
                              <SidebarMarqueeTitle
                                text={chat.title || 'Untitled'}
                              />
                              </button>
                            </div>
                            <div className="relative h-6 w-10 justify-self-end">
                              <span
                                className={cn(
                                  'text-muted-foreground/70 pointer-events-none absolute inset-0 flex items-center justify-end pr-0.5 text-[11px] transition-opacity',
                                  threadMenuOpenId === item.id
                                    ? 'opacity-0'
                                    : 'opacity-100 group-hover:opacity-0'
                                )}
                              >
                                {relativeTime(
                                  chat.lastMessageAt || chat.updatedAt
                                )}
                              </span>
                              <Popover
                                open={threadMenuOpenId === item.id}
                                onOpenChange={open => {
                                  setThreadMenuOpenId(open ? item.id : null)
                                }}
                              >
                                <PopoverTrigger asChild>
                                  <button
                                    type="button"
                                    className={cn(
                                      'text-muted-foreground hover:bg-muted absolute right-0 top-0 inline-flex size-6 items-center justify-center rounded-md',
                                      threadMenuOpenId === item.id
                                        ? 'opacity-100'
                                        : 'opacity-0 group-hover:opacity-100'
                                    )}
                                    aria-label="Thread options"
                                  >
                                    <MoreHorizontal className="size-3.5" />
                                  </button>
                                </PopoverTrigger>
                                <PopoverContent
                                  align="start"
                                  className="w-52 p-1.5"
                                >
                                  <SessionActionsMenu
                                    session={chat}
                                    projects={projects}
                                    tabColor={tabColor || null}
                                    onRename={() => {
                                      setThreadMenuOpenId(null)
                                      openRenameDialog(chat)
                                    }}
                                    onTogglePin={() => {
                                      setThreadMenuOpenId(null)
                                      void updateSession(chat, {
                                        organizeLabel:
                                          chat.organizeLabel === 'pinned'
                                            ? null
                                            : 'pinned'
                                      })
                                    }}
                                    onMoveToProject={projectId => {
                                      setThreadMenuOpenId(null)
                                      void updateSession(chat, { projectId })
                                    }}
                                    onSetTabColor={color => {
                                      setTabColor(item.id, color)
                                      setThreadMenuOpenId(null)
                                    }}
                                    onExport={() => {
                                      setThreadMenuOpenId(null)
                                      void exportTranscript(chat)
                                    }}
                                    onInspect={() => {
                                      setThreadMenuOpenId(null)
                                      navigate(
                                        `/agents/${item.id}?inspect=1`
                                      )
                                    }}
                                    onArchive={() => {
                                      setThreadMenuOpenId(null)
                                      const nextLabel =
                                        chat.organizeLabel === 'archive'
                                          ? null
                                          : 'archive'
                                      void updateSession(chat, {
                                        organizeLabel: nextLabel
                                      })
                                      if (nextLabel === 'archive') {
                                        setCollapsedSidebarSections(
                                          current => ({
                                            ...current,
                                            archive: false
                                          })
                                        )
                                      }
                                    }}
                                    onDelete={() => {
                                      setThreadMenuOpenId(null)
                                      setDeleteTarget(chat)
                                    }}
                                  />
                                </PopoverContent>
                              </Popover>
                            </div>
                          </div>
                        </li>
                      )
                    })}
                    {remaining > 0 ? (
                      <li>
                        <button
                          type="button"
                          className="text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground w-full rounded-md px-2 py-1 text-left text-[12px]"
                          onClick={() =>
                            setVisibleBySection(current => ({
                              ...current,
                              [section.id]: limit + SECTION_PAGE_SIZE
                            }))
                          }
                        >
                          Load more
                          <span className="text-muted-foreground/70">
                            {' '}
                            · {remaining} remaining
                          </span>
                        </button>
                      </li>
                    ) : null}
                  </ul>
              </div>
            )
          })
        )}
      </div>
    </ScrollArea>
  )
}

/**
 * Item de grupo de split view en el sidebar. Se pinta como una fila con
 * chevron collapsible; los chats hijos aparecen anidados debajo con una
 * indent y una línea vertical sutil (Arc/Notion style). La memoria de
 * expand/collapse es local — cada grupo recuerda si está abierto o
 * cerrado durante la vida del componente.
 */
function SidebarGroupItem({
  group,
  chats,
  activeId,
  activeChildId,
  chatBySessionId,
  tabColors,
  selectedSessionIds,
  attentionIds,
  onSelectGroup,
  onRenameGroup,
  onDissolveGroup,
  onSelectChat,
  onSetGroupColor,
  projects,
  navigate,
  setTabColor,
  openRenameDialog,
  updateSession,
  exportTranscript,
  setDeleteTarget
}: {
  group: import('@sandwalk/agent-ui-core').SessionGroup
  chats: AgentSession[]
  activeId: string | null
  activeChildId: string | null
  chatBySessionId: Record<string, SessionChatState>
  tabColors: Record<string, string>
  selectedSessionIds: Set<string>
  attentionIds: ReadonlySet<string>
  onSelectGroup?: (groupId: string) => void
  onRenameGroup?: (group: import('@sandwalk/agent-ui-core').SessionGroup) => void
  onDissolveGroup?: (groupId: string) => void
  onSelectChat: (chatId: string) => void
  onSetGroupColor?: (groupId: string, color: string | null) => void
  projects: AgentProject[]
  navigate: NavigateFunction
  setTabColor: (id: string, color: string | null) => void
  openRenameDialog: (target: AgentSession) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  exportTranscript: (target: AgentSession) => void | Promise<void>
  setDeleteTarget: Dispatch<SetStateAction<AgentSession | null>>
}) {
  const [openChildMenuId, setOpenChildMenuId] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  // Dispara el modal destructivo compartido con la strip.
  const [dissolveConfirmOpen, setDissolveConfirmOpen] = useState(false)
  // Por defecto los splits arrancan CERRADOS en el sidebar (sin importar
  // cuándo se crearon). Solo si el usuario abrió este grupo alguna vez,
  // se restaura abierto en próximos renders. Ver `lib/sidebar-group-expanded`.
  const [expanded, setExpandedState] = useState(() =>
    isSidebarGroupExpanded(group.id)
  )
  const setExpanded = (next: boolean | ((current: boolean) => boolean)) => {
    setExpandedState(current => {
      const value = typeof next === 'function' ? next(current) : next
      setSidebarGroupExpanded(group.id, value)
      return value
    })
  }
  // El name es siempre no-vacío ahora (auto "Group N" al crear, o custom
  // tras rename). El badge con la cuenta de chats vive aparte, al lado.
  const label = group.name || `Group`
  const chatCount = group.chatIds.length
  const groupActive = group.id === activeId
  const activeInside = chats.some(chat => chat.id === activeId)

  return (
    <li>
      <div
        className={cn(
          'hover:bg-sidebar-accent/45 group/gr grid grid-cols-[minmax(0,1fr)_2.5rem] items-center rounded-md px-2 py-1.5',
          // El chip del grupo se ilumina tanto cuando el grupo es la ruta
          // directa (`groupActive`) como cuando el foco está en cualquier
          // chat hijo (`activeInside`). Así el usuario siempre tiene un
          // ancla visual en el sidebar sobre "dónde estoy".
          (groupActive || activeInside) && 'bg-sidebar-accent/55'
        )}
        onContextMenu={event => {
          event.preventDefault()
          setMenuOpen(true)
        }}
      >
        <div className="flex min-w-0 items-center gap-1">
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground -ml-1 grid size-4 shrink-0 place-items-center rounded"
            aria-expanded={expanded}
            aria-label={expanded ? 'Collapse group' : 'Expand group'}
            onClick={event => {
              event.stopPropagation()
              setExpanded(v => !v)
            }}
          >
            <ChevronDown
              className={cn(
                'size-3.5 transition-transform',
                !expanded && '-rotate-90'
              )}
            />
          </button>
          <button
            type="button"
            className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
            onClick={() => onSelectGroup?.(group.id)}
          >
            <Columns2 className="size-3.5 shrink-0" aria-hidden />
            <span
              className="bg-muted text-foreground/70 inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded px-1 text-[10px] font-semibold tabular-nums"
              aria-label={`${chatCount} chats`}
            >
              {chatCount}
            </span>
            {group.color ? (
              <span
                className="size-2 shrink-0 rounded-full border border-black/10"
                style={{ backgroundColor: group.color }}
                aria-hidden
              />
            ) : null}
            <SidebarMarqueeTitle text={label} />
          </button>
        </div>
        <Popover open={menuOpen} onOpenChange={setMenuOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              aria-label={`Options for ${label}`}
              className={cn(
                'text-muted-foreground hover:text-foreground hover:bg-muted justify-self-end rounded-md p-0.5 transition-opacity',
                menuOpen ? 'opacity-100' : 'opacity-0 group-hover/gr:opacity-100'
              )}
              onClick={event => event.stopPropagation()}
            >
              <MoreHorizontal className="size-3.5" />
            </button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-52 p-1">
            {onRenameGroup ? (
              <>
                <button
                  type="button"
                  className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px]"
                  onClick={() => {
                    setMenuOpen(false)
                    onRenameGroup(group)
                  }}
                >
                  Rename…
                </button>
                <div className="border-border/60 my-1 border-t" />
              </>
            ) : null}
            {onSetGroupColor ? (
              <div className="px-2 py-1.5">
                <div className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase tracking-wide">
                  Color
                </div>
                <TabInlineColorRow
                  value={group.color}
                  onSelect={value => onSetGroupColor(group.id, value)}
                  onClear={() => onSetGroupColor(group.id, null)}
                />
              </div>
            ) : null}
            {onSetGroupColor && onDissolveGroup ? (
              <div className="border-border/60 my-1 border-t" />
            ) : null}
            {onDissolveGroup ? (
              <button
                type="button"
                className="hover:bg-destructive/10 text-destructive flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px]"
                onClick={() => {
                  setMenuOpen(false)
                  setDissolveConfirmOpen(true)
                }}
              >
                Dissolve
              </button>
            ) : null}
          </PopoverContent>
        </Popover>
      </div>
      <GroupDissolveDialog
        group={dissolveConfirmOpen ? group : null}
        chats={chats}
        onCancel={() => setDissolveConfirmOpen(false)}
        onConfirm={() => {
          setDissolveConfirmOpen(false)
          onDissolveGroup?.(group.id)
        }}
      />
      {expanded ? (
        <ul
          className={cn(
            'border-border/40 ml-3 mt-0.5 space-y-px border-l pl-2',
            (groupActive || activeInside) && 'border-border/70'
          )}
        >
          {chats.map(chat => {
            // El chat "activo" dentro del grupo puede ser el `activeChildId`
            // (si estás en la ruta del grupo con foco en este chat) o el
            // `activeId` global si por alguna razón la ruta apunta al chat
            // suelto — ambos escenarios se marcan igual visualmente.
            const active =
              chat.id === activeChildId || chat.id === activeId
            const isSelected = selectedSessionIds.has(chat.id)
            const tabColor = tabColors[chat.id]
            const menuOpenForChat = openChildMenuId === chat.id
            return (
              <li key={chat.id}>
                <div
                  className={cn(
                    'group/child hover:bg-sidebar-accent/45 flex w-full min-w-0 items-center gap-1.5 rounded-md px-2 py-1 text-[12.5px]',
                    active && !isSelected && 'bg-sidebar-accent/55',
                    isSelected && 'bg-sidebar-accent'
                  )}
                  onContextMenu={event => {
                    event.preventDefault()
                    setOpenChildMenuId(chat.id)
                  }}
                >
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                    onClick={() => onSelectChat(chat.id)}
                  >
                    <span className="grid size-3.5 shrink-0 place-items-center">
                      <SessionStatusIcon
                        status={
                          chat.status === 'awaiting_approval' ||
                          chatBySessionId[chat.id]?.pendingApproval
                            ? 'awaiting_approval'
                            : chatBySessionId[chat.id]?.runActive
                              ? 'running'
                              : chat.status
                        }
                      />
                    </span>
                    {attentionIds.has(chat.id) ? (
                      <span
                        className="size-1.5 shrink-0 rounded-full border border-black/10"
                        style={{ backgroundColor: UNREAD_DOT_COLOR }}
                        aria-label="Unread"
                      />
                    ) : null}
                    {tabColor ? (
                      <span
                        className="size-1.5 shrink-0 rounded-full border border-black/10"
                        style={{ backgroundColor: tabColor }}
                        aria-hidden
                      />
                    ) : null}
                    <SidebarMarqueeTitle text={chat.title || 'Untitled'} />
                  </button>
                  <Popover
                    open={menuOpenForChat}
                    onOpenChange={open =>
                      setOpenChildMenuId(open ? chat.id : null)
                    }
                  >
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        aria-label="Chat options"
                        className={cn(
                          'text-muted-foreground hover:text-foreground hover:bg-muted shrink-0 rounded-md p-0.5 transition-opacity',
                          menuOpenForChat
                            ? 'opacity-100'
                            : 'opacity-0 group-hover/child:opacity-100'
                        )}
                        onClick={event => event.stopPropagation()}
                      >
                        <MoreHorizontal className="size-3.5" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent
                      align="start"
                      className="w-52 p-1.5"
                    >
                      <SessionActionsMenu
                        session={chat}
                        projects={projects}
                        tabColor={tabColor || null}
                        onRename={() => {
                          setOpenChildMenuId(null)
                          openRenameDialog(chat)
                        }}
                        onTogglePin={() => {
                          setOpenChildMenuId(null)
                          void updateSession(chat, {
                            organizeLabel:
                              chat.organizeLabel === 'pinned'
                                ? null
                                : 'pinned'
                          })
                        }}
                        onMoveToProject={projectId => {
                          setOpenChildMenuId(null)
                          void updateSession(chat, { projectId })
                        }}
                        onSetTabColor={color => {
                          setTabColor(chat.id, color)
                          setOpenChildMenuId(null)
                        }}
                        onExport={() => {
                          setOpenChildMenuId(null)
                          void exportTranscript(chat)
                        }}
                        onInspect={() => {
                          setOpenChildMenuId(null)
                          navigate(`/agents/${chat.id}?inspect=1`)
                        }}
                        onArchive={() => {
                          setOpenChildMenuId(null)
                          void updateSession(chat, {
                            organizeLabel:
                              chat.organizeLabel === 'archive'
                                ? null
                                : 'archive'
                          })
                        }}
                        onDelete={() => {
                          setOpenChildMenuId(null)
                          setDeleteTarget(chat)
                        }}
                      />
                    </PopoverContent>
                  </Popover>
                </div>
              </li>
            )
          })}
        </ul>
      ) : null}
    </li>
  )
}

