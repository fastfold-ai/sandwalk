import type { AgentSession } from '@sandwalk/agent-ui-core'
import {
  Archive,
  CircleX,
  Download,
  Pencil,
  Pin,
  Search,
  Trash2,
  X
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useHorizontalWheelScroll } from '@/hooks/useHorizontalWheelScroll'
import { useSessionAttentionIds } from '@/hooks/useSessionAttention'
import { cn } from '@/lib/utils'

import { TAB_INLINE_COLORS } from './tab-context-menu'

/** Same Blue pastel as the tab color tag — marks unread notification sessions. */
const UNREAD_DOT_COLOR =
  TAB_INLINE_COLORS.find(item => item.name === 'Blue')?.value ?? '#8BB8F5'

import { useSessionTabColors } from './session-tab-colors'
import { SessionSourceIcon } from './SessionSourceIcon'
import { SessionStatusIcon } from './SessionStatusIcon'
import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator,
  TabInlineColorRow
} from './tab-context-menu'

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
  onRename: (session: AgentSession) => void
  onTogglePin: (session: AgentSession) => void
  onExport: (session: AgentSession) => void
  onInspect: (session: AgentSession) => void
  onArchive: (session: AgentSession) => void
  onDelete: (session: AgentSession) => void
}) {
  const [menu, setMenu] = useState<TabContextMenuState | null>(null)
  const { tabColors, setTabColor } = useSessionTabColors()
  const attentionIds = useSessionAttentionIds()
  const activeTabRef = useRef<HTMLDivElement | null>(null)
  const scrollerRef = useRef<HTMLDivElement | null>(null)
  useHorizontalWheelScroll(scrollerRef)

  const { pinnedTabs, scrollTabs } = useMemo(() => {
    const pinned: AgentSession[] = []
    const scroll: AgentSession[] = []
    for (const tab of tabs) {
      if (tab.organizeLabel === 'pinned') pinned.push(tab)
      else scroll.push(tab)
    }
    return { pinnedTabs: pinned, scrollTabs: scroll }
  }, [tabs])

  // Keep the selected unpinned tab in view when the bar overflows.
  const scrollIdsKey = scrollTabs.map(tab => tab.id).join('\0')
  useEffect(() => {
    if (!activeId) return
    if (pinnedTabs.some(tab => tab.id === activeId)) return
    const node = activeTabRef.current
    if (!node) return
    node.scrollIntoView({
      behavior: 'smooth',
      inline: 'nearest',
      block: 'nearest'
    })
  }, [activeId, pinnedTabs, scrollIdsKey])

  const menuSession = menu
    ? tabs.find(tab => tab.id === menu.sessionId) || null
    : null

  const runAction = (action: () => void) => {
    setMenu(null)
    action()
  }

  const renderTab = (tab: AgentSession, options?: { scrollActive?: boolean }) => {
    const active = tab.id === activeId
    const color = tabColors[tab.id]
    const pinned = tab.organizeLabel === 'pinned'
    const unread = attentionIds.has(tab.id)
    return (
      <div
        key={tab.id}
        ref={options?.scrollActive && active ? activeTabRef : undefined}
        className={cn(
          'group relative flex h-8 w-40 shrink-0 items-center rounded-md px-2.5',
          active
            ? 'bg-muted text-foreground'
            : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
        )}
        onContextMenu={event => {
          event.preventDefault()
          setMenu({
            sessionId: tab.id,
            x: event.clientX,
            y: event.clientY
          })
        }}
      >
        <button
          type="button"
          className="inline-flex min-w-0 flex-1 items-center gap-1.5 truncate pr-5 text-left text-xs font-medium leading-none"
          onClick={() => onSelect(tab.id)}
          title={tab.title || 'Untitled'}
        >
          <SessionStatusIcon status={tab.status} />
          <SessionSourceIcon source={tab.source} label={tab.sourceLabel} />
          {pinned ? (
            <Pin className="text-muted-foreground size-3 shrink-0" aria-hidden />
          ) : null}
          {unread ? (
            <span
              className="size-2 shrink-0 rounded-full border border-black/10"
              style={{ backgroundColor: UNREAD_DOT_COLOR }}
              aria-label="Unread"
            />
          ) : null}
          {color ? (
            <span
              className="size-2 shrink-0 rounded-full border border-black/10"
              style={{ backgroundColor: color }}
              aria-hidden
            />
          ) : null}
          <span className="truncate">{tab.title || 'Untitled'}</span>
        </button>
        <button
          type="button"
          className="bg-muted hover:bg-background/80 absolute right-0.5 top-1/2 inline-flex size-5 -translate-y-1/2 items-center justify-center rounded-sm opacity-0 group-hover:opacity-100"
          aria-label={`Close ${tab.title || 'Untitled'}`}
          onClick={event => {
            event.stopPropagation()
            onClose(tab.id)
          }}
        >
          <X className="size-3.5" />
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-8 min-w-0 flex-1 items-center gap-0.5">
      {pinnedTabs.length > 0 ? (
        <div className="border-border/50 flex h-8 shrink-0 items-center gap-0.5 border-r pr-1 mr-0.5">
          {pinnedTabs.map(tab => renderTab(tab))}
        </div>
      ) : null}

      <div
        ref={scrollerRef}
        className="session-tabs-scroll flex h-8 min-w-0 flex-1 items-center gap-0.5 overflow-x-auto overflow-y-hidden"
      >
        {scrollTabs.map(tab => renderTab(tab, { scrollActive: true }))}
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
