import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronDown,
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
import { SessionSourceIcon } from '@/components/agents/SessionSourceIcon'
import { SessionStatusIcon } from '@/components/agents/SessionStatusIcon'
import { TAB_INLINE_COLORS } from '@/components/agents/tab-context-menu'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useSessionAttentionIds } from '@/hooks/useSessionAttention'
import { groupSessions, relativeTime, type SessionChatState } from '@/lib/sessions'
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

type SessionSection = ReturnType<typeof groupSessions>[number]

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
  onClearSessionSelection
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
            const collapsed = Boolean(collapsedSidebarSections[section.id])
            const limit = visibleBySection[section.id] ?? SECTION_PAGE_SIZE
            const visibleItems = section.items.slice(0, limit)
            const remaining = Math.max(0, section.items.length - visibleItems.length)
            return (
              <div key={section.id} className="space-y-0.5">
                <button
                  type="button"
                  className="text-muted-foreground/80 hover:text-foreground flex w-full items-center gap-1 rounded-md px-2 py-0.5 text-left text-[12px]"
                  aria-expanded={!collapsed}
                  onClick={() =>
                    setCollapsedSidebarSections(current => ({
                      ...current,
                      [section.id]: !current[section.id]
                    }))
                  }
                >
                  <ChevronDown
                    className={cn(
                      'size-3.5 shrink-0 transition-transform',
                      collapsed && '-rotate-90'
                    )}
                  />
                  <span className="min-w-0 flex-1 truncate">
                    {section.title}
                  </span>
                  <span className="sandwalk-notification-count text-muted-foreground/60 shrink-0 text-[11px] tabular-nums">
                    {section.items.length}
                  </span>
                </button>
                {!collapsed ? (
                  <ul className="space-y-px">
                    {visibleItems.map(item => {
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
                                    ? `Deselect ${item.title || 'chat'}`
                                    : `Select ${item.title || 'chat'}`
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
                                      item.status === 'awaiting_approval' ||
                                      chatBySessionId[item.id]?.pendingApproval
                                        ? 'awaiting_approval'
                                        : chatBySessionId[item.id]?.runActive
                                          ? 'running'
                                          : item.status
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
                                  openSessionTab(item.id)
                                  void prefetchSessionMessages(item.id)
                                  navigate(`/agents/${item.id}`)
                                }}
                              >
                              <SessionSourceIcon
                                source={item.source}
                                label={item.sourceLabel}
                              />
                              {item.organizeLabel === 'pinned' ? (
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
                                text={item.title || 'Untitled'}
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
                                  item.lastMessageAt || item.updatedAt
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
                                    session={item}
                                    projects={projects}
                                    tabColor={tabColor || null}
                                    onRename={() => {
                                      setThreadMenuOpenId(null)
                                      openRenameDialog(item)
                                    }}
                                    onTogglePin={() => {
                                      setThreadMenuOpenId(null)
                                      void updateSession(item, {
                                        organizeLabel:
                                          item.organizeLabel === 'pinned'
                                            ? null
                                            : 'pinned'
                                      })
                                    }}
                                    onMoveToProject={projectId => {
                                      setThreadMenuOpenId(null)
                                      void updateSession(item, { projectId })
                                    }}
                                    onSetTabColor={color => {
                                      setTabColor(item.id, color)
                                      setThreadMenuOpenId(null)
                                    }}
                                    onExport={() => {
                                      setThreadMenuOpenId(null)
                                      void exportTranscript(item)
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
                                        item.organizeLabel === 'archive'
                                          ? null
                                          : 'archive'
                                      void updateSession(item, {
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
                                      setDeleteTarget(item)
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
                ) : null}
              </div>
            )
          })
        )}
      </div>
    </ScrollArea>
  )
}
