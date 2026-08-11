import type { AgentSession, SessionGroup } from '@sandwalk/agent-ui-core'
import {
  closestCenter,
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent
} from '@dnd-kit/core'
import {
  restrictToHorizontalAxis,
  restrictToParentElement
} from '@dnd-kit/modifiers'
import {
  arrayMove,
  horizontalListSortingStrategy,
  SortableContext
} from '@dnd-kit/sortable'
import {
  Archive,
  ChevronDown,
  CircleX,
  Columns2,
  Download,
  Pencil,
  Pin,
  Plus,
  Search,
  Trash2,
  X
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { useSessionAttentionIds } from '@/hooks/useSessionAttention'
import { relativeTime } from '@/lib/sessions'
import { cn } from '@/lib/utils'

import { SessionStatusIcon } from './SessionStatusIcon'
import { useSessionTabColors } from './session-tab-colors'
import { SessionTab } from './SessionTab'
import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator,
  TabInlineColorRow
} from './tab-context-menu'

import './session-chrome-tabs.css'

/** Height of the two chrome-tab overflow buttons (all-tabs + new-agent). */
const OVERFLOW_BTN_HEIGHT = 'h-[30px]'

type TabContextMenuState = {
  sessionId: string
  x: number
  y: number
}

export function SessionTabs({
  tabs,
  activeId,
  onSelect,
  onClose,
  onCloseOthers,
  onReorder,
  onRename,
  onTogglePin,
  onExport,
  onInspect,
  onArchive,
  onDelete,
  onCreateSession,
  groups,
  onSplitWith,
  onDissolveGroup
}: {
  tabs: AgentSession[]
  activeId: string | null
  onSelect: (id: string) => void
  onClose: (id: string) => void
  onCloseOthers: (id: string) => void
  onReorder?: (orderedIds: string[]) => void
  onRename: (session: AgentSession) => void
  onTogglePin: (session: AgentSession) => void
  onExport: (session: AgentSession) => void
  onInspect: (session: AgentSession) => void
  onArchive: (session: AgentSession) => void
  onDelete: (session: AgentSession) => void
  /** Opens a fresh draft agent session (only persists on first message). */
  onCreateSession?: () => void
  /** Split-view groups that live in this project scope. Rendered as
   *  additional chip-tabs after the session tabs. */
  groups?: SessionGroup[]
  /** Creates a new split-view group from `sourceId` + the next open tab. */
  onSplitWith?: (sourceId: string) => void
  onDissolveGroup?: (groupId: string) => void
}) {
  const [menu, setMenu] = useState<TabContextMenuState | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const { tabColors, setTabColor } = useSessionTabColors()
  const attentionIds = useSessionAttentionIds()
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const stripRef = useRef<HTMLDivElement | null>(null)

  const draggable = Boolean(onReorder)
  const sensors = useSensors(
    useSensor(PointerSensor, {
      // Small distance keeps a plain click from starting a drag.
      activationConstraint: { distance: 4 }
    })
  )

  // Pinned first, then the rest (Chrome pin cluster).
  const orderedTabs = useMemo(() => {
    const pinned: AgentSession[] = []
    const rest: AgentSession[] = []
    for (const tab of tabs) {
      if (tab.organizeLabel === 'pinned') pinned.push(tab)
      else rest.push(tab)
    }
    return [...pinned, ...rest]
  }, [tabs])

  const sortableIds = useMemo(
    () => orderedTabs.map(tab => tab.id),
    [orderedTabs]
  )



  // Auto-scroll active tab so it's fully in view:
  //   first tab  → snap to the strip's left edge
  //   last tab   → snap to the right edge (fade removed via [data-last-active])
  //   otherwise  → center it in the viewport
  // First mount uses instant scroll (auto) so entering the section shows the
  // tab already correctly positioned; later changes animate smoothly.
  const didScrollOnceRef = useRef(false)
  useEffect(() => {
    const strip = stripRef.current
    if (!strip || !activeId) return
    const tabEl = strip.querySelector(
      `[data-tab-id="${CSS.escape(activeId)}"]`
    )
    if (!(tabEl instanceof HTMLElement)) return

    const idx = orderedTabs.findIndex(tab => tab.id === activeId)
    if (idx < 0) return
    const isFirst = idx === 0
    const isLast = idx === orderedTabs.length - 1

    let targetLeft: number
    if (isFirst) {
      targetLeft = 0
    } else if (isLast) {
      targetLeft = strip.scrollWidth - strip.clientWidth
    } else {
      targetLeft =
        tabEl.offsetLeft - (strip.clientWidth - tabEl.offsetWidth) / 2
    }

    const behavior: ScrollBehavior = didScrollOnceRef.current
      ? 'smooth'
      : 'auto'
    strip.scrollTo({ left: Math.max(0, targetLeft), behavior })
    didScrollOnceRef.current = true
  }, [activeId, sortableIds, orderedTabs])

  const filteredSearchTabs = useMemo(() => {
    const needle = searchQuery.trim().toLowerCase()
    if (!needle) return orderedTabs
    return orderedTabs.filter(tab =>
      (tab.title || 'Untitled').toLowerCase().includes(needle)
    )
  }, [orderedTabs, searchQuery])

  useEffect(() => {
    if (!searchOpen) {
      setSearchQuery('')
      return
    }
    const timer = window.setTimeout(() => searchInputRef.current?.focus(), 20)
    return () => window.clearTimeout(timer)
  }, [searchOpen])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || !event.shiftKey) return
      if (event.key.toLowerCase() !== 'a') return
      event.preventDefault()
      setSearchOpen(true)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const menuSession = menu
    ? tabs.find(tab => tab.id === menu.sessionId) || null
    : null

  const runAction = (action: () => void) => {
    setMenu(null)
    action()
  }

  const handleDragEnd = (event: DragEndEvent) => {
    if (!onReorder) return
    const { active, over } = event
    if (!over || active.id === over.id) return
    const fromIndex = sortableIds.indexOf(String(active.id))
    const toIndex = sortableIds.indexOf(String(over.id))
    if (fromIndex < 0 || toIndex < 0) return
    const nextIds = arrayMove(sortableIds, fromIndex, toIndex)
    // Pinned cluster is always kept at the front.
    const byId = new Map(orderedTabs.map(tab => [tab.id, tab]))
    const pinned = nextIds.filter(
      id => byId.get(id)?.organizeLabel === 'pinned'
    )
    const rest = nextIds.filter(
      id => byId.get(id)?.organizeLabel !== 'pinned'
    )
    onReorder([...pinned, ...rest])
  }

  const openContextMenu = (id: string, event: React.MouseEvent) => {
    setMenu({ sessionId: id, x: event.clientX, y: event.clientY })
  }

  return (
    <div className="relative z-[1] flex min-w-0 flex-1 items-end">
      <div ref={stripRef} className="sandwalk-tab-strip-main">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
          modifiers={[restrictToHorizontalAxis, restrictToParentElement]}
        >
          <SortableContext
            items={sortableIds}
            strategy={horizontalListSortingStrategy}
          >
            <div className="sandwalk-chrome-tabs">
              {orderedTabs.map(tab => (
                <SessionTab
                  key={tab.id}
                  tab={tab}
                  active={tab.id === activeId}
                  color={tabColors[tab.id]}
                  unread={attentionIds.has(tab.id)}
                  draggable={draggable}
                  onSelect={onSelect}
                  onClose={onClose}
                  onContextMenu={openContextMenu}
                />
              ))}
              {groups && groups.length > 0
                ? groups.map(group => (
                    <SessionGroupTab
                      key={group.id}
                      group={group}
                      active={group.id === activeId}
                      onSelect={onSelect}
                      onDissolve={onDissolveGroup}
                    />
                  ))
                : null}
            </div>
          </SortableContext>
        </DndContext>
      </div>

      {/*
        Right-hand "New agent" button — opens a draft session (composer only).
        Nothing persists in the backend until the user sends the first message.
      */}
      {onCreateSession ? (
        <div className="sandwalk-tab-new-slot">
          <TooltipProvider delayDuration={300}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className={cn(
                    `sandwalk-tab-overflow-btn inline-flex ${OVERFLOW_BTN_HEIGHT} items-center justify-center gap-1 rounded-lg`,
                    'px-2.5',
                    'bg-black/[0.06] text-foreground/85',
                    'hover:bg-black/[0.1] hover:text-foreground',
                    'dark:bg-white/[0.1] dark:text-zinc-100',
                    'dark:hover:bg-white/[0.16] dark:hover:text-white'
                  )}
                  aria-label="New agent"
                  onClick={onCreateSession}
                >
                  <Plus className="size-3.5 shrink-0" />
                </button>
              </TooltipTrigger>
              <TooltipContent
                side="bottom"
                className="flex items-center gap-2"
              >
                <span>New agent</span>
                <kbd className="text-muted-foreground/80 rounded border px-1 text-[10px] tabular-nums">
                  ⌘N
                </kbd>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      ) : null}

      {/*
        Right-hand panel: full navigator of all tabs (search + list with state +
        time). Not an "overflow" list anymore — it always shows every tab.
      */}
      <div className="sandwalk-tab-overflow-slot">
        <Popover open={searchOpen} onOpenChange={setSearchOpen}>
          <TooltipProvider delayDuration={300}>
            <Tooltip>
              <TooltipTrigger asChild>
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    className={cn(
                      `sandwalk-tab-overflow-btn inline-flex ${OVERFLOW_BTN_HEIGHT} items-center justify-center gap-1 rounded-lg`,
                      'pl-2.5 pr-2',
                      'bg-black/[0.06] text-foreground/85',
                      'hover:bg-black/[0.1] hover:text-foreground',
                      'dark:bg-white/[0.1] dark:text-zinc-100',
                      'dark:hover:bg-white/[0.16] dark:hover:text-white',
                      searchOpen &&
                        'bg-black/[0.12] text-foreground dark:bg-white/[0.18] dark:text-white'
                    )}
                    aria-label={`All tabs (${orderedTabs.length})`}
                  >
                    <ChevronDown className="size-3.5 shrink-0 stroke-[2.25]" />
                    {orderedTabs.length > 0 ? (
                      <span className="text-[11px] font-semibold tabular-nums leading-none">
                        {orderedTabs.length}
                      </span>
                    ) : null}
                  </button>
                </PopoverTrigger>
              </TooltipTrigger>
              <TooltipContent
                side="bottom"
                className="flex items-center gap-2"
              >
                <span>All tabs</span>
                <kbd className="text-muted-foreground/80 rounded border px-1 text-[10px] tabular-nums">
                  ⌘⇧A
                </kbd>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <PopoverContent
            align="start"
            sideOffset={6}
            className="w-[22rem] overflow-hidden rounded-xl p-0"
            /* Non-modal so tab-strip scrollTo() and other background
             * side-effects don't count as "outside interaction". */
            onOpenAutoFocus={event => event.preventDefault()}
            onCloseAutoFocus={event => event.preventDefault()}
            onFocusOutside={event => event.preventDefault()}
            onInteractOutside={event => {
              // Keep the panel open on strip scroll / gutter clicks, BUT
              // let it close when the user clicks a specific tab so the
              // panel doesn't linger over a fresh selection.
              const target = event.target as Node | null
              if (
                target instanceof HTMLElement &&
                target.closest('.sandwalk-tab-strip-main') &&
                !target.closest('.chrome-tab')
              ) {
                event.preventDefault()
              }
            }}
          >
            <div className="border-border/70 flex items-center gap-2 border-b px-3 py-2">
              <Search className="text-muted-foreground size-3.5 shrink-0" />
              <Input
                ref={searchInputRef}
                value={searchQuery}
                onChange={event => setSearchQuery(event.target.value)}
                placeholder="Search by name"
                className="h-7 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
              />
              <span className="text-muted-foreground/70 shrink-0 text-[10px] tabular-nums">
                ⇧⌘A
              </span>
            </div>
            <div className="max-h-[32rem] overflow-y-auto overscroll-contain">
              <div className="p-1.5" role="listbox" aria-label="Session tabs">
                {filteredSearchTabs.length === 0 ? (
                  <p className="text-muted-foreground px-2 py-6 text-center text-xs">
                    No matches
                  </p>
                ) : (
                  filteredSearchTabs.map(tab => {
                    const active = tab.id === activeId
                    const title = tab.title || 'Untitled'
                    const stamp = relativeTime(
                      tab.lastMessageAt || tab.updatedAt || tab.createdAt
                    )
                    return (
                      <div
                        key={tab.id}
                        role="option"
                        aria-selected={active}
                        tabIndex={0}
                        className={cn(
                          'group/item hover:bg-muted flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                          active && 'bg-muted'
                        )}
                        onClick={() => onSelect(tab.id)}
                        onKeyDown={event => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            onSelect(tab.id)
                          }
                        }}
                        onContextMenu={event => {
                          event.preventDefault()
                          openContextMenu(tab.id, event)
                        }}
                      >
                        <span className="bg-muted/80 flex size-7 shrink-0 items-center justify-center rounded-md">
                          <SessionStatusIcon status={tab.status} />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-2">
                            {tabColors[tab.id] ? (
                              <span
                                className="size-2 shrink-0 rounded-full border border-black/10"
                                style={{
                                  backgroundColor: tabColors[tab.id]
                                }}
                                aria-hidden
                              />
                            ) : null}
                            <span className="text-foreground min-w-0 flex-1 truncate text-sm font-medium">
                              {title}
                            </span>
                            {/*
                              Stamp and close X share the same slot: the stamp
                              fades out on item hover while the X fades in in
                              its place. Fixed min-width keeps the layout stable.
                            */}
                            <span
                              className="relative block h-4 shrink-0"
                              style={{ width: 28 }}
                            >
                              <span className="text-muted-foreground absolute inset-0 inline-flex items-center justify-center text-[11px] tabular-nums transition-opacity group-hover/item:opacity-0">
                                {stamp}
                              </span>
                              <button
                                type="button"
                                className="text-muted-foreground hover:text-foreground absolute inset-0 inline-flex items-center justify-center rounded-md opacity-0 transition-opacity group-hover/item:opacity-100"
                                aria-label={`Close ${title}`}
                                onClick={event => {
                                  event.stopPropagation()
                                  onClose(tab.id)
                                }}
                              >
                                <X className="size-3.5" />
                              </button>
                            </span>
                          </span>
                          {tab.organizeLabel === 'pinned' ? (
                            <span className="text-muted-foreground mt-0.5 flex items-center gap-1 text-[11px]">
                              <Pin
                                className="size-3 shrink-0"
                                aria-hidden
                              />
                              Pinned
                            </span>
                          ) : null}
                        </span>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          </PopoverContent>
        </Popover>
      </div>

      {menu && menuSession ? (
        <TabContextMenuShell
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
        >
          <TabContextItem
            icon={<Pencil className="size-3.5" />}
            label="Rename…"
            onClick={() => runAction(() => onRename(menuSession))}
          />
          <TabContextItem
            icon={<Pin className="size-3.5" />}
            label={menuSession.organizeLabel === 'pinned' ? 'Unpin' : 'Pin'}
            onClick={() => runAction(() => onTogglePin(menuSession))}
          />
          <TabContextSeparator />
          <TabInlineColorRow
            value={tabColors[menuSession.id] || null}
            onSelect={color => {
              setTabColor(menuSession.id, color)
              setMenu(null)
            }}
            onClear={() => {
              setTabColor(menuSession.id, null)
              setMenu(null)
            }}
          />
          <TabContextSeparator />
          <TabContextItem
            icon={<Download className="size-3.5" />}
            label="Export session"
            onClick={() => runAction(() => onExport(menuSession))}
          />
          <TabContextItem
            icon={<Search className="size-3.5" />}
            label="Inspect chat"
            onClick={() => runAction(() => onInspect(menuSession))}
          />
          <TabContextItem
            icon={<Archive className="size-3.5" />}
            label={
              menuSession.organizeLabel === 'archive' ? 'Unarchive' : 'Archive'
            }
            onClick={() => runAction(() => onArchive(menuSession))}
          />
          {onSplitWith && tabs.length >= 2 ? (
            <>
              <TabContextSeparator />
              <TabContextItem
                icon={<Columns2 className="size-3.5" />}
                label="Split with next tab"
                onClick={() => runAction(() => onSplitWith(menuSession.id))}
              />
            </>
          ) : null}
          <TabContextSeparator />
          <TabContextItem
            icon={<X className="size-3.5" />}
            label="Close"
            onClick={() => runAction(() => onClose(menuSession.id))}
          />
          <TabContextItem
            icon={<CircleX className="size-3.5" />}
            label="Close others"
            disabled={tabs.length <= 1}
            onClick={() => runAction(() => onCloseOthers(menuSession.id))}
          />
          <TabContextSeparator />
          <TabContextItem
            icon={<Trash2 className="size-3.5" />}
            label="Delete"
            destructive
            onClick={() => runAction(() => onDelete(menuSession))}
          />
        </TabContextMenuShell>
      ) : null}
    </div>
  )
}

/**
 * Grupo de split-view renderizado como una pestaña adicional al final de la
 * strip. Muestra icono de columnas + nombre del grupo (o `N chats` como
 * fallback) + botón para disolver.
 *
 * MVP visual: chip discreto que se pinta activo cuando la ruta apunta al
 * grupo. Fase 5 completa: pintar chats internos como sub-pestañas, color
 * de grupo, pin, reorder.
 */
function SessionGroupTab({
  group,
  active,
  onSelect,
  onDissolve
}: {
  group: SessionGroup
  active: boolean
  onSelect: (id: string) => void
  onDissolve?: (groupId: string) => void
}) {
  const label = group.name || `${group.chatIds.length} chats`
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={() => onSelect(group.id)}
      className={cn(
        'sandwalk-chrome-tab group/tab relative inline-flex h-[30px] shrink-0 items-center gap-1.5 rounded-t-lg px-2.5 text-[12px]',
        'text-foreground/85 hover:text-foreground',
        active
          ? 'bg-background text-foreground shadow-[inset_0_0_0_1px_hsl(var(--border))]'
          : 'bg-black/[0.04] hover:bg-black/[0.08] dark:bg-white/[0.06] dark:hover:bg-white/[0.1]'
      )}
      title={`Split view: ${label}`}
    >
      <Columns2 className="size-3.5 shrink-0" aria-hidden />
      <span className="max-w-[16ch] truncate">{label}</span>
      <span className="bg-black/10 text-foreground/70 dark:bg-white/15 rounded-md px-1 text-[10px] font-semibold tabular-nums leading-none">
        {group.chatIds.length}
      </span>
      {onDissolve ? (
        <span
          role="button"
          tabIndex={-1}
          aria-label={`Dissolve group ${label}`}
          className="text-muted-foreground hover:text-foreground -mr-0.5 ml-0.5 inline-flex size-4 items-center justify-center rounded-md opacity-0 transition-opacity group-hover/tab:opacity-100"
          onClick={event => {
            event.stopPropagation()
            onDissolve(group.id)
          }}
        >
          <X className="size-3" />
        </span>
      ) : null}
    </button>
  )
}
