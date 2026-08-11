import type { AgentSession } from '@sandwalk/agent-ui-core'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Pin, X } from 'lucide-react'
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

function TabBackground() {
  const ref = useRef<HTMLDivElement | null>(null)
  const [width, setWidth] = useState(240)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => setWidth(el.clientWidth)
    update()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      className="chrome-tab-background pointer-events-none absolute inset-0"
    >
      <svg
        className="block h-full w-full"
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
  onSelect: (id: string) => void
  onClose: (id: string) => void
  onContextMenu: (id: string, event: React.MouseEvent) => void
}

export function SessionTab({
  tab,
  active,
  color,
  unread,
  draggable,
  onSelect,
  onClose,
  onContextMenu
}: SessionTabProps) {
  const [hovering, setHovering] = useState(false)
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: tab.id, disabled: !draggable })

  const pinned = tab.organizeLabel === 'pinned'
  const title = tab.title || 'Untitled'
  const showClose = !pinned

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
    zIndex: isDragging ? 5 : active ? 4 : hovering ? 3 : 1
  }

  return (
    <div
      ref={setNodeRef}
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
        onSelect(tab.id)
      }}
      onContextMenu={event => {
        event.preventDefault()
        onContextMenu(tab.id, event)
      }}
      {...(active ? { 'data-active': 'true' } : {})}
    >
      <TabBackground />
      <div className="chrome-tab-content">
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
        <TabMarqueeTitle text={title} active={active} hovering={hovering} />
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
