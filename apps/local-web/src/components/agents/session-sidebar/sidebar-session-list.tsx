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
        className="space-y-3 p-3 transition-opacity duration-150 ease-out"
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
              <div key={section.id} className="space-y-1">
                <button
                  type="button"
                  className="text-muted-foreground/80 hover:text-foreground flex w-full items-center gap-1 rounded-lg px-2 py-0.5 text-left text-[13px]"
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
                  <ul className="space-y-0.5">
                    {visibleItems.map(item => {
                      const isSelected = selectedSessionIds.has(item.id)
                      const tabColor = tabColors[item.id]
                      return (
                        <li key={item.id}>
                          <div
                            className={cn(
                              'hover:bg-sidebar-accent/50 group grid grid-cols-[minmax(0,1fr)_2.75rem] items-center rounded-lg px-2 py-1.5',
                              item.id === sessionId && 'bg-sidebar-accent/55',
                              isSelected &&
                                'bg-sidebar-accent/55 ring-primary/30 ring-1'
                            )}
                            onContextMenu={event => {
                              event.preventDefault()
                              setThreadMenuOpenId(item.id)
                            }}
                          >
                            <button
                              type="button"
                              className="flex min-w-0 items-center gap-1.5 text-left"
                              onClick={(event: MouseEvent<HTMLButtonElement>) => {
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
                                if (selectedSessionIds.size > 0) {
                                  onClearSessionSelection()
                                }
                                setSelectionAnchorId(item.id)
                                openSessionTab(item.id)
                                void prefetchSessionMessages(item.id)
                                navigate(`/agents/${item.id}`)
                              }}
                            >
                              {isSelected || selectedSessionIds.size > 0 ? (
                                <span
                                  className={cn(
                                    'grid size-3.5 shrink-0 place-items-center rounded-[4px] border',
                                    isSelected
                                      ? 'border-primary bg-primary text-primary-foreground'
                                      : 'border-muted-foreground/40'
                                  )}
                                  aria-hidden
                                >
                                  {isSelected ? (
                                    <Check
                                      className="size-2.5"
                                      strokeWidth={3}
                                    />
                                  ) : null}
                                </span>
                              ) : (
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
                              <span className="text-foreground/90 group-hover:text-foreground truncate text-[13px]">
                                {item.title || 'Untitled'}
                              </span>
                            </button>
                            <div className="relative h-7 w-11 justify-self-end">
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
                                      'text-muted-foreground hover:bg-muted absolute right-0 top-0 inline-flex h-7 w-7 items-center justify-center rounded-md',
                                      threadMenuOpenId === item.id
                                        ? 'opacity-100'
                                        : 'opacity-0 group-hover:opacity-100'
                                    )}
                                    aria-label="Thread options"
                                  >
                                    <MoreHorizontal className="h-4 w-4" />
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
                          className="text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground w-full rounded-lg px-2 py-1.5 text-left text-[12px]"
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
