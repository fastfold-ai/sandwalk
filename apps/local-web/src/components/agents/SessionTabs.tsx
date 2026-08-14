import type {
  AgentProject,
  AgentSession,
  SessionGroup
} from '@sandwalk/agent-ui-core'
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
  Folder,
  Pencil,
  Pin,
  Plus,
  Search,
  Trash2,
  X
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
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

import { ProjectPicker } from './ProjectPicker'
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
  onMoveToProject,
  projects,
  onDelete,
  onCreateSession,
  groups,
  openTabIds,
  onSplitWith,
  onDissolveGroup,
  onRenameGroup,
  onSetGroupColor,
  onCloseGroup,
  selectedChatIds,
  onToggleSelectChat,
  onClearSelection,
  onCreateSplitFromSelection
}: {
  tabs: AgentSession[]
  activeId: string | null
  /**
   * Orden real de la strip (`openTabIds`) mezclando IDs de sesión y de
   * grupo. Cuando se provee, la strip lo usa como fuente de verdad y
   * renderiza cada item (chat o grupo) en el lugar exacto que le
   * corresponde. Sin él, cae al comportamiento anterior (chats primero,
   * grupos al final).
   */
  openTabIds?: string[]
  onSelect: (id: string) => void
  onClose: (id: string) => void
  onCloseOthers: (id: string) => void
  onReorder?: (orderedIds: string[]) => void
  onRename: (session: AgentSession) => void
  onTogglePin: (session: AgentSession) => void
  onExport: (session: AgentSession) => void
  onInspect: (session: AgentSession) => void
  onArchive: (session: AgentSession) => void
  onMoveToProject?: (session: AgentSession, projectId: string | null) => void
  projects?: AgentProject[]
  onDelete: (session: AgentSession) => void
  /** Opens a fresh draft agent session (only persists on first message). */
  onCreateSession?: () => void
  /** Split-view groups that live in this project scope. Rendered as
   *  additional chip-tabs after the session tabs. */
  groups?: SessionGroup[]
  /** Creates a new split-view group from `sourceId` + the next open tab. */
  onSplitWith?: (sourceId: string) => void
  onDissolveGroup?: (groupId: string) => void
  onRenameGroup?: (group: SessionGroup) => void
  onSetGroupColor?: (groupId: string, color: string | null) => void
  onCloseGroup?: (groupId: string) => void
  selectedChatIds?: Set<string>
  onToggleSelectChat?: (id: string) => void
  onClearSelection?: () => void
  onCreateSplitFromSelection?: () => void
}) {
  const [menu, setMenu] = useState<TabContextMenuState | null>(null)
  // Modal de confirmación para "Delete Split View": la acción disuelve el
  // grupo (los chats vuelven a ser conversaciones sueltas) — irreversible
  // en tanto la agrupación se pierde, pero ningún chat se borra.
  const [dissolveConfirm, setDissolveConfirm] = useState<SessionGroup | null>(
    null
  )
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

  /*
   * Modelo unificado de la strip: cada item es un chat (sesión) o un grupo
   * (split view). Los dos se renderizan con el mismo <SessionTab>, comparten
   * el mismo SortableContext y respetan el orden real de `openTabIds`.
   * Los pinned se agrupan al frente (Chrome pin cluster) sean chats o grupos.
   */
  type TabItem =
    | { kind: 'chat'; id: string; session: AgentSession; pinned: boolean }
    | {
        kind: 'group'
        id: string
        group: SessionGroup
        pinned: boolean
      }

  const tabsById = useMemo(() => {
    const map = new Map<string, AgentSession>()
    for (const tab of tabs) map.set(tab.id, tab)
    return map
  }, [tabs])

  const groupsById = useMemo(() => {
    const map = new Map<string, SessionGroup>()
    for (const g of groups ?? []) map.set(g.id, g)
    return map
  }, [groups])

  const orderedItems = useMemo<TabItem[]>(() => {
    // Cuando el caller nos pasa openTabIds, respetamos ese orden exacto,
    // mezclando chats y grupos. Cuando no, hacemos el fallback antiguo
    // (chats primero por orden, grupos al final) para no romper otros usos.
    const items: TabItem[] = []
    if (openTabIds && openTabIds.length > 0) {
      for (const id of openTabIds) {
        const group = groupsById.get(id)
        if (group) {
          items.push({
            kind: 'group',
            id: group.id,
            group,
            pinned: group.pinned
          })
          continue
        }
        const session = tabsById.get(id)
        if (session) {
          items.push({
            kind: 'chat',
            id: session.id,
            session,
            pinned: session.organizeLabel === 'pinned'
          })
        }
      }
    } else {
      for (const tab of tabs) {
        items.push({
          kind: 'chat',
          id: tab.id,
          session: tab,
          pinned: tab.organizeLabel === 'pinned'
        })
      }
      for (const g of groups ?? []) {
        items.push({ kind: 'group', id: g.id, group: g, pinned: g.pinned })
      }
    }
    // Pin cluster: los pinned mantienen su orden relativo pero saltan al frente.
    const pinned = items.filter(item => item.pinned)
    const rest = items.filter(item => !item.pinned)
    return [...pinned, ...rest]
  }, [openTabIds, tabs, tabsById, groupsById, groups])

  const orderedTabs = useMemo(
    () =>
      orderedItems
        .filter((item): item is TabItem & { kind: 'chat' } => item.kind === 'chat')
        .map(item => item.session),
    [orderedItems]
  )

  const sortableIds = useMemo(
    () => orderedItems.map(item => item.id),
    [orderedItems]
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

    // Si el tab activo YA está totalmente visible en el viewport del
    // strip, no scrolleamos: el usuario acaba de clickear un tab que
    // ya ve, no tiene sentido animar. El centrado automático solo
    // aplica cuando el tab está fuera del viewport (típicamente
    // porque el usuario navegó desde el sidebar o el dropdown "All
    // tabs" a un tab que no estaba a la vista).
    const stripRect = strip.getBoundingClientRect()
    const tabRect = tabEl.getBoundingClientRect()
    const isFullyVisible =
      tabRect.left >= stripRect.left && tabRect.right <= stripRect.right
    if (isFullyVisible) {
      didScrollOnceRef.current = true
      return
    }

    const isFirst = idx === 0
    const isLast = idx === orderedItems.length - 1

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

  /*
   * Lista del dropdown "All tabs" — mezcla chats y grupos en el mismo
   * orden que la strip (respetando openTabIds), con búsqueda unificada.
   * Antes había una sección aparte "Split view groups" que aislaba a los
   * grupos con sub-items; se eliminó — un grupo aparece como una fila
   * igual a un chat, con su propio título y conteo.
   */
  const filteredSearchItems = useMemo(() => {
    const needle = searchQuery.trim().toLowerCase()
    if (!needle) return orderedItems
    return orderedItems.filter(item => {
      const title =
        item.kind === 'chat'
          ? item.session.title || 'Untitled'
          : item.group.name || 'Group'
      return title.toLowerCase().includes(needle)
    })
  }, [orderedItems, searchQuery])

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
  const menuGroup = menu
    ? (groups ?? []).find(g => g.id === menu.sessionId) || null
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
    // Pin cluster: pinneados adelante, respetando su nuevo orden relativo.
    // Aplica tanto a chats pinned como a grupos pinned — todo item que se
    // marque como pinned salta al frente por igual.
    const pinnedById = new Map(
      orderedItems.map(item => [item.id, item.pinned])
    )
    const pinned = nextIds.filter(id => pinnedById.get(id))
    const rest = nextIds.filter(id => !pinnedById.get(id))
    onReorder([...pinned, ...rest])
  }

  const openContextMenu = (id: string, event: React.MouseEvent) => {
    setMenu({ sessionId: id, x: event.clientX, y: event.clientY })
  }

  const selectionCount = selectedChatIds?.size ?? 0
  return (
    <div className="relative z-[1] flex min-w-0 flex-1 items-end">
      {selectionCount >= 2 &&
      onCreateSplitFromSelection &&
      onClearSelection ? (
        <div className="border-primary/40 bg-primary/5 text-foreground absolute -top-[36px] left-2 z-10 flex items-center gap-2 rounded-md border px-2 py-1 text-[12px] shadow-sm">
          <Columns2 className="text-primary size-3.5" />
          <span className="font-medium">
            {selectionCount} chats seleccionados
          </span>
          <button
            type="button"
            onClick={onCreateSplitFromSelection}
            className="bg-primary text-primary-foreground hover:bg-primary/90 ml-1 rounded-md px-2 py-0.5 text-[11px] font-semibold"
          >
            Split view
          </button>
          <button
            type="button"
            onClick={onClearSelection}
            className="text-muted-foreground hover:text-foreground rounded-md px-1.5 py-0.5 text-[11px]"
          >
            Cancelar
          </button>
        </div>
      ) : null}
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
              {orderedItems.map(item => {
                if (item.kind === 'chat') {
                  const tab = item.session
                  return (
                    <SessionTab
                      key={tab.id}
                      tab={tab}
                      active={tab.id === activeId}
                      color={tabColors[tab.id]}
                      unread={attentionIds.has(tab.id)}
                      draggable={draggable}
                      onSelect={(id, event) => {
                        if (
                          onToggleSelectChat &&
                          event &&
                          (event.shiftKey || event.metaKey)
                        ) {
                          onToggleSelectChat(id)
                          return
                        }
                        onSelect(id)
                      }}
                      onClose={onClose}
                      onContextMenu={openContextMenu}
                      selected={selectedChatIds?.has(tab.id) ?? false}
                    />
                  )
                }
                const group = item.group
                const pseudoTab: AgentSession = {
                  id: group.id,
                  title: group.name || 'Group',
                  status: 'idle',
                  source: 'local',
                  sourceLabel: 'Split view',
                  organizeLabel: group.pinned ? 'pinned' : null,
                  createdAt: new Date().toISOString(),
                  updatedAt: new Date().toISOString(),
                  lastMessageAt: null,
                  projectId: null,
                  titleSource: null,
                  workspacePath: null
                } as unknown as AgentSession
                return (
                  <SessionTab
                    key={group.id}
                    tab={pseudoTab}
                    active={group.id === activeId}
                    color={group.color || undefined}
                    unread={false}
                    draggable={draggable}
                    onSelect={onSelect}
                    onClose={onDissolveGroup || (() => {})}
                    onContextMenu={openContextMenu}
                    selected={selectedChatIds?.has(group.id) ?? false}
                    variant="group"
                    groupCount={
                      group.isPending ? undefined : group.chatIds.length
                    }
                  />
                )
              })}
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
                    aria-label={`All tabs (${orderedItems.length})`}
                  >
                    <ChevronDown className="size-3.5 shrink-0 stroke-[2.25]" />
                    {orderedItems.length > 0 ? (
                      <span className="text-[11px] font-semibold tabular-nums leading-none">
                        {orderedItems.length}
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
                {filteredSearchItems.length === 0 ? (
                  <p className="text-muted-foreground px-2 py-6 text-center text-xs">
                    No matches
                  </p>
                ) : (
                  filteredSearchItems.map(item => {
                    const active = item.id === activeId
                    const isGroup = item.kind === 'group'
                    const tab = isGroup ? null : item.session
                    const group = isGroup ? item.group : null
                    const title = isGroup
                      ? group!.name || 'Group'
                      : tab!.title || 'Untitled'
                    const stamp = isGroup
                      ? ''
                      : relativeTime(
                          tab!.lastMessageAt ||
                            tab!.updatedAt ||
                            tab!.createdAt
                        )
                    const color = isGroup ? group!.color : tabColors[item.id]
                    return (
                      <div
                        key={item.id}
                        role="option"
                        aria-selected={active}
                        tabIndex={0}
                        className={cn(
                          'group/item hover:bg-muted flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                          active && 'bg-muted'
                        )}
                        onClick={event => {
                          if (
                            !isGroup &&
                            onToggleSelectChat &&
                            (event.shiftKey || event.metaKey)
                          ) {
                            onToggleSelectChat(item.id)
                            return
                          }
                          onSelect(item.id)
                        }}
                        onKeyDown={event => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            onSelect(item.id)
                          }
                        }}
                        onContextMenu={event => {
                          event.preventDefault()
                          openContextMenu(item.id, event)
                        }}
                        data-selected={
                          selectedChatIds?.has(item.id) ? 'true' : undefined
                        }
                      >
                        <span className="bg-muted/80 flex size-7 shrink-0 items-center justify-center rounded-md">
                          {isGroup ? (
                            <Columns2 className="size-3.5" />
                          ) : (
                            <SessionStatusIcon status={tab!.status} />
                          )}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-2">
                            {color ? (
                              <span
                                className="size-2 shrink-0 rounded-full border border-black/10"
                                style={{ backgroundColor: color }}
                                aria-hidden
                              />
                            ) : null}
                            {isGroup && !group!.isPending ? (
                              <span
                                className="bg-muted text-foreground/70 inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded px-1 text-[10px] font-semibold tabular-nums"
                                aria-label={`${group!.chatIds.length} chats`}
                              >
                                {group!.chatIds.length}
                              </span>
                            ) : null}
                            <span className="text-foreground min-w-0 flex-1 truncate text-sm font-medium">
                              {title}
                            </span>
                            <span
                              className="relative block h-4 shrink-0"
                              style={{ width: 28 }}
                            >
                              {!isGroup ? (
                                <span className="text-muted-foreground absolute inset-0 inline-flex items-center justify-center text-[11px] tabular-nums transition-opacity group-hover/item:opacity-0">
                                  {stamp}
                                </span>
                              ) : null}
                              <button
                                type="button"
                                className="text-muted-foreground hover:text-foreground absolute inset-0 inline-flex items-center justify-center rounded-md opacity-0 transition-opacity group-hover/item:opacity-100"
                                aria-label={`Close ${title}`}
                                onClick={event => {
                                  event.stopPropagation()
                                  if (isGroup) {
                                    onCloseGroup?.(item.id)
                                  } else {
                                    onClose(item.id)
                                  }
                                }}
                              >
                                <X className="size-3.5" />
                              </button>
                            </span>
                          </span>
                          {!isGroup && tab!.organizeLabel === 'pinned' ? (
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
          {onMoveToProject && projects ? (
            <ProjectPicker
              projects={projects}
              value={menuSession.projectId}
              noneLabel="No project"
              trigger={
                <button
                  type="button"
                  className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px]"
                >
                  <Folder className="size-3.5" />
                  Move to project…
                </button>
              }
              onChange={projectId => {
                onMoveToProject(menuSession, projectId)
                setMenu(null)
              }}
            />
          ) : null}
          <TabContextSeparator />
          <div className="text-muted-foreground/80 px-2 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wide">
            Color
          </div>
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
          {onSplitWith ? (
            <>
              <TabContextSeparator />
              <TabContextItem
                icon={<Columns2 className="size-3.5" />}
                label="Create split view"
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
          {/*
            Delete queda fuera del context menu de la strip (y del
            dropdown "All tabs" — mismo menú). Es destructiva y en la
            strip se lee muy cerca de Close: fácil accidente. La acción
            vive solo en el sidebar izquierdo, en modo "organizar".
          */}
        </TabContextMenuShell>
      ) : null}

      {menu && menuGroup ? (
        <TabContextMenuShell
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
        >
          {onRenameGroup ? (
            <>
              <TabContextItem
                icon={<Pencil className="size-3.5" />}
                label="Rename…"
                onClick={() => runAction(() => onRenameGroup(menuGroup))}
              />
              <TabContextSeparator />
            </>
          ) : null}
          {onSetGroupColor ? (
            <>
              <div className="text-muted-foreground/80 px-2 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wide">
                Color
              </div>
              <TabInlineColorRow
                value={menuGroup.color}
                onSelect={color => {
                  onSetGroupColor(menuGroup.id, color)
                  setMenu(null)
                }}
                onClear={() => {
                  onSetGroupColor(menuGroup.id, null)
                  setMenu(null)
                }}
              />
              <TabContextSeparator />
            </>
          ) : null}
          {onCloseGroup ? (
            <TabContextItem
              icon={<X className="size-3.5" />}
              label="Close"
              onClick={() => runAction(() => onCloseGroup(menuGroup.id))}
            />
          ) : null}
          <TabContextItem
            icon={<CircleX className="size-3.5" />}
            label="Close others"
            disabled={orderedItems.length <= 1}
            onClick={() => runAction(() => onCloseOthers(menuGroup.id))}
          />
          {onDissolveGroup ? (
            <>
              <TabContextSeparator />
              <TabContextItem
                icon={<Trash2 className="size-3.5" />}
                label="Delete Split View"
                destructive
                onClick={() => {
                  setDissolveConfirm(menuGroup)
                  setMenu(null)
                }}
              />
            </>
          ) : null}
        </TabContextMenuShell>
      ) : null}
      <GroupDissolveDialog
        group={dissolveConfirm}
        chats={
          dissolveConfirm
            ? tabs.filter(t => dissolveConfirm.chatIds.includes(t.id))
            : []
        }
        onCancel={() => setDissolveConfirm(null)}
        onConfirm={() => {
          if (dissolveConfirm && onDissolveGroup) {
            onDissolveGroup(dissolveConfirm.id)
          }
          setDissolveConfirm(null)
        }}
      />
    </div>
  )
}

/**
 * Modal de confirmación para el "Delete Split View" (strip) o
 * "Dissolve split" (sidebar). Se enfatiza que los chats de adentro
 * NO se borran — sólo se liberan como conversaciones individuales.
 * Esa distinción es clave: la acción es destructiva sobre la
 * agrupación, no sobre las conversaciones.
 */
export function GroupDissolveDialog({
  group,
  chats,
  onCancel,
  onConfirm
}: {
  group: SessionGroup | null
  chats: AgentSession[]
  onCancel: () => void
  onConfirm: () => void
}) {
  const open = group !== null
  const label = group?.name || 'Group'
  return (
    <Dialog open={open} onOpenChange={next => (next ? null : onCancel())}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete Split View</DialogTitle>
          <DialogDescription>
            El split view <span className="text-foreground font-medium">{label}</span>{' '}
            desaparece. Los chats que viven dentro se quedan sueltos como
            conversaciones individuales — ninguna se borra.
          </DialogDescription>
        </DialogHeader>
        {chats.length > 0 ? (
          <div className="border-border/60 max-h-56 overflow-y-auto rounded-md border">
            <ul className="divide-border/60 divide-y text-[13px]">
              {chats.map(chat => (
                <li key={chat.id} className="truncate px-3 py-2">
                  {chat.title || 'Untitled'}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <DialogFooter>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button size="sm" variant="destructive" onClick={onConfirm}>
            Delete Split View
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
