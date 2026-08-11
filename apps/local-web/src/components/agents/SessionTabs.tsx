import type { AgentSession } from '@sandwalk/agent-ui-core'
import {
  closestCenter,
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent
} from '@dnd-kit/core'
import {
  arrayMove,
  horizontalListSortingStrategy,
  SortableContext
} from '@dnd-kit/sortable'
import {
  Archive,
  ChevronDown,
  CircleX,
  Download,
  Pencil,
  Pin,
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
  onDelete
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

  const orderKey = sortableIds.join('\0')

  // Auto-scroll active tab into view when the active id changes.
  useEffect(() => {
    const strip = stripRef.current
    if (!strip || !activeId) return
    const tabEl = strip.querySelector(
      `[data-tab-id="${CSS.escape(activeId)}"]`
    )
    if (!(tabEl instanceof HTMLElement)) return
    const stripRect = strip.getBoundingClientRect()
    const tabRect = tabEl.getBoundingClientRect()
    const outOfView =
      tabRect.left < stripRect.left || tabRect.right > stripRect.right
    if (!outOfView) return
    const targetLeft =
      tabEl.offsetLeft - (strip.clientWidth - tabEl.offsetWidth) / 2
    strip.scrollTo({ left: Math.max(0, targetLeft), behavior: 'smooth' })
  }, [activeId, orderKey])

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
            </div>
          </SortableContext>
        </DndContext>
      </div>

      {/*
        Right-hand panel: full navigator of all tabs (search + list with state +
        time). Not an "overflow" list anymore — it always shows every tab.
      */}
      <div className="sandwalk-tab-overflow-slot">
        <Popover open={searchOpen} onOpenChange={setSearchOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className={cn(
                'sandwalk-tab-overflow-btn inline-flex h-7 items-center justify-center gap-1 rounded-lg',
                'pl-2.5 pr-2',
                'bg-black/[0.06] text-foreground/85',
                'hover:bg-black/[0.1] hover:text-foreground',
                'dark:bg-white/[0.1] dark:text-zinc-100',
                'dark:hover:bg-white/[0.16] dark:hover:text-white',
                searchOpen &&
                  'bg-black/[0.12] text-foreground dark:bg-white/[0.18] dark:text-white'
              )}
              aria-label={`Todos los tabs (${orderedTabs.length})`}
              title="Todos los tabs"
            >
              <ChevronDown className="size-3.5 shrink-0 stroke-[2.25]" />
              {orderedTabs.length > 0 ? (
                <span className="text-[11px] font-semibold tabular-nums leading-none">
                  {orderedTabs.length}
                </span>
              ) : null}
            </button>
          </PopoverTrigger>
          <PopoverContent
            align="end"
            sideOffset={6}
            className="w-[22rem] overflow-hidden rounded-xl p-0"
            onOpenAutoFocus={event => event.preventDefault()}
          >
            <div className="border-border/70 flex items-center gap-2 border-b px-3 py-2">
              <Search className="text-muted-foreground size-3.5 shrink-0" />
              <Input
                ref={searchInputRef}
                value={searchQuery}
                onChange={event => setSearchQuery(event.target.value)}
                placeholder="Buscar por nombre"
                className="h-7 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
              />
              <span className="text-muted-foreground/70 shrink-0 text-[10px] tabular-nums">
                ⇧⌘A
              </span>
            </div>
            <div className="text-muted-foreground flex items-center justify-between px-3 py-1.5 text-[10px] font-medium tracking-wide uppercase">
              <span>Todos los tabs</span>
              <span className="tabular-nums">{orderedTabs.length}</span>
            </div>
            <div className="max-h-72 overflow-y-auto overscroll-contain">
              <div className="p-1.5 pt-0">
                {filteredSearchTabs.length === 0 ? (
                  <p className="text-muted-foreground px-2 py-6 text-center text-xs">
                    Sin coincidencias
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
                        className={cn(
                          'group/item hover:bg-muted flex items-center gap-2 rounded-lg px-2 py-2',
                          active && 'bg-muted'
                        )}
                      >
                        <button
                          type="button"
                          className="flex min-w-0 flex-1 items-center gap-2 text-left"
                          onClick={() => {
                            onSelect(tab.id)
                            setSearchOpen(false)
                          }}
                        >
                          <span className="bg-muted/80 flex size-7 shrink-0 items-center justify-center rounded-md">
                            <SessionStatusIcon status={tab.status} />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="flex items-center gap-2">
                              <span className="text-foreground min-w-0 flex-1 truncate text-sm font-medium">
                                {title}
                              </span>
                              <span className="text-muted-foreground shrink-0 text-[11px] tabular-nums">
                                {stamp}
                              </span>
                            </span>
                            <span className="text-muted-foreground block truncate text-[11px]">
                              {tab.sourceLabel || tab.source || 'Agent'}
                              {tab.organizeLabel === 'pinned' ? ' · Pinned' : ''}
                            </span>
                          </span>
                        </button>
                        <button
                          type="button"
                          className="text-muted-foreground hover:text-foreground inline-flex size-6 shrink-0 items-center justify-center rounded-md opacity-0 group-hover/item:opacity-100"
                          aria-label={`Close ${title}`}
                          onClick={event => {
                            event.stopPropagation()
                            onClose(tab.id)
                          }}
                        >
                          <X className="size-3.5" />
                        </button>
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
