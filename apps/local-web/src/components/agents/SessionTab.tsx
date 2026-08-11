import type { AgentSession } from '@sandwalk/agent-ui-core'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Columns2, Pin, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

import { SessionSourceIcon } from './SessionSourceIcon'
import { SessionStatusIcon } from './SessionStatusIcon'
import { TAB_INLINE_COLORS } from './tab-context-menu'

const UNREAD_DOT_COLOR =
  TAB_INLINE_COLORS.find(item => item.name === 'Blue')?.value ?? '#8BB8F5'

/** Title marquee — same feel as the previous chrome-tabs label. */
function TabMarqueeTitle({
  text,
  active,
  hovering,
  tabWidth
}: {
  text: string
  active: boolean
  hovering: boolean
  /** Passed down from SessionTab so we can react to tab resize without
   * running a per-tab ResizeObserver (SessionTab already runs one). */
  tabWidth: number
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

  // Re-measure when the title text or the tab's outer width changes.
  useEffect(() => {
    setOverflow(measureOverflow())
  }, [text, tabWidth])

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
    // Cleanup runs on hovering/text change AND on unmount.
    return () => clearRevealTimer()
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

/**
 * Chrome-tab background: one single SVG path that draws the whole tab (both
 * ears + central body) in one stroke. The path is generated from the current
 * tab width so ears stay at their natural size and the body stretches with
 * the tab. No seams, no rendering-pipeline gaps between div and svg.
 */
function buildTabPath(width: number) {
  // Ear geometry (10×11 at each corner, 10-radius top curve, 20 px total)
  //   Top-left  : (20, 0) → (10, 10) via cubic
  //   Left down : (10, 10) → (10, 25)
  //   Bot-left  : (10, 25) → (0, 36) via cubic
  //   Floor     : (0, 36) → (width, 36)
  //   Bot-right : (width, 36) → (width-10, 25) via cubic
  //   Right up  : (width-10, 25) → (width-10, 10)
  //   Top-right : (width-10, 10) → (width-20, 0) via cubic
  //   Top seat  : (width-20, 0) → (20, 0)
  const bodyWidth = Math.max(0, width - 40)
  return (
    `M20 0 h${bodyWidth} ` +
    `c5.5 0 10 4.5 10 10 v15 c0 7 5 11 10 11 ` +
    `H0 ` +
    `c5 0 10-4 10-11 V10 c0-5.5 4.5-10 10-10 z`
  )
}

function TabBackground({ width }: { width: number }) {
  return (
    <div className="chrome-tab-background pointer-events-none absolute inset-0">
      {/* Hover-only shape: rounded rectangle (visible only on inactive hover) */}
      <div className="chrome-tab-hover-shape" />
      {/* Active-only shape: SVG with curved ears (visible only when active) */}
      <svg
        className="chrome-tab-active-shape block h-full w-full"
        width={width}
        height="36"
        viewBox={`0 0 ${width} 36`}
        preserveAspectRatio="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path d={buildTabPath(width)} className="chrome-tab-geometry" />
      </svg>
    </div>
  )
}

export type SessionTabProps = {
  tab: AgentSession
  active: boolean
  color?: string
  unread: boolean
  draggable: boolean
  onSelect: (id: string, event?: React.MouseEvent) => void
  onClose: (id: string) => void
  onContextMenu: (id: string, event: React.MouseEvent) => void
  selected?: boolean
  /**
   * Cuando la pestaña representa un grupo de split view, en vez del
   * SessionStatusIcon + SessionSourceIcon se dibuja el icono Columns2 y un
   * badge numérico con `groupCount`. Todo lo demás (chrome, hover, marquee,
   * X para disolver) se mantiene idéntico al de una pestaña de sesión.
   */
  variant?: 'session' | 'group'
  groupCount?: number
}

export function SessionTab({
  tab,
  active,
  color,
  unread,
  draggable,
  onSelect,
  onClose,
  onContextMenu,
  selected,
  variant = 'session',
  groupCount
}: SessionTabProps) {
  const isGroup = variant === 'group'
  const [hovering, setHovering] = useState(false)
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: tab.id, disabled: !draggable })

  // Single ResizeObserver per tab — width is passed down to TabBackground
  // (SVG path) and TabMarqueeTitle (overflow measurement) so we don't run
  // two independent observers per tab (was: 2N observers → now: N).
  const tabRef = useRef<HTMLDivElement | null>(null)
  const [tabWidth, setTabWidth] = useState(240)
  useEffect(() => {
    const el = tabRef.current
    if (!el) return
    const update = () => setTabWidth(el.clientWidth)
    update()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const combinedRef = (node: HTMLDivElement | null) => {
    setNodeRef(node)
    tabRef.current = node
  }

  const pinned = tab.organizeLabel === 'pinned'
  const title = tab.title || 'Untitled'
  const showClose = !pinned

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    // Solid on drag (no opacity dip) + soft lift shadow for presence.
    opacity: 1,
    filter: isDragging
      ? 'drop-shadow(0 6px 14px rgb(0 0 0 / 0.35))'
      : undefined,
    zIndex: isDragging ? 5 : active ? 4 : hovering ? 3 : 1
  }

  return (
    <div
      ref={combinedRef}
      className="chrome-tab"
      data-tab-id={tab.id}
      style={style}
      {...attributes}
      {...(draggable ? listeners : {})}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      onMouseDown={event => {
        // Left-click without close-button hit → activate.
        if (event.button !== 0) return
        const target = event.target as HTMLElement | null
        if (target?.closest('.chrome-tab-close')) return
        onSelect(tab.id, event)
      }}
      onContextMenu={event => {
        event.preventDefault()
        onContextMenu(tab.id, event)
      }}
      {...(active ? { 'data-active': 'true' } : {})}
      {...(selected ? { 'data-selected': 'true' } : {})}
    >
      <TabBackground width={tabWidth} />
      <div className="chrome-tab-content">
        {isGroup ? (
          <>
            <Columns2
              className="text-muted-foreground size-3.5 shrink-0"
              aria-hidden
            />
            {typeof groupCount === 'number' ? (
              <span
                className="bg-black/10 text-foreground/70 dark:bg-white/15 shrink-0 rounded-md px-1 text-[10px] font-semibold tabular-nums leading-none"
                aria-label={`${groupCount} chats in group`}
              >
                {groupCount}
              </span>
            ) : null}
          </>
        ) : (
          <>
            <SessionStatusIcon status={tab.status} />
            <SessionSourceIcon source={tab.source} label={tab.sourceLabel} />
          </>
        )}
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
        <TabMarqueeTitle
          text={title}
          active={active}
          hovering={hovering}
          tabWidth={tabWidth}
        />
      </div>
      {showClose ? (
        <button
          type="button"
          className="chrome-tab-close text-muted-foreground hover:text-foreground inline-flex items-center justify-center"
          aria-label={`Close ${title}`}
          onPointerDown={event => event.stopPropagation()}
          onClick={event => {
            event.stopPropagation()
            onClose(tab.id)
          }}
        >
          <X className="size-3.5" />
        </button>
      ) : null}
    </div>
  )
}
