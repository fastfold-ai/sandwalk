import type { AgentSession } from '@sandwalk/agent-ui-core'
import { Tabs } from '@sinm/react-chrome-tabs'
import type { TabProperties } from '@sinm/react-chrome-tabs/dist/chrome-tabs'
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
import { createPortal } from 'react-dom'

import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useSessionAttentionIds } from '@/hooks/useSessionAttention'
import { cn } from '@/lib/utils'

import { chromeTabMinOuter, chromeTabOverlap } from './chrome-tab-layout'
import { useSessionTabColors } from './session-tab-colors'
import { SessionSourceIcon } from './SessionSourceIcon'
import { SessionStatusIcon } from './SessionStatusIcon'
import {
  TAB_INLINE_COLORS,
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator,
  TabInlineColorRow
} from './tab-context-menu'

import '@sinm/react-chrome-tabs/css/chrome-tabs.css'
import '@sinm/react-chrome-tabs/css/chrome-tabs-dark-theme.css'
/* After the package CSS so divider/close overrides actually win. */
import './session-chrome-tabs.css'

/** Same Blue pastel as the tab color tag — marks unread notification sessions. */
const UNREAD_DOT_COLOR =
  TAB_INLINE_COLORS.find(item => item.name === 'Blue')?.value ?? '#8BB8F5'

const TAB_MIN_OUTER = chromeTabMinOuter
const TAB_OVERLAP = chromeTabOverlap

type TabContextMenuState = {
  sessionId: string
  x: number
  y: number
}

function useDocumentDark() {
  const [dark, setDark] = useState(
    () =>
      typeof document !== 'undefined' &&
      document.documentElement.classList.contains('dark')
  )
  useEffect(() => {
    const root = document.documentElement
    const sync = () => setDark(root.classList.contains('dark'))
    sync()
    const observer = new MutationObserver(sync)
    observer.observe(root, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])
  return dark
}

/** Title marquee — same feel as sidebar session rows. */
function TabMarqueeTitle({
  text,
  active,
  hovering
}: {
  text: string
  active: boolean
  hovering: boolean
}) {
  const wrapRef = useRef<HTMLSpanElement>(null)
  const textRef = useRef<HTMLSpanElement>(null)
  const revealTimerRef = useRef<number | null>(null)
  const [overflow, setOverflow] = useState(0)
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

  useEffect(() => {
    clearRevealTimer()
    setRevealEnd(false)
    if (!hovering) return
    const next = measureOverflow()
    setOverflow(next)
    if (next <= 0) return
    const duration = Math.min(10, Math.max(2.2, next / 26)) * 1000
    revealTimerRef.current = window.setTimeout(() => {
      setRevealEnd(true)
      revealTimerRef.current = null
    }, duration * 0.4)
  }, [hovering, text])

  const durationSec =
    overflow > 0 ? Math.min(10, Math.max(2.2, overflow / 26)) : 0.35
  const easing = 'cubic-bezier(0.35, 0.12, 0.2, 1)'
  const edgeFade =
    overflow <= 0
      ? undefined
      : hovering && revealEnd
        ? 'linear-gradient(to right, transparent, #000 10px, #000 100%)'
        : hovering
          ? 'linear-gradient(to right, transparent, #000 10px, #000 calc(100% - 10px), transparent)'
          : 'linear-gradient(to right, #000 0%, #000 calc(100% - 12px), transparent)'

  return (
    <span
      ref={wrapRef}
      className="min-w-0 flex-1 overflow-hidden"
      style={
        edgeFade
          ? { maskImage: edgeFade, WebkitMaskImage: edgeFade }
          : undefined
      }
    >
      <span
        ref={textRef}
        className={cn(
          'inline-block whitespace-nowrap text-xs font-medium leading-none will-change-transform',
          active ? 'text-foreground' : 'text-muted-foreground'
        )}
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

function ensureLabelHost(tabEl: Element) {
  const content = tabEl.querySelector('.chrome-tab-content')
  if (!content) return null
  let host = content.querySelector(
    '.sandwalk-tab-label-host'
  ) as HTMLElement | null
  if (!host) {
    host = document.createElement('div')
    host.className = 'sandwalk-tab-label-host'
    content.insertBefore(host, content.firstChild)
  }
  return host
}

function useTabHover(root: HTMLElement | null, tabId: string) {
  const [hovering, setHovering] = useState(false)
  useEffect(() => {
    if (!root) return
    const tabEl = root.querySelector(`[data-tab-id="${CSS.escape(tabId)}"]`)
    if (!tabEl) return
    const enter = () => setHovering(true)
    const leave = () => setHovering(false)
    tabEl.addEventListener('mouseenter', enter)
    tabEl.addEventListener('mouseleave', leave)
    return () => {
      tabEl.removeEventListener('mouseenter', enter)
      tabEl.removeEventListener('mouseleave', leave)
    }
  }, [root, tabId])
  return hovering
}

function TabChromeLabel({
  root,
  tab,
  active,
  color,
  unread
}: {
  root: HTMLElement | null
  tab: AgentSession
  active: boolean
  color?: string
  unread: boolean
}) {
  const hovering = useTabHover(root, tab.id)
  const pinned = tab.organizeLabel === 'pinned'
  const title = tab.title || 'Untitled'

  return (
    <>
      <SessionStatusIcon status={tab.status} />
      <SessionSourceIcon source={tab.source} label={tab.sourceLabel} />
      {pinned ? (
        <Pin
          className="text-muted-foreground size-3 shrink-0"
          aria-hidden
        />
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
      <TabMarqueeTitle text={title} active={active} hovering={hovering} />
    </>
  )
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
  const [labelHosts, setLabelHosts] = useState<Record<string, HTMLElement>>(
    {}
  )
  /** Tabs squeezed so the label isn’t readable (is-smaller / is-mini). */
  const [hiddenCount, setHiddenCount] = useState(0)
  const { tabColors, setTabColor } = useSessionTabColors()
  const attentionIds = useSessionAttentionIds()
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const darkMode = useDocumentDark()

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

  const orderKey = orderedTabs.map(tab => tab.id).join('\0')

  const chromeTabs: TabProperties[] = useMemo(
    () =>
      orderedTabs.map(tab => ({
        id: tab.id,
        title: tab.title || 'Untitled',
        active: tab.id === activeId,
        favicon: false,
        isCloseIconVisible: tab.organizeLabel !== 'pinned'
      })),
    [orderedTabs, activeId]
  )

  /** Tabs that don’t fit at the content min (200px / ~218 outer) → +N. */
  const measureHiddenCount = (root: HTMLElement, tabCount: number) => {
    if (tabCount <= 1) return 0
    const strip = root.querySelector('.sandwalk-chrome-tabs')
    if (!(strip instanceof HTMLElement)) return 0
    const avail = strip.clientWidth
    if (avail <= 0) return 0
    const stride = TAB_MIN_OUTER - TAB_OVERLAP
    const capacity = Math.max(
      1,
      Math.floor((avail + TAB_OVERLAP) / stride)
    )
    return Math.max(0, tabCount - capacity)
  }

  // Label hosts + +N only — never rewrite lib transforms (causes click jumps).
  useEffect(() => {
    const root = rootRef.current
    if (!root) return

    let syncing = false
    const sync = () => {
      if (syncing) return
      syncing = true
      try {
        const next: Record<string, HTMLElement> = {}
        for (const tab of orderedTabs) {
          const tabEl = root.querySelector(
            `[data-tab-id="${CSS.escape(tab.id)}"]`
          )
          if (!tabEl) continue
          const host = ensureLabelHost(tabEl)
          if (host) next[tab.id] = host
        }
        const hidden = measureHiddenCount(root, orderedTabs.length)
        setHiddenCount(prev => (prev === hidden ? prev : hidden))
        setLabelHosts(prev => {
          const prevIds = Object.keys(prev)
          const nextIds = Object.keys(next)
          if (
            prevIds.length === nextIds.length &&
            nextIds.every(id => prev[id] === next[id])
          ) {
            return prev
          }
          return next
        })
      } finally {
        syncing = false
      }
    }

    sync()
    const frame = window.requestAnimationFrame(sync)
    const timer = window.setTimeout(sync, 50)
    const observer = new MutationObserver(sync)
    observer.observe(root, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class']
    })
    const strip = root.querySelector('.sandwalk-chrome-tabs')
    const ro =
      typeof ResizeObserver !== 'undefined' && strip
        ? new ResizeObserver(sync)
        : null
    if (ro && strip) ro.observe(strip)
    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(timer)
      observer.disconnect()
      ro?.disconnect()
    }
  }, [orderKey, orderedTabs])

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

  return (
    <div
      ref={rootRef}
      className="relative z-[1] flex min-w-0 flex-1 items-end"
    >
      {/* Own column — overflow:hidden so absolute tabs cannot cover the slot */}
      <div className="sandwalk-tab-strip-main min-w-0 flex-1 overflow-hidden">
        <Tabs
          className="sandwalk-chrome-tabs"
          darkMode={darkMode}
          draggable={Boolean(onReorder)}
          tabs={chromeTabs}
          onTabActive={onSelect}
          onTabClose={onClose}
          onTabReorder={(tabId, fromIndex, toIndex) => {
            if (!onReorder) return
            const ids = orderedTabs.map(tab => tab.id)
            if (
              fromIndex < 0 ||
              toIndex < 0 ||
              fromIndex >= ids.length ||
              toIndex >= ids.length
            ) {
              return
            }
            const [moved] = ids.splice(fromIndex, 1)
            if (!moved || moved !== tabId) return
            ids.splice(toIndex, 0, moved)
            const byId = new Map(orderedTabs.map(tab => [tab.id, tab]))
            const pinned = ids.filter(
              id => byId.get(id)?.organizeLabel === 'pinned'
            )
            const rest = ids.filter(
              id => byId.get(id)?.organizeLabel !== 'pinned'
            )
            onReorder([...pinned, ...rest])
          }}
          onContextMenu={(tabId, event) => {
            event.preventDefault()
            setMenu({
              sessionId: tabId,
              x: event.clientX,
              y: event.clientY
            })
          }}
        />
      </div>

      {/*
        Button chip (sibling of tabs):
          [  ⌄  +N  ]  — chevron left of count, extra left padding
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
            aria-label={
              hiddenCount > 0
                ? `Search tabs, ${hiddenCount} more`
                : 'Search tabs'
            }
            title="Search tabs"
          >
            <ChevronDown className="size-3.5 shrink-0 stroke-[2.25]" />
            {hiddenCount > 0 ? (
              <span className="text-[11px] font-semibold tabular-nums leading-none">
                +{hiddenCount}
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
              placeholder="Search Tabs"
              className="h-7 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
            />
            <span className="text-muted-foreground/70 shrink-0 text-[10px] tabular-nums">
              ⇧⌘A
            </span>
          </div>
          <div className="text-muted-foreground px-3 py-1.5 text-[10px] font-medium tracking-wide uppercase">
            {hiddenCount > 0
              ? `Open Tabs · +${hiddenCount}`
              : 'Open Tabs'}
          </div>
          <ScrollArea className="max-h-72">
            <div className="p-1.5 pt-0">
              {filteredSearchTabs.length === 0 ? (
                <p className="text-muted-foreground px-2 py-6 text-center text-xs">
                  No matching tabs
                </p>
              ) : (
                filteredSearchTabs.map(tab => {
                  const active = tab.id === activeId
                  const title = tab.title || 'Untitled'
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
                          <span className="text-foreground block truncate text-sm font-medium">
                            {title}
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
          </ScrollArea>
        </PopoverContent>
      </Popover>
      </div>

      {orderedTabs.map(tab => {
        const host = labelHosts[tab.id]
        if (!host) return null
        return createPortal(
          <TabChromeLabel
            key={tab.id}
            root={rootRef.current}
            tab={tab}
            active={tab.id === activeId}
            color={tabColors[tab.id]}
            unread={attentionIds.has(tab.id)}
          />,
          host
        )
      })}

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
