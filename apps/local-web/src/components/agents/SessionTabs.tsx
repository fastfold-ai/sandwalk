import './session-chrome-tabs.css'

import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors} from '@dnd-kit/core'
import {
  restrictToHorizontalAxis,
  restrictToParentElement
} from '@dnd-kit/modifiers'
import {
  arrayMove,
  horizontalListSortingStrategy,
  SortableContext
} from '@dnd-kit/sortable'
import type {
  AgentProject,
  AgentSession,
  ExternalAgentKind,
  SessionGroup,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import {
  Archive,
  ChevronDown,
  CircleX,
  Columns2,
  Copy,
  Download,
  Folder,
  LayoutGrid,
  Pencil,
  Pin,
  Plus,
  Search,
  SquareTerminal,
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
import {
  DRAFT_AGENT_SESSION_ID,
  isDraftAgentSessionId
} from '@/lib/draft-agent'
import { duplicateChat } from '@/lib/duplicate-chat'
import type { PaneSplitDirection, PaneSplitTarget } from '@/lib/pane-split'
import { perfCount } from '@/lib/perf-probe'
import { relativeTime } from '@/lib/sessions'
import { cn } from '@/lib/utils'

import {
  ContinueInSubmenu,
  ConvertTerminalItem,
  NewTabMenu
} from './ExternalAgentMenuBlocks'
import { gridLayoutChoices } from './GridArrangeControl'
import { ProjectPicker } from './ProjectPicker'
import { useSessionTabColors } from './session-tab-colors'
import { SessionStatusIcon } from './SessionStatusIcon'
import { SessionTab } from './SessionTab'
import { SplitMenuBlock } from './split-menu'
import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator,
  TabContextSubmenu,
  TabInlineColorRow
} from './tab-context-menu'
import { TerminalTypeIcon } from './TerminalTypeIcon'

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
  onDelete: _onDelete,
  onCreateSession,
  groups,
  openTabIds,
  onSplitWith,
  onSplitPane,
  onDissolveGroup,
  onRenameGroup,
  onSetGroupColor,
  onSetGroupPinned,
  onArrangeGroup,
  onCloseGroup,
  selectedChatIds,
  onToggleSelectChat,
  onClearSelection,
  onCreateSplitFromSelection,
  terminals,
  onCreateTerminal,
  onCreateAgentTerminal,
  onRenameTerminal,
  onToggleTerminalOrganizeLabel,
  onMoveTerminalToProject
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
  /** Split this tab into a new pane of the chosen kind. */
  onSplitPane?: (
    sourceId: string,
    direction: PaneSplitDirection,
    target: PaneSplitTarget
  ) => void
  onDissolveGroup?: (groupId: string) => void
  onRenameGroup?: (group: SessionGroup) => void
  onSetGroupColor?: (groupId: string, color: string | null) => void
  /**
   * FAS-107 X4.2b: pin/unpin del grupo. Antes el store tenía la acción
   * (`useAppTabGroups.setGroupPinned`) pero ninguna superficie la
   * exponía — asimetría §3.2 con chats y terminales.
   */
  onSetGroupPinned?: (groupId: string, pinned: boolean) => void
  /** Relayout this group's panes into equal rows and columns. */
  onArrangeGroup?: (groupId: string, rows: number, cols: number) => void
  onCloseGroup?: (groupId: string) => void
  selectedChatIds?: Set<string>
  onToggleSelectChat?: (id: string) => void
  onClearSelection?: () => void
  onCreateSplitFromSelection?: () => void
  /**
   * Terminal-as-first-class-item chips (FAS-107). Optional. When
   * provided, ids in `openTabIds` that match a terminal render as a
   * SessionTab with `variant="terminal"` (gray terminal icon, or the CLI logo).
   */
  terminals?: TerminalSession[]
  onCloseTerminal?: (terminalId: string) => void
  /** FAS-107 GF5: opens a new terminal from the tab-strip "+" menu. */
  onCreateTerminal?: () => void
  /** "+" menu: open a terminal that starts Claude Code, Codex, OpenCode, or fx. */
  onCreateAgentTerminal?: (kind: ExternalAgentKind) => void
  /** FAS-107 GF-PARITY-5: parity actions for the terminal chip context menu. */
  onRenameTerminal?: (terminalId: string) => void
  onToggleTerminalOrganizeLabel?: (
    terminalId: string,
    label: 'pinned' | 'archive'
  ) => void | Promise<void>
  onMoveTerminalToProject?: (
    terminalId: string,
    projectId: string | null
  ) => void | Promise<void>
}) {
  perfCount('render.SessionTabs')
  const [menu, setMenu] = useState<TabContextMenuState | null>(null)
  // Confirmation modal for "Delete Split View": the action dissolves
  // the group (chats become standalone conversations again) —
  // irreversible in the sense that the grouping is lost, but no chat
  // is deleted.
  const [dissolveConfirm, setDissolveConfirm] = useState<SessionGroup | null>(
    null
  )
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const { tabColors, setTabColor } = useSessionTabColors()
  const attentionIds = useSessionAttentionIds()
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const stripRef = useRef<HTMLDivElement | null>(null)
  const newMenuButtonRef = useRef<HTMLButtonElement | null>(null)
  const newMenuRef = useRef<HTMLDivElement | null>(null)
  const [newMenu, setNewMenu] = useState<{ top: number; right: number } | null>(null)
  useEffect(() => {
    if (!newMenu) return
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (newMenuRef.current?.contains(target) || newMenuButtonRef.current?.contains(target)) return
      setNewMenu(null)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setNewMenu(null)
    }
    window.addEventListener('pointerdown', onPointerDown, true)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('pointerdown', onPointerDown, true)
      window.removeEventListener('keydown', onKey)
    }
  }, [newMenu])

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
    | {
        kind: 'terminal'
        id: string
        terminal: TerminalSession
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

  const terminalsById = useMemo(() => {
    const map = new Map<string, TerminalSession>()
    for (const t of terminals ?? []) map.set(t.id, t)
    return map
  }, [terminals])

  const orderedItems = useMemo<TabItem[]>(() => {
    // The caller (App shell) always drives the strip through `openTabIds`.
    // An EMPTY array means "no tabs open" — render nothing, not "fall back
    // and paint every group that exists across every project". The old
    // `else` branch was defensive dead code that fired during the single
    // frame between `setOpenTabIds([])` and the router settling on `/`,
    // making every split group visually reappear.
    const items: TabItem[] = []
    if (isDraftAgentSessionId(activeId)) {
      items.push({
        kind: 'chat',
        id: DRAFT_AGENT_SESSION_ID,
        pinned: false,
        session: {
          id: DRAFT_AGENT_SESSION_ID,
          title: 'New Agent',
          status: 'idle',
          projectId: null,
          organizeLabel: null,
          createdAt: '',
          updatedAt: '',
          lastMessageAt: null,
          workspacePath: null,
          titleSource: 'pending',
          source: null,
          sourceLabel: null
        } as unknown as AgentSession
      })
    }
    if (openTabIds) {
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
        const terminal = terminalsById.get(id)
        if (terminal) {
          items.push({
            kind: 'terminal',
            id: terminal.id,
            terminal,
            pinned: terminal.organizeLabel === 'pinned'
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
      // Legacy fallback for callers that don't pass `openTabIds` at all.
      // Kept behind a strict `undefined` check so passing `[]` no longer
      // trips it.
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
  }, [activeId, openTabIds, tabs, tabsById, groupsById, groups, terminalsById])

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

    // If the active tab is ALREADY fully visible in the strip's
    // viewport, don't scroll: the user just clicked a tab they can
    // already see, no point animating. Auto-centering only kicks in
    // when the tab is off-viewport (typically because the user
    // navigated from the sidebar or the "All tabs" dropdown to a tab
    // that wasn't in view).
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
          : item.kind === 'group'
            ? item.group.name || 'Group'
            : item.terminal.title || 'Terminal'
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
  const menuTerminal = menu
    ? (terminals ?? []).find(t => t.id === menu.sessionId) || null
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
    // FAS-107 GF-PARITY-5: terminals now share the same menu machinery as
    // chats/groups. `menuTerminal` (below) resolves the id → TerminalSession
    // so its dedicated menu branch renders.
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
                if (item.kind === 'terminal') {
                  const term = item.terminal
                  const pseudoTab: AgentSession = {
                    id: term.id,
                    title: term.title,
                    status: 'idle',
                    source: 'local',
                    sourceLabel: 'Terminal',
                    organizeLabel: term.organizeLabel ?? null,
                    createdAt: term.createdAt,
                    updatedAt: term.updatedAt,
                    lastMessageAt: null,
                    projectId: term.projectId,
                    titleSource: term.titleSource,
                    workspacePath: term.workspacePath
                  } as unknown as AgentSession
                  return (
                    <SessionTab
                      key={term.id}
                      tab={pseudoTab}
                      active={term.id === activeId}
                      color={tabColors[term.id]}
                      unread={false}
                      draggable={draggable}
                      onSelect={onSelect}
                      // X4.4-hotfix: la X del chip del terminal en el
                      // strip usaba `onCloseTerminal` = destructor real
                      // (borraba el terminal del disco → desaparecía
                      // del sidebar también). Los chats en la misma
                      // posición usan `onClose` = `closeSessionTab`
                      // (no destructivo, solo quita del strip). Ahora
                      // el terminal sigue el mismo patrón — la acción
                      // destructiva vive solo en el "Delete" del sidebar.
                      onClose={onClose}
                      onContextMenu={openContextMenu}
                      selected={selectedChatIds?.has(term.id) ?? false}
                      variant="terminal"
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
                    onClose={onCloseGroup ? () => onCloseGroup(group.id) : () => {}}
                    onContextMenu={openContextMenu}
                    selected={selectedChatIds?.has(group.id) ?? false}
                    variant="group"
                    groupCount={
                      group.isPending ? undefined : group.itemIds.length
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
          {/*
            FAS-107 GF5: the "+" now opens a dropdown with two entries
            (Agent chat / Terminal) so users can create either kind from
            the same affordance. When `onCreateTerminal` isn't wired the
            button falls back to the classic single-action behavior for
            backwards compatibility.
          */}
          {onCreateTerminal ? (
            <>
              <button
                ref={newMenuButtonRef}
                type="button"
                data-tauri-drag-region="false"
                className={cn(
                  `sandwalk-tab-overflow-btn inline-flex ${OVERFLOW_BTN_HEIGHT} items-center justify-center gap-1 rounded-lg`,
                  'px-2.5',
                  'bg-black/[0.06] text-foreground/85',
                  'hover:bg-black/[0.1] hover:text-foreground',
                  'dark:bg-white/[0.1] dark:text-zinc-100',
                  'dark:hover:bg-white/[0.16] dark:hover:text-white'
                )}
                aria-label="New"
                aria-expanded={newMenu != null}
                onPointerDown={event => {
                  if (event.button !== 0) return
                  event.preventDefault()
                  event.stopPropagation()
                  const rect = event.currentTarget.getBoundingClientRect()
                  setNewMenu(current =>
                    current
                      ? null
                      : { top: rect.bottom + 4, right: Math.max(8, window.innerWidth - rect.right) }
                  )
                }}
                onMouseDown={event => event.stopPropagation()}
                onClick={event => event.stopPropagation()}
              >
                <Plus className="size-3.5 shrink-0" />
              </button>
              <NewTabMenu
                open={newMenu != null}
                top={newMenu?.top ?? 0}
                right={newMenu?.right ?? 8}
                menuRef={newMenuRef}
                onCreateSession={() => {
                  setNewMenu(null)
                  onCreateSession()
                }}
                onCreateTerminal={() => {
                  setNewMenu(null)
                  onCreateTerminal()
                }}
                onCreateAgentTerminal={kind => {
                  setNewMenu(null)
                  onCreateAgentTerminal?.(kind)
                }}
              />
            </>
          ) : (
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
          )}
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
                    const isTerminal = item.kind === 'terminal'
                    const title =
                      item.kind === 'chat'
                        ? item.session.title || 'Untitled'
                        : item.kind === 'group'
                          ? item.group.name || 'Group'
                          : item.terminal.title || 'Terminal'
                    const stamp =
                      item.kind === 'chat'
                        ? relativeTime(
                            item.session.lastMessageAt ||
                              item.session.updatedAt ||
                              item.session.createdAt
                          )
                        : item.kind === 'terminal'
                          ? relativeTime(
                              item.terminal.updatedAt || item.terminal.createdAt
                            )
                          : ''
                    const color =
                      item.kind === 'group' ? item.group.color : tabColors[item.id]
                    const pinnedBadge =
                      item.kind === 'chat'
                        ? item.session.organizeLabel === 'pinned'
                        : item.kind === 'terminal'
                          ? item.terminal.organizeLabel === 'pinned'
                          : item.group.pinned
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
                            item.kind === 'chat' &&
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
                          item.kind === 'chat' && selectedChatIds?.has(item.id)
                            ? 'true'
                            : undefined
                        }
                      >
                        <span className="bg-muted/80 flex size-7 shrink-0 items-center justify-center rounded-md">
                          {isGroup ? (
                            <Columns2 className="size-3.5" />
                          ) : isTerminal ? (
                            <TerminalTypeIcon terminalId={item.id} />
                          ) : (
                            <SessionStatusIcon status={item.session.status} />
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
                            {item.kind === 'group' && !item.group.isPending ? (
                              <span
                                className="bg-muted text-foreground/70 inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded px-1 text-[10px] font-semibold tabular-nums"
                                aria-label={`${item.group.itemIds.length} chats`}
                              >
                                {item.group.itemIds.length}
                              </span>
                            ) : null}
                            <span className="text-foreground min-w-0 flex-1 truncate text-sm font-medium">
                              {title}
                            </span>
                            <span
                              className="relative block h-4 shrink-0"
                              style={{ width: 28 }}
                            >
                              {stamp ? (
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
                                  if (item.kind === 'group') {
                                    onCloseGroup?.(item.id)
                                  } else {
                                    // X4.4-hotfix: chats Y terminales
                                    // usan el mismo `onClose` (no
                                    // destructivo, solo quita del
                                    // strip). Antes los terminales
                                    // caían en `onCloseTerminal` que
                                    // los borraba del disco.
                                    onClose(item.id)
                                  }
                                }}
                              >
                                <X className="size-3.5" />
                              </button>
                            </span>
                          </span>
                          {pinnedBadge ? (
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

      {menu && isDraftAgentSessionId(menu.sessionId) ? (
        <TabContextMenuShell
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
        >
          {onSplitPane ? (
            <SplitMenuBlock
              sourceId={menu.sessionId}
              trailingSeparator={false}
              onSplitPane={(id, direction, target) =>
                runAction(() => onSplitPane(id, direction, target))
              }
            />
          ) : (
            <TabContextItem
              icon={<SquareTerminal className="size-3.5" />}
              label="New terminal"
              disabled={!onCreateTerminal}
              onClick={() => runAction(() => onCreateTerminal?.())}
            />
          )}
        </TabContextMenuShell>
      ) : null}

      {menu && menuSession ? (
        <TabContextMenuShell
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
        >
          {onSplitPane ? (
            <SplitMenuBlock
              sourceId={menuSession.id}
              onSplitPane={(id, direction, target) =>
                runAction(() => onSplitPane(id, direction, target))
              }
            />
          ) : null}
          <TabContextItem
            icon={<Pencil className="size-3.5" />}
            label="Rename chat…"
            onClick={() => runAction(() => onRename(menuSession))}
          />
          <TabContextItem
            icon={<Copy className="size-3.5" />}
            label="Duplicate chat"
            onClick={() => runAction(() => void duplicateChat(menuSession))}
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
                  role="menuitem"
                  className="hover:bg-muted flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-xs [&_svg]:size-3"
                >
                  <Folder />
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
            label="Export transcript"
            onClick={() => runAction(() => onExport(menuSession))}
          />
          <TabContextItem
            icon={<Search className="size-3.5" />}
            label="Inspect chat"
            onClick={() => runAction(() => onInspect(menuSession))}
          />
          <ContinueInSubmenu session={menuSession} onClose={() => setMenu(null)} />
          <TabContextItem
            icon={<Archive className="size-3.5" />}
            label={
              menuSession.organizeLabel === 'archive' ? 'Unarchive' : 'Archive'
            }
            onClick={() => runAction(() => onArchive(menuSession))}
          />
          <TabContextSeparator />
          <TabContextItem
            icon={<X className="size-3.5" />}
            label="Close tab"
            onClick={() => runAction(() => onClose(menuSession.id))}
          />
          <TabContextItem
            icon={<CircleX className="size-3.5" />}
            label="Close other tabs"
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
          {onSplitPane ? (
            <SplitMenuBlock
              sourceId={menuGroup.activeChatId || menuGroup.itemIds[0]}
              onSplitPane={(id, direction, target) =>
                runAction(() => onSplitPane(id, direction, target))
              }
            />
          ) : null}
          {onRenameGroup ? (
            <>
              <TabContextItem
                icon={<Pencil className="size-3.5" />}
                label="Rename split…"
                onClick={() => runAction(() => onRenameGroup(menuGroup))}
              />
            </>
          ) : null}
          {onSetGroupPinned ? (
            <TabContextItem
              icon={<Pin className="size-3.5" />}
              label={menuGroup.pinned ? 'Unpin' : 'Pin'}
              onClick={() =>
                runAction(() => onSetGroupPinned(menuGroup.id, !menuGroup.pinned))
              }
            />
          ) : null}
          {onArrangeGroup && menuGroup.itemIds.length >= 2 ? (
            <TabContextSubmenu
              icon={<LayoutGrid className="size-3.5 text-muted-foreground" />}
              label="Grid"
            >
              {gridLayoutChoices(menuGroup.itemIds.length).map(choice => (
                <TabContextItem
                  key={choice.label}
                  icon={<LayoutGrid className="size-3.5 text-muted-foreground" />}
                  label={choice.label}
                  trailing={
                    <span className="text-muted-foreground text-[11px] tabular-nums">
                      {choice.cols}×{choice.rows}
                    </span>
                  }
                  onClick={() =>
                    runAction(() =>
                      onArrangeGroup(menuGroup.id, choice.rows, choice.cols)
                    )
                  }
                />
              ))}
            </TabContextSubmenu>
          ) : null}
          {onRenameGroup || onSetGroupPinned || onArrangeGroup ? (
            <TabContextSeparator />
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
              label="Close tab"
              onClick={() => runAction(() => onCloseGroup(menuGroup.id))}
            />
          ) : null}
          <TabContextItem
            icon={<CircleX className="size-3.5" />}
            label="Close other tabs"
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

      {menu && menuTerminal ? (
        <TabContextMenuShell
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
        >
          {onRenameTerminal ? (
            <TabContextItem
              icon={<Pencil className="size-3.5" />}
              label="Rename terminal…"
              onClick={() =>
                runAction(() => onRenameTerminal(menuTerminal.id))
              }
            />
          ) : null}
          {onToggleTerminalOrganizeLabel ? (
            <TabContextItem
              icon={<Pin className="size-3.5" />}
              label={
                menuTerminal.organizeLabel === 'pinned' ? 'Unpin' : 'Pin'
              }
              onClick={() =>
                runAction(() =>
                  void onToggleTerminalOrganizeLabel(menuTerminal.id, 'pinned')
                )
              }
            />
          ) : null}
          {onMoveTerminalToProject && projects ? (
            <ProjectPicker
              projects={projects}
              value={menuTerminal.projectId}
              noneLabel="No project"
              trigger={
                <button
                  type="button"
                  role="menuitem"
                  className="hover:bg-muted flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-xs [&_svg]:size-3"
                >
                  <Folder />
                  Move to project…
                </button>
              }
              onChange={projectId => {
                void onMoveTerminalToProject(menuTerminal.id, projectId)
                setMenu(null)
              }}
            />
          ) : null}
          <TabContextSeparator />
          <div className="text-muted-foreground/80 px-2 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wide">
            Color
          </div>
          <TabInlineColorRow
            value={tabColors[menuTerminal.id] || null}
            onSelect={color => {
              setTabColor(menuTerminal.id, color)
              setMenu(null)
            }}
            onClear={() => {
              setTabColor(menuTerminal.id, null)
              setMenu(null)
            }}
          />
          {onToggleTerminalOrganizeLabel ? (
            <>
              <TabContextSeparator />
              <TabContextItem
                icon={<Archive className="size-3.5" />}
                label={
                  menuTerminal.organizeLabel === 'archive'
                    ? 'Unarchive'
                    : 'Archive'
                }
                onClick={() =>
                  runAction(() =>
                    void onToggleTerminalOrganizeLabel(
                      menuTerminal.id,
                      'archive'
                    )
                  )
                }
              />
            </>
          ) : null}
          {onSplitWith ? (
            <>
              <TabContextSeparator />
              <TabContextItem
                icon={<Columns2 className="size-3.5" />}
                label="Create split view"
                onClick={() => runAction(() => onSplitWith(menuTerminal.id))}
              />
            </>
          ) : null}
          <TabContextSeparator />
          <ConvertTerminalItem
            terminal={menuTerminal}
            onDone={() => setMenu(null)}
          />
          <TabContextItem
            icon={<X className="size-3.5" />}
            label="Close tab"
            // X4.4-hotfix: paridad con la X del chip. Close tab quita
            // el terminal del strip, NO lo borra del disco. El delete
            // real vive en el sidebar como "Delete".
            onClick={() => runAction(() => onClose(menuTerminal.id))}
          />
          <TabContextItem
            icon={<CircleX className="size-3.5" />}
            label="Close other tabs"
            disabled={orderedItems.length <= 1}
            onClick={() => runAction(() => onCloseOthers(menuTerminal.id))}
          />
        </TabContextMenuShell>
      ) : null}

      <GroupDissolveDialog
        group={dissolveConfirm}
        chats={
          dissolveConfirm
            ? tabs.filter(t => dissolveConfirm.itemIds.includes(t.id))
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
